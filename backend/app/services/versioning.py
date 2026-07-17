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

from app.models import ImportBatch, Measurement


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
