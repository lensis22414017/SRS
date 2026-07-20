"""数据版本与幂等工具: source_sha256 / mapping_hash / 场地数据版本(brief 4.2)。

设计:
- source_sha256: 源文件内容指纹, 幂等判重的核心键(取代含时间戳的 source_file)。
- mapping_hash: 映射配置指纹, 同文件不同映射视为不同批次。
- current_site_data_version: 基于最新批次 sha256 + measurement 计数, 替换旧的
  site{id}_n{count} 假指纹——后者只含点数, 内容变但点数不变时版本不变, stale 检测失效。
"""
from __future__ import annotations

import hashlib
import json

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import ImportBatch, Measurement, EconomicIndicator, EconomicRawInput


def _eval_params_sha256() -> str:
    """Round8 审计二类 2.3: 计算 evaluation_params.json 真实 SHA-256(不只是版本号)。

    参数文件 mtime/内容任一变化 → sha256 变化 → 旧 SSUI 自动 stale。
    文件不存在时返回 "missing"(标记为待校验, 禁止复用)。
    """
    import hashlib as _hl
    import os as _os
    # evaluation_params.json 在 SRS 根/ml/params/
    # __file__ = backend/app/services/versioning.py → 3 级 dirname 到 SRS 根
    _here = _os.path.dirname(_os.path.abspath(__file__))
    _PARAMS_PATH = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.dirname(
        _here))), "ml", "params", "evaluation_params.json")
    try:
        if not _os.path.exists(_PARAMS_PATH):
            return "missing"
        h = _hl.sha256()
        with open(_PARAMS_PATH, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()[:16]
    except OSError:
        return "unreadable"


def _economic_ref_csv_sha256() -> str:
    """Round9 P0-1: 经济参照集 CSV 的 SHA-256。

    CSV 在 data/standards/ssui_economic_reference_v1.csv; 文件变化 → 指纹变化 → stale。
    文件不存在返回 "missing"; 不可读返回 "unreadable"。
    """
    import hashlib as _hl
    import os as _os
    _here = _os.path.dirname(_os.path.abspath(__file__))
    # backend/app/services/ → SRS 根是 3 级 dirname
    _root = _os.path.dirname(_os.path.dirname(_os.path.dirname(_here)))
    _CSV = _os.path.join(_root, "data", "standards", "ssui_economic_reference_v1.csv")
    try:
        if not _os.path.exists(_CSV):
            return "missing"
        h = _hl.sha256()
        with open(_CSV, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()[:16]
    except OSError:
        return "unreadable"


def _threshold_set_hash(db: Session) -> str:
    """Round9 P0-1.1: 阈值数据集哈希(扩展字段)。

    基于 standard_thresholds 表的完整内容(standard_code/factor_name/screening_value/version
    + pH_condition/land_use_type/unit/exposure_scenario + 派生 track)生成稳定哈希。
    排序必须稳定(按所有字段排序), 不依赖数据库 id 自然顺序。
    """
    import hashlib as _hl
    try:
        from app.models import StandardThreshold
        rows = (db.query(StandardThreshold.standard_code, StandardThreshold.factor_name,
                          StandardThreshold.screening_value, StandardThreshold.version,
                          StandardThreshold.pH_condition, StandardThreshold.land_use_type,
                          StandardThreshold.unit, StandardThreshold.exposure_scenario)
                .all())
        if not rows:
            return "no_thr"
        def _track(std_code: str) -> str:
            sc = (std_code or "").upper().replace(" ", "")
            if "GB15618" in sc:
                return "prod"
            if "GB36600" in sc:
                return "eco"
            return "unknown"
        items = []
        for r in rows:
            items.append({
                "std": r.standard_code or "",
                "fac": r.factor_name or "",
                "sv": float(r.screening_value) if r.screening_value is not None else None,
                "ver": str(r.version or ""),
                "ph": r.pH_condition or "",
                "lu": r.land_use_type or "",
                "u": r.unit or "",
                "es": r.exposure_scenario or "",
                "track": _track(r.standard_code or ""),
            })
        # 显式排序(稳定), 不依赖 DB id
        items.sort(key=lambda x: (x["std"], x["fac"], x["ph"], x["lu"],
                                    str(x["sv"]), x["ver"], x["u"], x["es"]))
        content = json.dumps(items, sort_keys=True, ensure_ascii=False)
        return _hl.sha256(content.encode("utf-8")).hexdigest()[:12]
    except Exception:
        return "thr_err"


def evaluation_input_fingerprint(db: Session, site_id: int,
                                  evaluation_year: int | None = None,
                                  scenario: str = "production",
                                  scope: str = "production",
                                  t: float = 2.0, intensity: str = "medium",
                                  allow_proxy: bool = False,
                                  param_version: str = "") -> str:
    """Round9 P0-1: 评价输入指纹(显式包含所有字面值, 供 GET stale 重算)。

    审计 P0-1.4: input_fingerprint 必须显式包含:
      - site_id / measurement_data_version
      - evaluation_year 字面值(非 None)
      - scenario 字面值
      - scope / t / intensity / allow_proxy
      - 指定年+指定场景 D18-D25 经济指标内容哈希
      - EconomicRawInput 内容哈希
      - evaluation_params.json 完整 SHA-256
      - 经济参照 CSV SHA-256
      - 阈值数据集完整哈希(含 pH_condition/land_use_type/unit/exposure_scenario/track)
    """
    import hashlib as _hl
    # 1. 检测数据版本
    meas_version = current_site_data_version(db, site_id)
    # 2. 经济指标内容哈希(锁定 year+scenario)
    econ_q = db.query(EconomicIndicator).filter_by(site_id=site_id, scenario=scenario)
    if evaluation_year is not None:
        econ_q = econ_q.filter_by(evaluation_year=evaluation_year)
    econ_rows = econ_q.order_by(
        EconomicIndicator.indicator_code, EconomicIndicator.updated_at.desc()).all()
    econ_content = json.dumps([{
        "code": r.indicator_code, "value": r.raw_value, "unit": r.unit,
        "source_type": r.source_type, "is_proxy": r.is_proxy,
        "updated_at": str(r.updated_at or r.created_at),
    } for r in econ_rows], sort_keys=True, ensure_ascii=False)
    econ_hash = _hl.sha256(econ_content.encode("utf-8")).hexdigest()[:12] if econ_rows else "no_econ"
    # 3. 原始汇总值哈希
    raw_q = db.query(EconomicRawInput).filter_by(site_id=site_id, scenario=scenario)
    if evaluation_year is not None:
        raw_q = raw_q.filter_by(evaluation_year=evaluation_year)
    raw_rows = raw_q.all()
    raw_content = json.dumps([{
        "area": r.area_hectare, "yield": r.yield_kg,
        "gross_output": r.gross_output_yuan, "total_cost": r.total_cost_yuan,
    } for r in raw_rows], sort_keys=True, ensure_ascii=False)
    raw_hash = _hl.sha256(raw_content.encode("utf-8")).hexdigest()[:8] if raw_rows else "no_raw"
    # Round9 P0-1: 参数 SHA + 阈值集哈希 + 经济参照 CSV SHA
    params_sha = _eval_params_sha256()
    csv_sha = _economic_ref_csv_sha256()
    thr_hash = _threshold_set_hash(db)
    # 4. 组合指纹 — Round9 P0-1: 显式包含 evaluation_year/scenario 字面值
    fp_str = (f"site={site_id}|meas={meas_version}|"
              f"year={evaluation_year}|scn={scenario}|scope={scope}|"
              f"t={t}|intensity={intensity}|proxy={allow_proxy}|"
              f"econ={econ_hash}|raw={raw_hash}|"
              f"pv={param_version}|psha={params_sha}|csv={csv_sha}|thr={thr_hash}")
    return _hl.sha256(fp_str.encode("utf-8")).hexdigest()[:20]


def compute_source_sha256(path: str) -> str:
    """文件内容 sha256(分块读取, 支持大文件)。"""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def compute_mapping_hash(mapping: dict) -> str:
    """映射配置 sha256(稳定序列化, 只哈希决定数据形态的字段)。"""
    site = mapping.get("site") or {}
    key_fields = {
        "sheet": mapping.get("sheet"),
        "header_row": mapping.get("header_row"),
        "point_columns": mapping.get("point_columns"),
        "factor_columns": mapping.get("factor_columns"),
        # v1.0.2(GPT 3a): 排除 site_code — smart_detect 每次生成唯一 site_code(时间戳+随机),
        # 但 site_code 不影响"数据形态"; 同文件同结构重导应幂等去重, 不因 site_code 不同而判异
        "site": {k: site.get(k) for k in ("pollution_type", "land_use_type")},
    }
    return hashlib.sha256(
        json.dumps(key_fields, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()[:16]


def batch_data_version(source_sha256: str | None, n_measurements: int, site_id: int) -> str:
    """单批次数据版本字符串。"""
    if source_sha256:
        return f"{source_sha256[:12]}_n{n_measurements}"
    return f"site{site_id}_n{n_measurements}"


def current_site_data_version(db: Session, site_id: int) -> str:
    """场地当前数据版本: 基于最新导入批次的 source_sha256 + measurement 计数。

    brief 4.2 / D2: 诊断/评价/推荐/报告统一用此版本判断 stale。
    """
    batch = (db.query(ImportBatch).filter_by(site_id=site_id)
             .order_by(ImportBatch.id.desc()).first())
    n_meas = db.query(func.count(Measurement.id)).filter_by(site_id=site_id).scalar() or 0
    if batch and batch.source_sha256:
        return f"{batch.source_sha256[:12]}_n{n_meas}"
    return f"site{site_id}_n{n_meas}"
