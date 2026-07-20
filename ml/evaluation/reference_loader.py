"""SSUI 经济参照样本加载与审计。

生产参照文件保存逐年官方观测值；上下界由代码从同一 scope/crop/region 的
多年度样本计算，禁止在 CSV 中手填不可复算的 min/max。
"""
from __future__ import annotations

import csv
import hashlib
import math
import os
from collections import Counter, defaultdict
from urllib.parse import urlparse

EXPECTED_CODES = tuple(f"D{i}" for i in range(18, 26))
EXPECTED_UNITS = {
    "D18": "元/亩·年", "D19": "元/亩·年", "D20": "元/亩·年", "D21": "元/亩·年",
    "D22": "元/公顷·年", "D23": "无量纲", "D24": "元/人·年", "D25": "kg/公顷·年",
}
EXPECTED_DIRECTIONS = {code: ("negative" if code in {"D18", "D19", "D20", "D21"} else "positive")
                       for code in EXPECTED_CODES}
REQUIRED_COLUMNS = {
    "indicator_code", "indicator_name", "scope", "crop", "region", "year", "unit", "value",
    "direction", "source_name", "source_url", "source_document", "table_or_page", "is_proxy",
    "version", "effective_date", "derivation",
}


def _default_csv_path() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(os.path.dirname(here))
    return os.path.join(root, "data", "standards", "ssui_economic_reference_v1.csv")


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _empty(status: str, errors: list[str] | None = None) -> dict:
    return {
        "valid": False, "status": status, "errors": errors or [], "version": status,
        "source": "", "source_url": "", "sha256": status, "sample_count": 0,
        "year_range": None, "ranges": {}, "observations": [],
    }


def _is_auditable_text(value: str) -> bool:
    cleaned = value.strip()
    return bool(cleaned) and "待核查" not in cleaned and "unknown" not in cleaned.lower()


def load_economic_reference(csv_path: str | None = None, *, scope: str = "production",
                            crop: str = "rice", region: str = "CN",
                            minimum_samples: int = 2) -> dict:
    """加载匹配场景的官方观测并计算 D18-D25 参照范围。

    任一指标样本不足、单位/方向冲突、来源不可核查或上下界退化时，整个参照集
    ``valid=False``。调用方必须阻断 proxy/正式 SSUI，不得回退 JSON 常数。
    """
    path = csv_path or _default_csv_path()
    if not os.path.exists(path):
        return _empty("missing")
    try:
        sha = _sha256_file(path)
        with open(path, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            columns = set(reader.fieldnames or [])
            if not REQUIRED_COLUMNS.issubset(columns):
                missing = sorted(REQUIRED_COLUMNS - columns)
                return _empty("invalid_schema", [f"缺少列: {', '.join(missing)}"])
            rows = list(reader)
    except (OSError, UnicodeError, csv.Error) as exc:
        return _empty("unreadable", [str(exc)])

    errors: list[str] = []
    observations: list[dict] = []
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row_number, row in enumerate(rows, start=2):
        if (row.get("scope") or "").strip() != scope or (row.get("crop") or "").strip() != crop \
                or (row.get("region") or "").strip() != region:
            continue
        code = (row.get("indicator_code") or "").strip()
        if code not in EXPECTED_CODES:
            errors.append(f"第{row_number}行指标代码非法: {code}")
            continue
        try:
            year = int((row.get("year") or "").strip())
            value = float((row.get("value") or "").strip())
        except ValueError:
            errors.append(f"第{row_number}行年份或数值非法")
            continue
        if not math.isfinite(value) or value < 0:
            errors.append(f"第{row_number}行数值必须为非负有限数")
            continue
        unit = (row.get("unit") or "").strip()
        direction = (row.get("direction") or "").strip()
        if unit != EXPECTED_UNITS[code]:
            errors.append(f"第{row_number}行{code}单位应为{EXPECTED_UNITS[code]}，实际为{unit}")
        if direction != EXPECTED_DIRECTIONS[code]:
            errors.append(f"第{row_number}行{code}方向应为{EXPECTED_DIRECTIONS[code]}")
        url = (row.get("source_url") or "").strip()
        if urlparse(url).scheme != "https" or not urlparse(url).netloc:
            errors.append(f"第{row_number}行来源URL不可核查")
        for field in ("source_name", "source_document", "table_or_page", "derivation", "version"):
            if not _is_auditable_text(row.get(field) or ""):
                errors.append(f"第{row_number}行{field}缺少可核查内容")
        observation = {
            "indicator_code": code, "indicator_name": (row.get("indicator_name") or "").strip(),
            "scope": scope, "crop": crop, "region": region, "year": year, "unit": unit,
            "value": value, "direction": direction, "source_name": (row.get("source_name") or "").strip(),
            "source_url": url, "source_document": (row.get("source_document") or "").strip(),
            "table_or_page": (row.get("table_or_page") or "").strip(),
            "derivation": (row.get("derivation") or "").strip(),
            "version": (row.get("version") or "").strip(), "is_proxy": True,
        }
        observations.append(observation)
        grouped[code].append(observation)

    ranges: dict[str, dict] = {}
    for code in EXPECTED_CODES:
        samples = grouped.get(code, [])
        unique_years = {sample["year"] for sample in samples}
        if len(samples) < minimum_samples or len(unique_years) < minimum_samples:
            errors.append(f"{code}参照样本不足{minimum_samples}个独立年份")
            continue
        values = [sample["value"] for sample in samples]
        lo, hi = min(values), max(values)
        if hi <= lo:
            errors.append(f"{code}参照范围退化")
            continue
        exemplar = samples[0]
        ranges[code] = {
            "min": lo, "max": hi, "unit": exemplar["unit"], "direction": exemplar["direction"],
            "description": exemplar["indicator_name"], "sample_count": len(samples),
            "years": sorted(unique_years), "source_name": exemplar["source_name"],
            "source_url": exemplar["source_url"], "is_proxy": True,
        }

    versions = [row["version"] for row in observations if row["version"]]
    sources = [row["source_name"] for row in observations if row["source_name"]]
    urls = [row["source_url"] for row in observations if row["source_url"]]
    years = [row["year"] for row in observations]
    valid = not errors and set(ranges) == set(EXPECTED_CODES)
    return {
        "valid": valid, "status": "ok" if valid else "invalid", "errors": errors,
        "version": Counter(versions).most_common(1)[0][0] if versions else "missing",
        "source": Counter(sources).most_common(1)[0][0] if sources else "",
        "source_url": Counter(urls).most_common(1)[0][0] if urls else "",
        "sha256": sha, "sample_count": len(observations),
        "year_range": [min(years), max(years)] if years else None,
        "ranges": ranges if valid else {}, "observations": observations,
    }
