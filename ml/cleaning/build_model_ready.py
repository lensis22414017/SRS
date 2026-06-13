"""从 merged_std33 数据湖派生 model_ready 子表。

红线:
- 只读原始数据, 不覆盖/改写 raw;
- 未测污染物保留 NaN, 不补 0, 不补满 719 列;
- 所有实测值为 measured_*, 缺失事实为 missing_*;
- 派生表显式带 is_synthetic=false、evidence_level=MEASURED、source_file_sha256。
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "ml", "cleaning"))
from standardize import (  # noqa: E402
    normalize_landuse,
    normalize_pollution_type,
    normalize_province,
    province_to_region,
)

MERGED = os.path.join(ROOT, "data", "raw", "merged_std33,zh .xlsx")
OUTDIR = os.path.join(ROOT, "data", "model_ready")

HM_COLS = ["Cd_mgkg", "Pb_mgkg", "As_mgkg", "Cu_mgkg", "Zn_mgkg", "Ni_mgkg", "Cr_mgkg", "Hg_mgkg"]
OP_PATTERNS = [
    "Nap", "Phe", "Ant", "Pyr", "BaP", "BaA", "Chr", "Flu", "BghiP", "IcdP",
    "HCH", "DDT", "DDE", "DDD", "PCB", "HCB", "TPH", "PFOS", "PFOA", "PAH",
    "OCP", "PBDE", "BTEX", "Benz",
]
ID_COLS = ["DOI", "Source", "SampleID", "StudyID", "ExperimentID"]
BASE_COVARIATES = [
    "Province", "City", "Region", "Latitude", "Longitude", "LandUse", "Pollution_Type",
    "SamplingYear", "Year", "Country",
]
SOIL_COVARIATES = [
    "pH_merged", "SoilpH", "pH", "OC_pct", "SOC", "BackgroundSOC", "SoilBD_gcm3",
    "BD", "CEC_cmolkg", "CEC", "Sand_pct", "Silt_pct", "Clay_pct", "SandPerc",
    "SiltPerc", "ClayPerc", "SoilTexture", "SoilType",
]
VIEW_ORDER = ["shared", "hm", "op", "hm_op", "risk", "production", "ecology"]


def _sha(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _stable_uid(view: str, row: pd.Series) -> str:
    parts = [
        str(row.get("DOI", "")),
        str(row.get("Source", "")),
        str(row.get("SampleID", "")),
        str(row.get("_source_row_index", "")),
    ]
    digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:16]
    return f"{view}_{digest}"


def pick_op_cols(cols: list[str], op_limit: int | None = None) -> list[str]:
    out = []
    for c in cols:
        cs = str(c)
        low = cs.lower()
        if cs in HM_COLS:
            continue
        if not cs.endswith(("_ngg", "_mgkg", "_ugkg")):
            continue
        if any(p.lower() in low for p in OP_PATTERNS):
            out.append(cs)
    out = sorted(dict.fromkeys(out))
    return out[:op_limit] if op_limit else out


def _existing(df: pd.DataFrame, cols: list[str]) -> list[str]:
    return [c for c in cols if c in df.columns]


def _pollutants_for_view(view: str, df: pd.DataFrame, op_cols: list[str]) -> list[str]:
    hm = _existing(df, HM_COLS)
    if view == "shared":
        return []
    if view == "hm":
        return hm
    if view == "op":
        return op_cols
    return hm + op_cols


def _filter_for_view(df: pd.DataFrame, view: str, pollutants: list[str]) -> pd.DataFrame:
    if view == "shared":
        return df.copy()
    if not pollutants:
        return df.iloc[0:0].copy()
    return df.loc[df[pollutants].notna().any(axis=1)].copy()


def _identity_and_covariate_data(sub: pd.DataFrame, view: str, source_sha256: str) -> dict:
    data = {
        "row_uid": [_stable_uid(view, row) for _, row in sub.iterrows()],
        "dataset_view": view,
        "source_dataset": "merged_std33",
        "source_file_sha256": source_sha256,
        "is_synthetic": False,
        "evidence_level": "MEASURED",
        "simulation_batch_id": pd.NA,
        "generation_rule_version": pd.NA,
    }

    for c in _existing(sub, ID_COLS):
        data[f"id_{c}"] = sub[c].values
    for c in _existing(sub, BASE_COVARIATES + SOIL_COVARIATES):
        data[f"covariate_{c}"] = sub[c].values

    province_source = sub["Province"] if "Province" in sub.columns else pd.Series([None] * len(sub), index=sub.index)
    landuse_source = sub["LandUse"] if "LandUse" in sub.columns else pd.Series([None] * len(sub), index=sub.index)
    pollution_source = sub["Pollution_Type"] if "Pollution_Type" in sub.columns else pd.Series([None] * len(sub), index=sub.index)
    data["covariate_Province_std"] = [normalize_province(v) for v in province_source]
    data["covariate_Region"] = [province_to_region(p) for p in data["covariate_Province_std"]]
    data["covariate_LandUse_std"] = [normalize_landuse(v) for v in landuse_source]
    data["covariate_Pollution_Type_std"] = [normalize_pollution_type(v) for v in pollution_source]
    return data


def build_view(df: pd.DataFrame, view: str, source_sha256: str,
               op_cols: list[str] | None = None) -> pd.DataFrame:
    """构建单个 model_ready 视图。"""
    work = df.copy()
    if "_source_row_index" not in work.columns:
        work["_source_row_index"] = range(len(work))
    op_cols = op_cols if op_cols is not None else pick_op_cols(work.columns.tolist())
    pollutants = _pollutants_for_view(view, work, op_cols)
    sub = _filter_for_view(work, view, pollutants)

    data = _identity_and_covariate_data(sub, view, source_sha256)
    for c in pollutants:
        data[f"measured_{c}"] = sub[c].values
        data[f"missing_{c}"] = sub[c].isna().astype(int).values

    if view in ("risk", "production", "ecology"):
        data[f"label_{view}_source"] = "DERIVED_PENDING_STANDARD_THRESHOLD_SERVICE"
    return pd.DataFrame(data).reset_index(drop=True)


def build_schema(views: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for view, df in views.items():
        for c in df.columns:
            if c.startswith("id_") or c == "row_uid":
                role = "id"
            elif c.startswith("measured_"):
                role = "measured"
            elif c.startswith("missing_"):
                role = "missing_indicator"
            elif c.startswith("covariate_"):
                role = "covariate"
            elif c.startswith("label_"):
                role = "label"
            else:
                role = "metadata"
            rows.append({
                "view": view,
                "column": c,
                "role": role,
                "evidence_level": "MEASURED" if role in ("id", "measured", "covariate") else "DERIVED",
                "include": "Y",
                "missing_strategy": "keep" if role != "label" else "compute_later",
                "note": "未观测值保留为空; 下游训练只允许 train 内插补" if role in ("measured", "missing_indicator") else "",
            })
    return pd.DataFrame(rows)


def build_views(df: pd.DataFrame, source_sha256: str, op_limit: int | None = None):
    """返回 ({view: DataFrame}, schema)。"""
    work = df.copy()
    work["_source_row_index"] = range(len(work))
    op_cols = pick_op_cols(work.columns.tolist(), op_limit=op_limit)
    views = {view: build_view(work, view, source_sha256, op_cols) for view in VIEW_ORDER}
    return views, build_schema(views)


def main():
    sha = _sha(MERGED)
    df = pd.read_excel(MERGED, sheet_name="china")
    os.makedirs(OUTDIR, exist_ok=True)
    views, schema = build_views(df, source_sha256=sha)
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_file": os.path.relpath(MERGED, ROOT),
        "source_file_sha256": sha,
        "views": {},
        "rules": [
            "raw immutable",
            "measured values keep NaN",
            "missing indicators explicit",
            "synthetic rows excluded from model_ready real views",
        ],
    }
    for view, out in views.items():
        path = os.path.join(OUTDIR, f"model_ready_{view}.csv")
        out.to_csv(path, index=False, encoding="utf-8-sig")
        meas_cols = [c for c in out.columns if c.startswith("measured_")]
        manifest["views"][view] = {
            "rows": int(len(out)),
            "columns": int(out.shape[1]),
            "measured_columns": len(meas_cols),
            "preserves_missing": bool(out[meas_cols].isna().any().any()) if meas_cols else True,
            "path": os.path.relpath(path, ROOT),
        }
    schema_path = os.path.join(OUTDIR, "model_ready_schema.csv")
    schema.to_csv(schema_path, index=False, encoding="utf-8-sig")
    manifest_path = os.path.join(OUTDIR, "model_ready_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    assert _sha(MERGED) == sha, "原始文件被改动!"
    for view, meta in manifest["views"].items():
        print(f"{view:10} 行={meta['rows']:6} 列={meta['columns']:4} "
              f"实测列={meta['measured_columns']:3} 保留缺失={meta['preserves_missing']}")
    print("原始 SHA256 未变 ✅")


if __name__ == "__main__":
    main()
