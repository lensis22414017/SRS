"""Round9 P0-6: SSUI 经济参照集 CSV 加载器。

替代 evaluation_params.json 中的 economic_reference_ranges 节点(后者手填 min/max
不可核查出处;CSV 化后每条参照值必须含 source_name/source_url/source_document/table_or_page,
方便审计追溯)。

设计:
- load_economic_reference(csv_path=None) → {
      "version": "v1",                      # CSV 内 version 列的众数
      "source": "<source_name 众数>",
      "source_url": "<source_url 众数>",
      "sha256": "<前 16 位>",                # 整个 CSV 内容 SHA-256, 用于指纹
      "ranges": {
          "D18": {"min":..., "max":..., "unit":..., "direction":...,
                  "description":..., "source_name":..., "source_url":...,
                  "source_document":..., "table_or_page":..., "is_proxy":...},
          ...
      }
  }
- 文件缺失返回 sha256="missing", ranges={} — 上游(SSUI/指纹)按 missing 处理 stale
"""
from __future__ import annotations

import csv
import hashlib
import os


def _default_csv_path() -> str:
    """data/standards/ssui_economic_reference_v1.csv。

    reference_loader.py 在 SRS/ml/evaluation/, 上溯 2 级 dirname 到 SRS 根。
    """
    _here = os.path.dirname(os.path.abspath(__file__))
    _root = os.path.dirname(os.path.dirname(_here))
    return os.path.join(_root, "data", "standards", "ssui_economic_reference_v1.csv")


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_economic_reference(csv_path: str | None = None) -> dict:
    """读 SSUI 经济参照集 CSV → {version, source, source_url, sha256, ranges}。

    缺失/损坏文件返回 sha256="missing"/"unreadable", ranges={}, version="missing";
    上游据此把旧 SSUI 标记为 stale(审计 P0-1.7: 参数文件 unreadable 禁止复用)。
    """
    path = csv_path or _default_csv_path()
    if not os.path.exists(path):
        return {"version": "missing", "source": "", "source_url": "",
                "sha256": "missing", "ranges": {}}
    try:
        sha = _sha256_file(path)[:16]
    except OSError:
        return {"version": "unreadable", "source": "", "source_url": "",
                "sha256": "unreadable", "ranges": {}}

    ranges: dict[str, dict] = {}
    source_names: list[str] = []
    source_urls: list[str] = []
    versions: list[str] = []
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            code = (row.get("indicator_code") or "").strip()
            if not code:
                continue
            try:
                lo = float(row["lower"])
                hi = float(row["upper"])
            except (KeyError, TypeError, ValueError):
                continue
            ranges[code] = {
                "min": lo,
                "max": hi,
                "unit": (row.get("unit") or "").strip(),
                "direction": (row.get("direction") or "positive").strip(),
                "description": (row.get("indicator_name") or "").strip(),
                "source_name": (row.get("source_name") or "").strip(),
                "source_url": (row.get("source_url") or "").strip(),
                "source_document": (row.get("source_document") or "").strip(),
                "table_or_page": (row.get("table_or_page") or "").strip(),
                "is_proxy": (row.get("is_proxy") or "").strip().lower() in {"true", "1", "yes"},
            }
            if row.get("source_name"):
                source_names.append(row["source_name"])
            if row.get("source_url"):
                source_urls.append(row["source_url"])
            if row.get("version"):
                versions.append(row["version"])

    # 众数(同 version 内通常一致; 不一致取第一条)
    def _mode(lst: list[str]) -> str:
        return lst[0] if lst else ""
    return {
        "version": _mode(versions) or "v1",
        "source": _mode(source_names),
        "source_url": _mode(source_urls),
        "sha256": sha,
        "ranges": ranges,
    }
