"""P2C Step 2: C 级 1055 篇 OP-only 全量抽取 (裴总质疑"几千条提不出来"的核心增量)

复用 p2_extract.extract_table (含 6 类陷阱排除) + p2_classify_tables_v2.classify_one.
对 C 级每篇: read_html → classify_one 过滤 → extract_table 抽取.
输出 c_level_observations.csv, 后续合并到 extracted_observations_long + 重跑 P3/P7.

质量继承: extract_table 已内建拒绝规则 (植物/土地利用汇总/生物修复/参考文献/转置表/summary Mean),
C 级直接复用, 不另写拒绝逻辑.
"""
from __future__ import annotations
import sys
import os
import re
from io import StringIO
from pathlib import Path

# 修复 Windows GBK 控制台 emoji/Unicode 崩溃 (probe 末尾 ✅ 报错根因)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent))
from common import OUT_DIR, LIT_ROOT, classify_landuse  # noqa: E402
from p2_extract import extract_table  # noqa: E402
from p2_classify_tables_v2 import classify_one, extract_title  # noqa: E402

import pandas as pd  # noqa: E402

TABLE_OPEN_PAT = re.compile(r"<table[\s>]", re.I)


def main():
    cand = pd.read_csv(OUT_DIR / "candidate_literature_op_hmop.csv", dtype=str, keep_default_na=False)
    c_level = cand[cand["candidate_level"] == "C"].copy()
    # P2C_LIMIT=N 仅处理前 N 篇 (冒烟测试用)
    limit = int(os.environ.get("P2C_LIMIT", "0"))
    if limit:
        c_level = c_level.head(limit)
        print(f"[冒烟测试] 仅处理前 {limit} 篇")
    print(f"C 级论文: {len(c_level)}")

    all_records = []
    log_rows = []
    stats = {"no_md": 0, "no_table": 0, "parse_err": 0, "parsed_ok": 0,
             "tables_seen": 0, "tables_conc_classified": 0,
             "tables_extracted": 0, "records_extracted": 0}

    n_total = len(c_level)
    for idx, (_, r) in enumerate(c_level.iterrows()):
        pid, stem = r["paper_id"], r["stem"]
        if (idx + 1) % 100 == 0:
            print(f"  进度 {idx+1}/{n_total} | 已抽 {stats['records_extracted']} 观测 / "
                  f"{stats['tables_extracted']} 表 / {stats['parsed_ok']} 篇解析", flush=True)
        md = LIT_ROOT / stem / "parsed" / "paper.md"
        if not md.exists():
            stats["no_md"] += 1
            continue
        try:
            text = md.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            stats["no_md"] += 1
            continue
        if "<table" not in text.lower():
            stats["no_table"] += 1
            continue

        positions = [m.start() for m in TABLE_OPEN_PAT.finditer(text)]
        try:
            tables = pd.read_html(StringIO(text))
        except Exception as e:
            stats["parse_err"] += 1
            log_rows.append({"paper_id": pid, "stem": stem, "tbl_idx": -1,
                             "title": "", "category": "",
                             "extract_status": "parse_err", "extract_note": str(e)[:50]})
            continue
        stats["parsed_ok"] += 1
        stats["tables_seen"] += len(tables)

        paper_info = {
            "paper_id": pid, "doi": r.get("doi", ""),
            "title": r.get("title", ""), "year": r.get("year", ""),
            "province": "", "city_or_region": "", "site_name": r.get("region", ""),
            "land_use": classify_landuse(stem + " " + r.get("title", "")),
        }

        for i, tbl in enumerate(tables):
            tbl_pos = positions[i] if i < len(positions) else 0
            text_before = text[max(0, tbl_pos - 700):tbl_pos]
            title = extract_title(text_before)
            try:
                tbl_text = tbl.to_string(index=False, header=False)
            except Exception:
                tbl_text = ""
            info = classify_one(tbl_text, title)
            # 只抽有浓度信号的表 (排除 risk_or_source / other)
            if info["category"] in ("risk_or_source", "other"):
                continue
            stats["tables_conc_classified"] += 1
            try:
                records, status, note = extract_table(tbl, title, paper_info, stem, i)
            except Exception as e:
                log_rows.append({"paper_id": pid, "stem": stem, "tbl_idx": i,
                                 "title": title[:80], "category": info["category"],
                                 "extract_status": "exception", "extract_note": str(e)[:60]})
                continue
            all_records.extend(records)
            stats["tables_extracted"] += 1
            stats["records_extracted"] += len(records)
            log_rows.append({"paper_id": pid, "stem": stem, "tbl_idx": i,
                             "title": title[:80], "category": info["category"],
                             "extract_status": status, "extract_note": note[:100]})

    df_out = pd.DataFrame(all_records)
    out_path = OUT_DIR / "c_level_observations.csv"
    df_out.to_csv(out_path, index=False, encoding="utf-8-sig")
    df_log = pd.DataFrame(log_rows)
    df_log.to_csv(OUT_DIR / "p2c_extraction_log.csv", index=False, encoding="utf-8-sig")

    print(f"\n=== P2C C 级抽取结果 ===")
    print(f"统计: {stats}")
    print(f"总观测: {len(df_out)}, 论文: {df_out['paper_id'].nunique() if len(df_out) else 0}")
    if len(df_out):
        print(f"\nevidence_level:")
        print(df_out["evidence_level"].value_counts().to_string())
        print(f"\npollutant_name_std top 15:")
        print(df_out["pollutant_name_std"].value_counts().head(15).to_string())
        print(f"\npollution_type:")
        print(df_out["pollution_type"].value_counts().to_string())
        print(f"\nextract_status 分布 (日志):")
        print(df_log["extract_status"].value_counts().to_string())
    print(f"\n输出: {out_path}")
    print(f"日志: {OUT_DIR / 'p2c_extraction_log.csv'}")


if __name__ == "__main__":
    main()
