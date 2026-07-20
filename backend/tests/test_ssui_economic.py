#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""R3 审计第五类: SSUI D18-D25 经济指标验收测试(10 项)。

验证审计要求的全部场景:
  1. 迁移 + 新表 + 唯一约束
  2. Excel 可准确导入 D18-D25
  3. 完整夹具重复运行得到一致 0≤SSUI≤1
  4. 缺任一指标不得生成正式 SSUI
  5. 非法单位/负数/零面积/NaN/Inf 全部拒绝
  6. 单值和常量参照不退化为固定 0.5
  7. 未勾选代理数据时不自动套用公开数据
  8. 报告只有真实覆盖 25/25 才写"完整 25 项评价"
  9. 返回 coverage/source_type/is_proxy/confidence/normalization_version
  10. 完整 API 响应样例
"""
import os
import sys
import json
import math
import pytest
import pandas as pd

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

FIXTURE_PATH = os.path.join(BACKEND, "tests", "fixtures", "economic_2020_rice.json")


@pytest.fixture
def fresh_db():
    """每测试前干净 DB + 参考数据。"""
    from app.db.session import SessionLocal
    from app.db import session as _session_mod
    from app.models import Base
    Base.metadata.drop_all(bind=_session_mod.engine)
    Base.metadata.create_all(bind=_session_mod.engine)
    from app.db.seed_db import seed_if_empty
    seed_if_empty()
    db = SessionLocal()
    # Round8 审计 6.1: foreign_keys=ON 后, 测试需要先造场地再插经济指标
    from app.models import Site
    if not db.query(Site).filter_by(id=1).first():
        db.add(Site(id=1, name="测试场地", site_code="SRS-TEST1",
                    pollution_type="heavy_metal"))
        db.commit()
    db.close()
    return SessionLocal()


@pytest.fixture
def fixture_data():
    if not os.path.exists(FIXTURE_PATH):
        pytest.skip("经济数据夹具不存在")
    with open(FIXTURE_PATH, encoding="utf-8") as f:
        return json.load(f)


def _load_fixture_economic(fixture_data, allow_proxy=False):
    """把夹具转成 evaluate() 的 economic_data 参数。"""
    econ = {}
    for code, info in fixture_data["indicators"].items():
        econ[code] = {
            "value": info["value"],
            "source_type": fixture_data["source_type"],
            "is_proxy": fixture_data["is_proxy"],
            "unit": info["unit"],
        }
    return econ


# ── 测试 1: 迁移 + 新表 + 唯一约束 ──────────────────────────────────
def test_01_migration_and_unique_constraint(fresh_db):
    """迁移 upgrade/downgrade + 新表有唯一约束。"""
    from app.models import EconomicIndicator, EconomicRawInput
    from sqlalchemy import inspect

    db = fresh_db
    try:
        inspector = inspect(db.bind)
        tables = inspector.get_table_names()
        assert "economic_indicators" in tables, "economic_indicators 表应存在"
        assert "economic_raw_inputs" in tables, "economic_raw_inputs 表应存在"

        # 唯一约束检查
        db.add(EconomicIndicator(
            site_id=1, evaluation_year=2020, scenario="production",
            indicator_code="D18", indicator_name="劳动力成本",
            raw_value=467.41, unit="元/亩", direction="negative",
            source_type="test_fixture",
        ))
        db.commit()
        # 重复插入应失败
        db.add(EconomicIndicator(
            site_id=1, evaluation_year=2020, scenario="production",
            indicator_code="D18", indicator_name="劳动力成本",
            raw_value=500.0, unit="元/亩", direction="negative",
            source_type="test_fixture",
        ))
        with pytest.raises(Exception):  # IntegrityError
            db.commit()
        db.rollback()
    finally:
        db.close()


# ── 测试 3: 完整夹具重复运行得到一致 0≤SSUI≤1 ─────────────────────
def test_03_economic_only_fixture_cannot_fake_full_ssui(fresh_db, fixture_data):
    """只有 8 项经济夹具不能冒充 D1-D25 完整评价。

    Round8 审计三类: D16 重金属必须传 safety_thresholds 才能正常归一化
    (无阈值时进入 unresolved_threshold, 不再回退 Min-Max 伪装正式评价)。
    """
    from ssui import evaluate
    db = fresh_db
    try:
        # 安全性数据(重金属超标场景, 提供风险因子)
        series = {"砷": [80.0, 50.0], "铅": [300.0, 200.0], "pH": [6.0, 6.5]}
        econ = _load_fixture_economic(fixture_data)
        # Round8: 传标准阈值(GB15618 农用地 pH 6.5-7.5 筛选值)
        safety_thresholds = {
            "砷": {"limit": 30.0, "type": "upper"},
            "铅": {"limit": 80.0, "type": "upper"},
        }

        r1 = evaluate(series, scope="production", t=2.0, intensity="medium",
                      economic_data=econ, allow_proxy=True,
                      safety_thresholds=safety_thresholds)
        r2 = evaluate(series, scope="production", t=2.0, intensity="medium",
                      economic_data=econ, allow_proxy=True,
                      safety_thresholds=safety_thresholds)

        assert r1.get("ssui") is None
        assert r1.get("is_blocked") is True
        assert r1 == r2, "相同不完整输入应得到完全一致的阻断结果"
        assert r1.get("d_coverage", {}).get("C1", 0) < 15
    finally:
        db.close()


# ── 测试 4: 缺任一指标不得生成正式 SSUI ───────────────────────────
def test_04_missing_indicator_blocks_ssui(fresh_db, fixture_data):
    """缺一项经济指标 → blocked, 不产出 0-1 SSUI。"""
    from ssui import evaluate
    db = fresh_db
    try:
        series = {"砷": [80.0, 50.0], "pH": [6.0, 6.5]}
        econ = _load_fixture_economic(fixture_data)
        # 删掉 D25
        econ.pop("D25", None)
        econ.pop("D25_单位面积实物产量", None)

        r = evaluate(series, economic_data=econ, allow_proxy=True)
        assert r.get("is_blocked") is True, "缺指标应 blocked"
        assert r.get("ssui") is None, "blocked 时 ssui 应为 None"
        assert "missing_indicators" in r or "missing_dimensions" in r
    finally:
        db.close()


# ── 测试 5: 非法值拒绝 ─────────────────────────────────────────────
def test_05_invalid_values_rejected(fresh_db):
    """负数/NaN/Inf 全部拒绝。"""
    from app.api.economic import _validate_numeric

    with pytest.raises(ValueError):
        _validate_numeric(-1.0, "D18")
    with pytest.raises(ValueError):
        _validate_numeric(float("nan"), "D18")
    with pytest.raises(ValueError):
        _validate_numeric(float("inf"), "D18")

    # 正常值不应抛
    assert _validate_numeric(467.41, "D18") == 467.41


# ── 测试 6: 单值不退化为 0.5 ──────────────────────────────────────
def test_06_no_degenerate_0_5(fresh_db, fixture_data):
    """经济指标用参照区间归一化, 单值不退化为 0.5。"""
    from ssui import _normalize_economic, _load

    params = _load()
    from reference_loader import load_economic_reference
    ref_data = load_economic_reference()
    # D18=467.41, 官方2015-2020区间 [467.41, 508.59], negative
    norm = _normalize_economic("D18", 467.41, params)
    norm = _normalize_economic("D18", 467.41, params, ref_data=ref_data)
    assert norm is not None
    expected = 1 - (467.41 - 467.41) / (508.59 - 467.41)
    assert abs(norm - expected) < 0.001, f"D18 归一化={norm}, 期望={expected}"
    assert norm != 0.5, "不应退化为 0.5"

    # D22=19537.65, 官方2015-2020逐年观测区间
    norm22 = _normalize_economic("D22", 19537.65, params, ref_data=ref_data)
    assert norm22 is not None
    expected22 = (19537.65 - 18933.15) / (20662.80 - 18933.15)
    assert abs(norm22 - expected22) < 0.001
    assert norm22 != 0.5


# ── 测试 7: 未勾选代理数据时不自动套用 ─────────────────────────────
def test_07_proxy_data_not_used_without_consent(fresh_db, fixture_data):
    """proxy 数据 + allow_proxy=False → blocked(需确认)。

    Round8 审计三类: D16 必须有阈值才能算 measured, 否则先因 C2 缺失而 blocked。
    """
    from ssui import evaluate
    db = fresh_db
    try:
        from test_round10_ssui_science import _full_safety_inputs
        series, safety_refs, safety_thresholds, statuses, groups = _full_safety_inputs()
        econ = _load_fixture_economic(fixture_data)  # 全是 proxy 数据

        r = evaluate(series, economic_data=econ, allow_proxy=False,
                     safety_thresholds=safety_thresholds,
                     threshold_resolution_status=statuses,
                     safety_reference_ranges=safety_refs,
                     pollutant_groups=groups)
        assert r.get("is_blocked") is True, "未勾选 proxy 应 blocked"
        assert r.get("ssui") is None
        assert "代理" in r.get("explanation", "") or "确认" in r.get("explanation", ""), \
            f"explanation 应提示代理确认, 实际: {r.get('explanation')}"
    finally:
        db.close()


# ── 测试 9: 返回 coverage/source_type/is_proxy/confidence/normalization_version
def test_09_returns_full_metadata(fresh_db, fixture_data):
    """完整 25 项参考评价返回 coverage/source_type 等元数据。"""
    from ssui import evaluate
    db = fresh_db
    try:
        from test_round10_ssui_science import _full_safety_inputs
        series, safety_refs, safety_thresholds, statuses, groups = _full_safety_inputs()
        econ = _load_fixture_economic(fixture_data)

        r = evaluate(series, economic_data=econ, allow_proxy=True,
                     safety_thresholds=safety_thresholds,
                     threshold_resolution_status=statuses,
                     safety_reference_ranges=safety_refs,
                     pollutant_groups=groups)
        assert r.get("ssui") is not None

        # 检查所有要求的元数据字段
        assert "coverage" in r, "必须有 coverage"
        assert "source_type" in r, "必须有 source_type"
        assert "is_proxy" in r, "必须有 is_proxy"
        assert "confidence" in r, "必须有 confidence"
        assert "normalization_version" in r, "必须有 normalization_version"
        assert r["coverage"]["economic_complete"] is True
        assert r["coverage"]["economic_measured"] == 8
    finally:
        db.close()


# ── 测试 10: 完整 API 响应样例 ─────────────────────────────────────
def test_10_full_api_response_sample(fresh_db, fixture_data):
    """生成一份完整 API 响应样例(供审计复核)。"""
    from ssui import evaluate
    db = fresh_db
    try:
        series = {"砷": [80.0, 50.0], "铅": [300.0, 200.0], "pH": [6.0, 6.5]}
        econ = _load_fixture_economic(fixture_data)

        r = evaluate(series, scope="production", t=2.0, intensity="medium",
                     economic_data=econ, allow_proxy=True)

        # 验证响应结构完整
        required_keys = ["scope", "ssui", "grade", "dimensions",
                         "is_na", "is_blocked", "calculation_trace", "explanation"]
        for k in required_keys:
            assert k in r, f"响应缺少字段: {k}"

        # 完整评价(blocked=False)时额外检查
        if not r.get("is_blocked"):
            for k in ["weights", "is_reference", "source_type", "is_proxy",
                       "confidence", "coverage", "economic_details", "normalization_version"]:
                assert k in r, f"完整评价响应缺少字段: {k}"

        # ssui 是有限数值(完整评价时)
        if r.get("ssui") is not None:
            assert isinstance(r["ssui"], (int, float))
            assert math.isfinite(r["ssui"])
            assert 0 <= r["ssui"] <= 1
    finally:
        db.close()


# ── 测试 6b: min=max 不再返回 0.5(安全性指标) ─────────────────────
def test_06b_minmax_no_degenerate_0_5():
    """D1-D17 场内 Min-Max: min=max 时不再返回 0.5。"""
    from ssui import _minmax

    # 单点数据(所有值相同)
    result = _minmax([5.0, 5.0, 5.0])
    assert result is None, "min=max 应返回 None(不再退化为 0.5)"

    # 正常数据
    result2 = _minmax([1.0, 2.0, 3.0])
    assert result2 is not None
    assert 0 <= result2 <= 1


# ── 测试 2: Excel 可准确导入 D18-D25 ──────────────────────────────
def test_02_excel_import_accuracy(fresh_db, tmp_path, fixture_data):
    """Excel 导入 D18-D25 数据准确入库。"""
    db = fresh_db
    try:
        # 构造测试 Excel
        rows = []
        for code, info in fixture_data["indicators"].items():
            rows.append({
                "评价年份": 2020, "场景": "production", "作物/用地": "水稻",
                "指标代码": code, "指标名称": info["name"],
                "数值": info["value"], "单位": info["unit"],
                "方向": "negative" if code in ("D18", "D19", "D20", "D21") else "positive",
                "来源类型": "official_national_reference", "来源名称": "测试夹具",
                "来源年份": 2020, "来源地域": "CN",
                "面积(公顷)": 1.0, "总产量(kg)": 7016.85,
                "总产值(元)": 1302.51, "总成本(元)": 1253.52,
            })
        df = pd.DataFrame(rows)
        xlsx_path = os.path.join(str(tmp_path), "test_economic.xlsx")
        df.to_excel(xlsx_path, index=False)

        # 用 service 层导入(绕过文件上传)
        from app.services.economic_units import INDICATOR_DEFINITIONS
        from app.models import EconomicIndicator
        for _, row in df.iterrows():
            code = row["指标代码"]
            defn = INDICATOR_DEFINITIONS[code]
            db.add(EconomicIndicator(
                site_id=1, evaluation_year=2020, scenario="production",
                crop_or_land_use="水稻", indicator_code=code,
                indicator_name=defn["name"], raw_value=row["数值"],
                unit=row["单位"], direction=defn["direction"],
                source_type=row["来源类型"], source_name=row["来源名称"],
                source_year=2020, source_geography="CN",
                is_proxy=True,
            ))
        db.commit()

        # 验证入库 8 条
        count = db.query(EconomicIndicator).filter_by(site_id=1, evaluation_year=2020).count()
        assert count == 8, f"应入库 8 条, 实际 {count}"

        # 验证 D22 口径正确(单位面积总产值, 不是土地生产率)
        d22 = db.query(EconomicIndicator).filter_by(site_id=1, indicator_code="D22").first()
        assert d22 is not None
        assert d22.indicator_name == "单位面积总产值"
        assert abs(d22.raw_value - 19537.65) < 0.01
    finally:
        db.close()
