"""R3 审计第五类: SSUI D18-D25 经济数据 CRUD API + 校验门禁。

端点:
  GET    /api/v1/sites/{id}/economic-data          — 获取场地经济数据
  POST   /api/v1/sites/{id}/economic-data          — 录入/更新(含校验)
  DELETE /api/v1/sites/{id}/economic-data          — 清除
  GET    /api/v1/sites/{id}/economic-data/template — 下载 Excel 模板
  POST   /api/v1/sites/{id}/economic-data/import   — Excel 导入
"""
from __future__ import annotations

import math
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.core.config import get_settings
from app.core.deps import get_current_user, assert_site_access
from app.db.session import get_db
from app.models import EconomicIndicator, EconomicRawInput, Site, User
from app.services.economic_units import INDICATOR_DEFINITIONS, standardize_unit

router = APIRouter(prefix=get_settings().api_v1_prefix + "/sites", tags=["economic"])


def _require_site(db: Session, user: User, site_id: int) -> Site:
    s = db.get(Site, site_id)
    if not s:
        raise HTTPException(404, "场地不存在")
    assert_site_access(db, user, s)
    return s


# ── 校验工具 ──────────────────────────────────────────────────────
def _validate_numeric(value: float, indicator_code: str) -> float:
    """R3 审计第五类: 负数/NaN/Inf 拒绝。"""
    if value is None:
        raise ValueError(f"{indicator_code}: 值为空")
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        raise ValueError(f"{indicator_code}: 值为 NaN 或 Inf, 已拒绝")
    if value < 0:
        raise ValueError(f"{indicator_code}: 负数({value})不允许, 已拒绝")
    return float(value)


def _validate_cross_check(indicators: dict, raw_input: dict | None):
    """R3 审计: D23/D25 交叉校验。"""
    raw_input = raw_input or {}
    # D23 = gross_output / total_cost
    d23 = indicators.get("D23")
    go = raw_input.get("gross_output_yuan")
    tc = raw_input.get("total_cost_yuan")
    if d23 is not None and go is not None and tc is not None and tc > 0:
        expected_d23 = go / tc
        if abs(d23 - expected_d23) / max(expected_d23, 0.001) > 0.05:  # 5% 容差
            raise ValueError(f"D23 交叉校验失败: 值={d23}, 但 gross_output/total_cost={expected_d23:.4f}")

    # D25 = yield / area
    d25 = indicators.get("D25")
    yk = raw_input.get("yield_kg")
    ah = raw_input.get("area_hectare")
    if d25 is not None and yk is not None and ah is not None and ah > 0:
        expected_d25 = yk / ah
        if abs(d25 - expected_d25) / max(expected_d25, 0.001) > 0.05:
            raise ValueError(f"D25 交叉校验失败: 值={d25}, 但 yield/area={expected_d25:.4f}")

    # 面积=0 拒绝
    if ah is not None and ah == 0:
        raise ValueError("面积(area_hectare)不能为 0")


# ── Pydantic 模型 ─────────────────────────────────────────────────
class EconomicIndicatorInput(BaseModel):
    indicator_code: str  # D18-D25
    value: float
    unit: str = ""
    source_type: str = "site_actual"
    source_name: str | None = None
    source_year: int | None = None
    source_geography: str | None = None
    is_proxy: bool = False
    note: str | None = None

    @field_validator("indicator_code")
    @classmethod
    def validate_code(cls, v: str) -> str:
        if v not in INDICATOR_DEFINITIONS:
            raise ValueError(f"非法指标代码: {v}, 应为 D18-D25")
        return v

    @field_validator("value")
    @classmethod
    def validate_value(cls, v: float) -> float:
        return _validate_numeric(v, "value")


class EconomicDataBody(BaseModel):
    evaluation_year: int
    scenario: str = "production"
    crop_or_land_use: str | None = None
    indicators: list[EconomicIndicatorInput]
    # 原始汇总值(可选, 用于交叉校验)
    area_hectare: float | None = None
    yield_kg: float | None = None
    gross_output_yuan: float | None = None
    total_cost_yuan: float | None = None


# ── 端点 ──────────────────────────────────────────────────────────
@router.get("/{site_id}/economic-data")
def get_economic_data(site_id: int,
                      user: User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    """获取场地经济数据(D18-D25)。"""
    _require_site(db, user, site_id)
    rows = (db.query(EconomicIndicator)
            .filter_by(site_id=site_id)
            .order_by(EconomicIndicator.evaluation_year.desc(),
                      EconomicIndicator.indicator_code).all())
    raw_rows = (db.query(EconomicRawInput)
                .filter_by(site_id=site_id)
                .order_by(EconomicRawInput.evaluation_year.desc()).all())
    return {
        "site_id": site_id,
        "indicators": [{
            "id": r.id, "year": r.evaluation_year, "scenario": r.scenario,
            "code": r.indicator_code, "name": r.indicator_name,
            "value": r.raw_value, "unit": r.unit, "direction": r.direction,
            "source_type": r.source_type, "source_name": r.source_name,
            "source_year": r.source_year, "is_proxy": r.is_proxy,
            "confidence": r.confidence, "note": r.note,
        } for r in rows],
        "raw_inputs": [{
            "id": r.id, "year": r.evaluation_year, "scenario": r.scenario,
            "area_hectare": r.area_hectare, "yield_kg": r.yield_kg,
            "gross_output_yuan": r.gross_output_yuan, "total_cost_yuan": r.total_cost_yuan,
            "source_type": r.source_type,
        } for r in raw_rows],
        "indicator_definitions": INDICATOR_DEFINITIONS,
    }


@router.post("/{site_id}/economic-data")
def save_economic_data(site_id: int, body: EconomicDataBody,
                       user: User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    """录入/更新经济数据(含校验门禁)。"""
    _require_site(db, user, site_id)

    # 构建指标 dict 用于交叉校验
    ind_dict = {}
    for ind in body.indicators:
        ind_dict[ind.indicator_code] = ind.value

    # 交叉校验
    raw_input_data = {
        "gross_output_yuan": body.gross_output_yuan,
        "total_cost_yuan": body.total_cost_yuan,
        "yield_kg": body.yield_kg,
        "area_hectare": body.area_hectare,
    }
    try:
        _validate_cross_check(ind_dict, raw_input_data)
    except ValueError as e:
        raise HTTPException(422, str(e))

    # 删除同年份同场景的旧数据(幂等 upsert)
    db.query(EconomicIndicator).filter_by(
        site_id=site_id, evaluation_year=body.evaluation_year,
        scenario=body.scenario).delete()
    db.query(EconomicRawInput).filter_by(
        site_id=site_id, evaluation_year=body.evaluation_year,
        scenario=body.scenario).delete()

    # 写入经济指标
    for ind in body.indicators:
        defn = INDICATOR_DEFINITIONS[ind.indicator_code]
        db.add(EconomicIndicator(
            site_id=site_id, evaluation_year=body.evaluation_year,
            scenario=body.scenario, crop_or_land_use=body.crop_or_land_use,
            indicator_code=ind.indicator_code, indicator_name=defn["name"],
            raw_value=ind.value, unit=ind.unit or defn["unit"],
            direction=defn["direction"],
            source_type=ind.source_type, source_name=ind.source_name,
            source_geography=ind.source_geography, source_year=ind.source_year,
            is_proxy=ind.is_proxy, note=ind.note,
        ))

    # 写入原始汇总值(如果有)
    if any(v is not None for v in [body.area_hectare, body.yield_kg,
                                    body.gross_output_yuan, body.total_cost_yuan]):
        db.add(EconomicRawInput(
            site_id=site_id, evaluation_year=body.evaluation_year,
            scenario=body.scenario, crop_or_land_use=body.crop_or_land_use,
            area_hectare=body.area_hectare, yield_kg=body.yield_kg,
            gross_output_yuan=body.gross_output_yuan, total_cost_yuan=body.total_cost_yuan,
            source_type=body.indicators[0].source_type if body.indicators else "site_actual",
        ))

    db.commit()
    return {
        "success": True,
        "site_id": site_id,
        "year": body.evaluation_year,
        "indicators_saved": len(body.indicators),
        "economic_complete": len(body.indicators) == 8,
        "missing": [c for c in INDICATOR_DEFINITIONS if c not in ind_dict],
    }


@router.delete("/{site_id}/economic-data")
def delete_economic_data(site_id: int,
                         year: int | None = Query(None),
                         user: User = Depends(get_current_user),
                         db: Session = Depends(get_db)):
    """清除场地经济数据(可按年份)。"""
    _require_site(db, user, site_id)
    q1 = db.query(EconomicIndicator).filter_by(site_id=site_id)
    q2 = db.query(EconomicRawInput).filter_by(site_id=site_id)
    if year:
        q1 = q1.filter_by(evaluation_year=year)
        q2 = q2.filter_by(evaluation_year=year)
    n1, n2 = q1.delete(), q2.delete()
    db.commit()
    return {"success": True, "deleted_indicators": n1, "deleted_raw_inputs": n2}


@router.get("/{site_id}/economic-data/template")
def download_template(site_id: int,
                      user: User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    """下载 D18-D25 Excel 模板。"""
    _require_site(db, user, site_id)
    import io
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "SSUI经济指标"
    headers = ["评价年份", "场景", "作物/用地", "指标代码", "指标名称",
               "数值", "单位", "方向", "来源类型", "来源名称", "来源年份", "来源地域",
               "面积(公顷)", "总产量(kg)", "总产值(元)", "总成本(元)"]
    ws.append(headers)
    # 示例行
    for code, defn in INDICATOR_DEFINITIONS.items():
        ws.append([2024, "production", "水稻", code, defn["name"],
                   "", defn["unit"], defn["direction"], "site_actual",
                   "", "", "", "", "", "", ""])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=ssui_economic_template.xlsx"},
    )


@router.post("/{site_id}/economic-data/import")
async def import_economic_data(site_id: int,
                         user: User = Depends(get_current_user),
                         db: Session = Depends(get_db),
                         file: UploadFile = File(...)):
    """R3 审计第五类: Excel 导入 D18-D25 经济数据。

    模板列: 评价年份, 场景, 作物/用地, 指标代码, 指标名称,
            数值, 单位, 方向, 来源类型, 来源名称, 来源年份, 来源地域,
            面积(公顷), 总产量(kg), 总产值(元), 总成本(元)
    禁止: 未知字段自动映射成模板值。
    """
    content = await file.read()
    _require_site(db, user, site_id)
    import io
    import pandas as pd

    try:
        df = pd.read_excel(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(400, f"Excel 读取失败: {e}")

    # R3: 未知字段检查(禁止自动映射)
    valid_cols = {"评价年份", "场景", "作物/用地", "指标代码", "指标名称",
                  "数值", "单位", "方向", "来源类型", "来源名称",
                  "来源年份", "来源地域",
                  "面积(公顷)", "总产量(kg)", "总产值(元)", "总成本(元)"}
    actual_cols = set(df.columns)
    unknown = actual_cols - valid_cols
    if unknown:
        raise HTTPException(422, f"未知字段(禁止自动映射): {unknown}. 请使用模板下载的标准列名。")

    if "指标代码" not in df.columns or "数值" not in df.columns:
        raise HTTPException(422, "缺少必需列: 指标代码, 数值")

    # 解析行
    indicators = []
    raw_input_data = {"area_hectare": None, "yield_kg": None,
                      "gross_output_yuan": None, "total_cost_yuan": None}
    evaluation_year = None
    scenario = "production"
    crop = None

    for _, row in df.iterrows():
        code = str(row.get("指标代码", "")).strip()
        if not code or code == "nan":
            continue
        if code not in INDICATOR_DEFINITIONS:
            raise HTTPException(422, f"非法指标代码: {code}, 应为 D18-D25")

        val = row.get("数值")
        if pd.isna(val) or val is None:
            continue
        try:
            val = _validate_numeric(float(val), code)
        except ValueError as e:
            raise HTTPException(422, str(e))

        year_val = int(row.get("评价年份", 2024)) if not pd.isna(row.get("评价年份")) else 2024
        if evaluation_year is None:
            evaluation_year = year_val
        elif evaluation_year != year_val:
            raise HTTPException(422, f"年份不一致: {evaluation_year} vs {year_val}")

        scenario = str(row.get("场景", "production")) if not pd.isna(row.get("场景")) else "production"
        crop = str(row.get("作物/用地", "")) if not pd.isna(row.get("作物/用地")) else None

        indicators.append({
            "indicator_code": code,
            "value": val,
            "unit": str(row.get("单位", "")) if not pd.isna(row.get("单位")) else "",
            "source_type": str(row.get("来源类型", "site_actual")) if not pd.isna(row.get("来源类型")) else "site_actual",
            "source_name": str(row.get("来源名称", "")) if not pd.isna(row.get("来源名称")) else None,
            "source_year": int(row.get("来源年份")) if not pd.isna(row.get("来源年份")) else None,
            "source_geography": str(row.get("来源地域", "")) if not pd.isna(row.get("来源地域")) else None,
            "is_proxy": bool(row.get("来源类型") == "regional_official_proxy") if not pd.isna(row.get("来源类型")) else False,
        })

    # 从第一行提取原始汇总值
    first_row = df.iloc[0] if len(df) > 0 else {}
    for src_key, dst_key in [("面积(公顷)", "area_hectare"), ("总产量(kg)", "yield_kg"),
                              ("总产值(元)", "gross_output_yuan"), ("总成本(元)", "total_cost_yuan")]:
        v = first_row.get(src_key)
        if not pd.isna(v) and v is not None:
            raw_input_data[dst_key] = float(v)

    if not indicators:
        raise HTTPException(422, "未找到有效经济指标数据")

    # 复用 save 逻辑
    body = EconomicDataBody(
        evaluation_year=evaluation_year or 2024,
        scenario=scenario, crop_or_land_use=crop,
        indicators=[EconomicIndicatorInput(**ind) for ind in indicators],
        **raw_input_data,
    )
    return save_economic_data(site_id, body, user, db)
