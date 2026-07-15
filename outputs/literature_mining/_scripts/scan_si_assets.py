"""快速筛选G盘SI资产中可形成样点级OP/HM+OP训练数据的表格。"""
from __future__ import annotations

import re
import zipfile
from pathlib import Path

import pandas as pd


ROOT = Path(r"G:\所有文献")
OUT = Path(__file__).resolve().parents[1] / "si_asset_content_scan_20260715.csv"
PRIORITY_LIST = Path(__file__).resolve().parents[1] / "gdrive_priority_assets_20260715.csv"
EXTENSIONS = {".xlsx", ".xls", ".csv", ".zip"}
HM_RE = re.compile(r"(?i)(?:^|\W)(Cd|Pb|As|Cr|Hg|Cu|Zn|Ni)(?:\W|$)|heavy\s*metal|重金属")
OP_RE = re.compile(
    r"(?i)PAH|PFAS|PFOA|PFOS|PBDE|PCB|OCP|pestic|phthal|PAE|flame\s*retard|"
    r"benzo|naphthal|phenanth|pyrene|有机污染|多环芳烃"
)
SOIL_RE = re.compile(r"(?i)soil|土壤|sediment|matrix")
UNIT_RE = re.compile(r"(?i)mg\s*/\s*kg|ng\s*/\s*g|ug\s*/\s*kg|µg\s*/\s*kg|μg\s*/\s*kg|ppm|ppb")
SAMPLE_RE = re.compile(r"(?i)sample|site|location|station|plot|编号|样点|采样点|经度|纬度|longitude|latitude")


def text_score(frame: pd.DataFrame) -> tuple[str, int, int, int, int, int]:
    text = " | ".join(
        str(value) for value in frame.fillna("").astype(str).to_numpy().ravel() if str(value).strip()
    )[:100_000]
    return (
        text[:2000].replace("\n", " "),
        len(HM_RE.findall(text)),
        len(OP_RE.findall(text)),
        len(SOIL_RE.findall(text)),
        len(UNIT_RE.findall(text)),
        len(SAMPLE_RE.findall(text)),
    )


def scan_table(path: Path) -> list[dict]:
    rows: list[dict] = []
    try:
        if path.suffix.lower() == ".csv":
            frames = {"csv": pd.read_csv(path, header=None, nrows=40, low_memory=False)}
        else:
            book = pd.ExcelFile(path)
            frames = {
                str(sheet): pd.read_excel(path, sheet_name=sheet, header=None, nrows=40)
                for sheet in book.sheet_names[:20]
            }
        for sheet, frame in frames.items():
            preview, hm, op, soil, unit, sample = text_score(frame)
            rows.append({
                "path": str(path), "kind": path.suffix.lower(), "sheet": sheet,
                "rows_previewed": len(frame), "columns": len(frame.columns),
                "hm_hits": hm, "op_hits": op, "soil_hits": soil,
                "unit_hits": unit, "sample_hits": sample,
                "priority": 4 * min(hm, 5) + 4 * min(op, 5) + 2 * min(unit, 5)
                            + min(sample, 5) + min(soil, 5),
                "preview": preview,
            })
    except Exception as exc:
        rows.append({"path": str(path), "kind": path.suffix.lower(), "error": repr(exc)})
    return rows


def scan_zip(path: Path) -> list[dict]:
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
        text = " | ".join(names)
        return [{
            "path": str(path), "kind": ".zip", "sheet": "archive_index",
            "rows_previewed": len(names), "columns": 0,
            "hm_hits": len(HM_RE.findall(text)), "op_hits": len(OP_RE.findall(text)),
            "soil_hits": len(SOIL_RE.findall(text)), "unit_hits": len(UNIT_RE.findall(text)),
            "sample_hits": len(SAMPLE_RE.findall(text)), "priority": 0,
            "preview": text[:2000],
        }]
    except Exception as exc:
        return [{"path": str(path), "kind": ".zip", "error": repr(exc)}]


def main() -> None:
    records: list[dict] = []
    if PRIORITY_LIST.exists():
        paths = [Path(value) for value in pd.read_csv(PRIORITY_LIST, encoding="utf-8-sig")["FullName"]]
    else:
        paths = ROOT.rglob("*")
    for path in paths:
        if not path.is_file() or path.suffix.lower() not in EXTENSIONS or path.stat().st_size == 0:
            continue
        records.extend(scan_zip(path) if path.suffix.lower() == ".zip" else scan_table(path))
    result = pd.DataFrame(records)
    result = result.sort_values(["priority", "path"], ascending=[False, True], na_position="last")
    result.to_csv(OUT, index=False, encoding="utf-8-sig")
    print(result.head(60).to_string(index=False, columns=[
        "priority", "hm_hits", "op_hits", "unit_hits", "sample_hits", "columns", "sheet", "path"
    ]))
    print(f"\nscanned_rows={len(result)} output={OUT}")


if __name__ == "__main__":
    main()
