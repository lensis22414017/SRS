"""SSUI D1-D15 安全参照范围加载与审计。

为 D1-D15 土壤理化性质提供外部参照归一化所需的 {min, max, direction} 范围。
从 data/standards/ssui_safety_reference_v1.csv 加载, 含完整校验与审计追溯。
仿 reference_loader.py 结构, 但面向 D1-D15(安全限制因子)而非 D18-D25(经济指标)。
"""
from __future__ import annotations

import csv
import hashlib
import math
import os
from collections import Counter

EXPECTED_COLUMNS = {
    "d_code", "factor_code", "min", "max", "unit", "direction",
    "source_standard", "source_document", "derivation", "evidence_level",
}


def _default_csv_path() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(os.path.dirname(here))
    return os.path.join(root, "data", "standards", "ssui_safety_reference_v1.csv")


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _empty(status: str, errors: list[str] | None = None) -> dict:
    return {
        "valid": False, "status": status, "errors": errors or [],
        "version": "missing", "sha256": status, "factor_count": 0,
        "ranges": {}, "evidence_distribution": {"A": 0, "B": 0, "C": 0},
        "quality": "unavailable", "unavailable_d_codes": [],
    }


def load_safety_reference(csv_path: str | None = None, *,
                          scope: str = "production") -> dict:
    """加载 D1-D15 安全参照范围。

    Args:
        csv_path: CSV 路径, None 用默认路径
        scope: "production" 或 "ecology"(当前使用同一套物理参照, 后续可按 scope 拆分)

    Returns:
        {
            valid: bool, status: str, errors: [str],
            version: str, sha256: str, factor_count: int,
            ranges: {factor_code: {min, max, direction, unit, source_standard,
                                    source_document, derivation, evidence_level,
                                    d_code}},
            evidence_distribution: {A: N, B: N, C: N},
            quality: "full" | "limited" | "unavailable",
            unavailable_d_codes: [str],
        }
    """
    path = csv_path or _default_csv_path()
    if not os.path.exists(path):
        return _empty("missing", [f"文件不存在: {path}"])

    errors: list[str] = []
    ranges: dict[str, dict] = {}
    evidence_dist: dict[str, int] = {"A": 0, "B": 0, "C": 0}
    d_codes_seen: set[str] = set()
    factor_codes_seen: list[str] = []

    try:
        sha = _sha256_file(path)
        with open(path, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            columns = set(reader.fieldnames or [])
            if not EXPECTED_COLUMNS.issubset(columns):
                missing = sorted(EXPECTED_COLUMNS - columns)
                return _empty("invalid_schema", [f"缺少列: {', '.join(missing)}"])

            for row_number, row in enumerate(reader, start=2):
                d_code = (row.get("d_code") or "").strip()
                factor_code = (row.get("factor_code") or "").strip()

                if not d_code or not factor_code:
                    errors.append(f"第{row_number}行 d_code/factor_code 为空")
                    continue
                if not d_code.startswith("D"):
                    errors.append(f"第{row_number}行 d_code 格式错误: {d_code}")
                    continue

                # 校验数值字段
                try:
                    min_val = float((row.get("min") or "").strip())
                    max_val = float((row.get("max") or "").strip())
                except ValueError:
                    errors.append(f"第{row_number}行 min/max 不是有效数值")
                    continue
                if not math.isfinite(min_val) or not math.isfinite(max_val):
                    errors.append(f"第{row_number}行 min/max 必须为有限数")
                    continue
                if min_val >= max_val:
                    errors.append(f"第{row_number}行 min({min_val}) >= max({max_val})")
                    continue

                direction = (row.get("direction") or "").strip()
                if direction not in ("positive", "negative"):
                    errors.append(f"第{row_number}行 direction 必须为 positive/negative")
                    continue

                evidence_level = (row.get("evidence_level") or "").strip().upper()
                if evidence_level not in ("A", "B", "C"):
                    errors.append(f"第{row_number}行 evidence_level 必须为 A/B/C")
                    continue

                source_standard = (row.get("source_standard") or "").strip()
                source_document = (row.get("source_document") or "").strip()
                derivation = (row.get("derivation") or "").strip()
                if not source_standard or not source_document or not derivation:
                    errors.append(f"第{row_number}行来源信息不完整")
                    continue

                unit = (row.get("unit") or "").strip()

                # 同一 factor_code 出现多次(如别名) → 用第一个
                if factor_code in ranges:
                    continue

                ranges[factor_code] = {
                    "min": min_val, "max": max_val, "unit": unit,
                    "direction": direction, "source_standard": source_standard,
                    "source_document": source_document, "derivation": derivation,
                    "evidence_level": evidence_level, "d_code": d_code,
                }
                evidence_dist[evidence_level] += 1
                d_codes_seen.add(d_code)
                factor_codes_seen.append(factor_code)

    except (OSError, UnicodeError, csv.Error) as exc:
        return _empty("unreadable", [str(exc)])

    # 质量判定
    total = sum(evidence_dist.values())
    if total == 0:
        return _empty("no_data", errors or ["CSV 无有效行"])

    c_ratio = evidence_dist["C"] / total if total > 0 else 0
    quality = "limited" if c_ratio > 0.30 else "full"

    # 收集无参照的 D 代码(从 D_TO_FACTORS 交叉比对)
    # 只需检查 D1-D15 中哪些在 ranges 中没有对应 factor
    from ml.evaluation.ssui import D_TO_FACTORS  # noqa: E402 (cyclic ok in loader)
    unavailable_d_codes = []
    for d_code in sorted(D_TO_FACTORS):
        if any(d_code.startswith(p) for p in (f"D{i}_" for i in range(1, 16))):
            has_any = any(fc in ranges for fc in D_TO_FACTORS[d_code])
            if not has_any:
                unavailable_d_codes.append(d_code)

    valid = len(errors) == 0 and total > 0
    return {
        "valid": valid, "status": "ok" if valid else "invalid",
        "errors": errors, "version": "v1.0", "sha256": sha[:16],
        "factor_count": total,
        "ranges": ranges if valid else {},
        "evidence_distribution": evidence_dist,
        "quality": quality,
        "unavailable_d_codes": unavailable_d_codes,
        "d_codes_covered": sorted(d_codes_seen),
        "factor_codes": factor_codes_seen,
    }
