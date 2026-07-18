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


def evaluation_input_fingerprint(db: Session, site_id: int,
                                  evaluation_year: int | None = None,
                                  scenario: str = "production",
                                  scope: str = "production",
                                  t: float = 2.0, intensity: str = "medium",
                                  allow_proxy: bool = False,
                                  param_version: str = "") -> str:
    """R3-P0-3: 评价输入指纹(用于 SSUI 缓存复用判断)。

    包含:
      - measurement_data_version(检测数据版本)
      - D18-D25 经济数据内容哈希(锁定 year+scenario)
      - 原始经济汇总值哈希
      - scope/t/intensity/allow_proxy(评价参数)
      - param_version(参数文件版本)

    只有指纹完全相同才允许复用旧 SSUI 结果。
    经济数据增删改后指纹变化 → 旧 SSUI 自动 stale。
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
    # 4. 组合指纹
    fp_str = f"{meas_version}|econ={econ_hash}|raw={raw_hash}|{scope}|t={t}|{intensity}|proxy={allow_proxy}|pv={param_version}"
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
