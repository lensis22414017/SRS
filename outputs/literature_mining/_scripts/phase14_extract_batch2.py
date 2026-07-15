"""Phase 14 第二批提取 — 仅处理新增论文
从 existing_pids.txt 过滤已提取论文, 仅处理新解析的 794 篇。
"""
from __future__ import annotations
import sys, os, json, csv, re, io
from html.parser import HTMLParser
from pathlib import Path
from collections import defaultdict, Counter

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = Path(r"G:\所有文献\14.第十阶段小补充 4 文献解析")
OUT_DIR = Path(r"C:\Users\曾鸿\Desktop\SRS\outputs\literature_mining\manual_extract\phase14")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ===== 污染物字典 (对齐 common.py) =====
HM_PATTERNS = {
    "Cd_mgkg": re.compile(r"(?:^|\W)(?:Cd|cadmium)(?:\W|$)", re.I),
    "Pb_mgkg": re.compile(r"(?:^|\W)(?:Pb|lead)(?:\W|$)", re.I),
    "Cr_mgkg": re.compile(r"(?:^|\W)(?:Cr|chromium|chrome)(?:\W|$)", re.I),
    "As_mgkg": re.compile(r"(?:^|\W)(?:As|arsenic)(?:\W|$)", re.I),
    "Hg_mgkg": re.compile(r"(?:^|\W)(?:Hg|mercury)(?:\W|$)", re.I),
    "Cu_mgkg": re.compile(r"(?:^|\W)(?:Cu|copper)(?:\W|$)", re.I),
    "Zn_mgkg": re.compile(r"(?:^|\W)(?:Zn|zinc)(?:\W|$)", re.I),
    "Ni_mgkg": re.compile(r"(?:^|\W)(?:Ni|nickel)(?:\W|$)", re.I),
    "Co_mgkg": re.compile(r"(?:^|\W)(?:Co|cobalt)(?:\W|$)", re.I),
    "Mn_mgkg": re.compile(r"(?:^|\W)(?:Mn|manganese)(?:\W|$)", re.I),
    "Sb_mgkg": re.compile(r"(?:^|\W)(?:Sb|antimony)(?:\W|$)", re.I),
    "Fe_mgkg": re.compile(r"(?:^|\W)(?:Fe|iron)(?:\W|$)", re.I),
    "Al_mgkg": re.compile(r"(?:^|\W)(?:Al|aluminium|aluminum)(?:\W|$)", re.I),
    "V_mgkg": re.compile(r"(?:^|\W)(?:V|vanadium)(?:\W|$)", re.I),
    "Be_mgkg": re.compile(r"(?:^|\W)(?:Be|beryllium)(?:\W|$)", re.I),
}

OP_PATTERNS = {
    "Sum_PAH_ngg": re.compile(r"(?:∑|Σ|total|sum|total\s+)?\s*PAHs?\b|polycyclic\s*aromatic|多环芳烃|total\s+16\s+PAH", re.I),
    "SumPCB_ngg": re.compile(r"(?:∑|Σ|total|sum)?\s*PCBs?\b|polychlorinated\s*biphenyl|多氯联苯", re.I),
    "SumDDT_ngg": re.compile(r"(?:∑|Σ|total|sum)?\s*DDTs?\b|dichlorodiphenyl|滴滴涕", re.I),
    "SumHCH_ngg": re.compile(r"(?:∑|Σ|total|sum)?\s*HCHs?\b|hexachlorocyclohexane|六六六|BHC", re.I),
    "SumPBDE_ngg": re.compile(r"(?:∑|Σ|total|sum)?\s*PBDEs?\b|polybrominated\s*diphenyl|多溴二苯醚", re.I),
    "SumOCP_ngg": re.compile(r"(?:∑|Σ|total|sum)?\s*OCPs?\b|organochlorine\s*pesticide|有机氯农药", re.I),
    "TotalPHC_mgkg": re.compile(r"(?:total\s+)?(?:petroleum\s*hydrocarbon|TPHs?\b|PHCs?\b|石油烃)", re.I),
    "SumPAE_ngg": re.compile(r"(?:∑|Σ|total|sum)?\s*PAEs?\b|phthalate\s*ester|邻苯二甲酸酯", re.I),
    "Nap_ngg": re.compile(r"\b(?:Nap|naphthalene|萘)\b", re.I),
    "Acy_ngg": re.compile(r"\b(?:Acy|acenaphthylene|苊烯)\b", re.I),
    "Ace_ngg": re.compile(r"\b(?:Ace|acenaphthene|苊)(?!烯)\b", re.I),
    "Flu_ngg": re.compile(r"\b(?:Flu|fluorene|芴)\b", re.I),
    "Phe_ngg": re.compile(r"\b(?:Phe|phenanthrene|菲)\b", re.I),
    "Ant_ngg": re.compile(r"\b(?:Ant|anthracene|蒽)\b", re.I),
    "Flt_ngg": re.compile(r"\b(?:Flt|fluoranthene|荧蒽)\b", re.I),
    "Pyr_ngg": re.compile(r"\b(?:Pyr|pyrene|芘)(?!荧蒽)\b", re.I),
    "BaA_ngg": re.compile(r"\b(?:BaA|benz\[?a\]?anthracene|苯并\[?a\]?蒽)\b", re.I),
    "Chr_ngg": re.compile(r"\b(?:Chr|chrysene|䓛)\b", re.I),
    "BbF_ngg": re.compile(r"\b(?:BbF|benz\[?b\]?fluoranthene|苯并\[?b\]?荧蒽)\b", re.I),
    "BkF_ngg": re.compile(r"\b(?:BkF|benz\[?k\]?fluoranthene|苯并\[?k\]?荧蒽)\b", re.I),
    "BaP_ngg": re.compile(r"\b(?:BaP|benz\[?a\]?pyrene|苯并\[?a\]?芘)\b", re.I),
    "Ind_ngg": re.compile(r"\b(?:Ind|IcdP|inden\[?o1,?2,?3-cd\]?pyrene|茚并\[?1,?2,?3-cd\]?芘)\b", re.I),
    "DahA_ngg": re.compile(r"\b(?:DahA|dibenz\[?a,?h\]?anthracene|二苯并\[?a,?h\]?蒽)\b", re.I),
    "BghiP_ngg": re.compile(r"\b(?:BghiP|benz\[?ghi\]?perylene|苯并\[?ghi\]?苝)\b", re.I),
    "SMZ_ngg": re.compile(r"\b(?:SMZ|sulfamethazine|磺胺二甲嘧啶)\b", re.I),
    "CTC_ngg": re.compile(r"\b(?:CTC|chlortetracycline|金霉素)\b", re.I),
    "OTC_ngg": re.compile(r"\b(?:OTC|oxytetracycline|土霉素)\b", re.I),
    "ENRO_ngg": re.compile(r"\b(?:ENRO|enrofloxacin|恩诺沙星)\b", re.I),
    "SDZ_ngg": re.compile(r"\b(?:SDZ|sulfadiazine|磺胺嘧啶)\b", re.I),
    "OPEs_ngg": re.compile(r"\b(?:OPEs?|organophosphate\s*ester|有机磷酸酯)\b", re.I),
}

PHYS_CHEM_PATTERNS = {
    "pH": re.compile(r"\b(?:pH|酸碱度)\b", re.I),
    "OC_pct": re.compile(r"\b(?:OC|organic\s*carbon|TOC|有机碳)(?:\s*%)?", re.I),
    "OM_pct": re.compile(r"\b(?:OM|organic\s*matter|有机质)(?:\s*%)?", re.I),
    "CEC_cmolkg": re.compile(r"\b(?:CEC|cation\s*exchange|阳离子交换)\b", re.I),
    "EC_mScm": re.compile(r"\b(?:EC|electrical\s*conduct|电导率)\b", re.I),
    "Clay_pct": re.compile(r"\b(?:clay|黏粒|粘粒)(?:\s*%)?", re.I),
    "Sand_pct": re.compile(r"\b(?:sand|砂粒)(?:\s*%)?", re.I),
    "Silt_pct": re.compile(r"\b(?:silt|粉粒)(?:\s*%)?", re.I),
}

# ===== 单位归一化 =====
UNIT_PATTERNS = {
    "mg/kg": re.compile(r"mg\s*[/·]\s*kg|mg/kg|mg\s*kg\s*[-−]\s*1|mg\s*·\s*kg", re.I),
    "ng/g": re.compile(r"ng\s*[/·]\s*g|ng/g|ng\s*g\s*[-−]\s*1|ng\s*·\s*g", re.I),
    "ug/kg": re.compile(r"(?:μg|ug)\s*[/·]\s*kg|μg/kg|ug/kg|μg\s*kg\s*[-−]\s*1", re.I),
    "g/kg": re.compile(r"g\s*[/·]\s*kg|g/kg", re.I),
    "%": re.compile(r"^\s*%|percent", re.I),
}

# ==== 值域黑名单: 样本 ID ====
BLACKLIST_SAMPLE_IDS = re.compile(
    r"^(?:abbr|abbr\.|abbreviation|abbreviations|缩写|note|notes|注|说明|"
    r"min|max|mean|average|avg|median|sd|std|std\.?\s*dev|cv|c\.?v\.?|"
    r"range|检出率|检出限|detection\s*(?:limit|frequency|rate)|"
    r"minimum|maximum|variance|"
    r"\d{4}\s*(?:year|yr|年)?)$", re.I
)

# ==== 值域守卫: 年份列检测 ====
def is_year_column(values):
    """检测一列值是否全是年份 (1900-2100 范围内的整数)。"""
    numeric = []
    for v in values:
        try:
            f = float(str(v).strip().replace(",", ""))
            numeric.append(f)
        except (ValueError, TypeError):
            return False
    if len(numeric) < 2:
        return False
    return all(1900 <= v <= 2100 and v == int(v) for v in numeric)


def detect_unit(text):
    for unit, pat in UNIT_PATTERNS.items():
        if pat.search(text):
            return unit
    return "Unknown"

def normalize_value(val_str):
    if not val_str:
        return None, ""
    v = str(val_str).strip()
    if not v:
        return None, ""
    if v.lower() in ("nd", "n.d.", "n.d", "bdl", "ndl", "未检出", "—", "–", "-", "na", "n/a", "nr", "nm"):
        return None, "below_detection"
    range_match = re.match(r"([\d.]+)\s*[-–—to]+\s*([\d.]+)", v)
    if range_match:
        try:
            return (float(range_match.group(1)) + float(range_match.group(2))) / 2, "range_mean"
        except ValueError:
            return None, "unparseable_range"
    lt_match = re.match(r"[<＜]\s*([\d.]+)", v)
    if lt_match:
        try:
            return float(lt_match.group(1)), "less_than_detection_limit"
        except ValueError:
            return None, "unparseable_lt"
    gt_match = re.match(r"[>＞]\s*([\d.]+)", v)
    if gt_match:
        try:
            return float(gt_match.group(1)), "greater_than"
        except ValueError:
            return None, "unparseable_gt"
    try:
        return float(v.replace(",", "").replace(" ", "")), ""
    except ValueError:
        return None, "not_numeric"


def match_pollutant(text):
    matches = []
    for name, pat in OP_PATTERNS.items():
        if pat.search(text):
            matches.append((name, "high"))
    for name, pat in HM_PATTERNS.items():
        if pat.search(text):
            matches.append((name, "high"))
    for name, pat in PHYS_CHEM_PATTERNS.items():
        if pat.search(text):
            matches.append((name, "high"))
    if not matches:
        if re.search(r"heavy\s*metal|重金属", text, re.I):
            matches.append(("HM_total", "low"))
        if re.search(r"organic\s*pollutant|有机污染", text, re.I):
            matches.append(("OP_total", "low"))
    return matches


def extract_from_table(table_item, paper_id, paper_md_text=""):
    body = table_item.get("table_body", "")
    if not body:
        return []

    caption = " ".join([str(c) for c in table_item.get("table_caption", [])]) if table_item.get("table_caption") else ""
    page_idx = table_item.get("page_idx", 0)
    table_unit = detect_unit(f"{caption} {body[:2000]}")

    rows_html = re.findall(r"<tr[^>]*>(.*?)</tr>", body, re.DOTALL)
    if not rows_html:
        return []

    parsed_rows = []
    for rh in rows_html:
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", rh, re.DOTALL)
        if cells:
            parsed_rows.append([c.strip() for c in cells])

    if len(parsed_rows) < 2:
        return []

    header_row = parsed_rows[0]

    header_pollutants = []
    for ci, cell in enumerate(header_row):
        pm = match_pollutant(cell)
        if pm:
            header_pollutants.append((ci, pm))

    first_col_pollutants = []
    for ri, row in enumerate(parsed_rows[1:], start=1):
        if row:
            pm = match_pollutant(row[0])
            if pm:
                first_col_pollutants.append((ri, row[0], pm))

    results = []

    # Strategy 1: 纵表头 — 行名是污染物
    if first_col_pollutants and len(first_col_pollutants) >= 2:
        sample_cols = []
        for ci, cell in enumerate(header_row[1:], start=1):
            cell_clean = cell.strip()
            # 额外检查: 这列里有没有年份?
            if cell_clean and not re.match(r"^(mean|average|median|sd|std|min|max|range|cv|变异|平均|均值|中位|标准|范围|检出|频率|detection|frequency)$", cell_clean, re.I):
                sample_cols.append((ci, cell_clean))

        if sample_cols:
            for ri, pollutant_name, pms in first_col_pollutants:
                for ci, sample_id in sample_cols:
                    if ci < len(parsed_rows[ri]):
                        val_str = parsed_rows[ri][ci].strip()
                        # 过滤黑名单样本ID
                        if BLACKLIST_SAMPLE_IDS.match(val_str):
                            continue
                        val, val_flag = normalize_value(val_str)
                        if val is not None:
                            for p_std, conf in pms:
                                results.append({
                                    "paper_id": paper_id,
                                    "sample_id": f"{paper_id}_{sample_id.replace(' ','_')}",
                                    "site_label": sample_id,
                                    "pollutant_std": p_std,
                                    "value": str(val),
                                    "unit": table_unit,
                                    "value_flag": val_flag,
                                    "confidence": conf,
                                    "evidence_location": f"table_p{page_idx}_ri{ri}_ci{ci}",
                                    "source_caption": caption[:200],
                                })

    # Strategy 2: 横表头 — 列名是污染物
    elif header_pollutants:
        for ri, row in enumerate(parsed_rows[1:], start=1):
            if not row:
                continue
            sample_id = row[0].strip() if row[0] else f"S{ri}"
            # 过滤黑名单
            if BLACKLIST_SAMPLE_IDS.match(sample_id):
                continue
            if re.match(r"^(mean|average|median|sd|std|min|max|range|cv|变异|平均|均值|中位|标准|最小值|最大值|范围)$", sample_id, re.I):
                continue
            for ci, pms in header_pollutants:
                if ci < len(row):
                    val_str = row[ci].strip()
                    val, val_flag = normalize_value(val_str)
                    if val is not None:
                        for p_std, conf in pms:
                            results.append({
                                "paper_id": paper_id,
                                "sample_id": f"{paper_id}_{sample_id.replace(' ','_')}",
                                "site_label": sample_id,
                                "pollutant_std": p_std,
                                "value": str(val),
                                "unit": table_unit,
                                "value_flag": val_flag,
                                "confidence": conf,
                                "evidence_location": f"table_p{page_idx}_ri{ri}_ci{ci}",
                                "source_caption": caption[:200],
                            })

    # Strategy 3: 混合表头
    if not results and len(parsed_rows) >= 3:
        for ri, row in enumerate(parsed_rows[1:], start=1):
            if len(row) < 2:
                continue
            numeric_cols = []
            for ci, cell in enumerate(row[1:], start=1):
                val, _ = normalize_value(cell)
                if val is not None:
                    numeric_cols.append((ci, val))
            if numeric_cols and len(numeric_cols) >= 2:
                pm = match_pollutant(row[0])
                if pm:
                    for ci, val in numeric_cols:
                        if ci < len(header_row):
                            sample_label = header_row[ci].strip() or f"col{ci}"
                        else:
                            sample_label = f"col{ci}"
                        for p_std, conf in pm:
                            results.append({
                                "paper_id": paper_id,
                                "sample_id": f"{paper_id}_{sample_label.replace(' ','_')}",
                                "site_label": sample_label,
                                "pollutant_std": p_std,
                                "value": str(val),
                                "unit": table_unit,
                                "value_flag": "",
                                "confidence": "medium",
                                "evidence_location": f"table_p{page_idx}_ri{ri}_ci{ci}",
                                "source_caption": caption[:200],
                            })

    return results


def extract_text_content(content_list_json):
    texts = []
    for item in content_list_json:
        if isinstance(item, dict) and item.get("type") == "text":
            texts.append(str(item.get("text", "")))
    return "\n".join(texts)


def process_paper(dir_name, paper_idx, total):
    paper_id = dir_name.replace(".pdf", "").replace("-main", "").replace("%2528", "(").replace("%2529", ")")[:50]
    full_path = BASE / dir_name

    try:
        inner_name = os.listdir(str(full_path))[0]
        inner_path = full_path / inner_name / "auto"

        cl_files = sorted([f for f in os.listdir(str(inner_path)) if "content_list" in f and "v2" not in f])
        if not cl_files:
            return paper_id, [], "no_content_list"

        cl_path = inner_path / cl_files[0]
        with open(str(cl_path), "r", encoding="utf-8") as f:
            content = json.load(f)

        full_text = extract_text_content(content)

        tables = [item for item in content if isinstance(item, dict) and item.get("type") == "table"]

        conc_keywords = ['μg/g','ng/g','mg/kg','mg·kg','concentr','μg·g','ng·g',
                         'soil','sediment','toc','organic carbon',
                         'pah','pcb','ddt','hch','pbde','ope','ocp']

        all_rows = []
        tables_used = 0
        for t in tables:
            caption = " ".join([str(c) for c in t.get("table_caption", [])]) if t.get("table_caption") else ""
            body = t.get("table_body", "")[:5000]
            combined = (caption + " " + body).lower()
            if not any(kw.lower() in combined for kw in conc_keywords):
                continue
            rows = extract_from_table(t, paper_id, full_text)
            # 年份列守卫: 如果结果 > 2条且值全是年份, 则跳过此表
            if rows and len(rows) > 2:
                vals = [float(r["value"]) for r in rows if r["value"].replace('.','',1).replace('-','',1).isdigit()]
                if len(vals) > 2 and all(1900 <= v <= 2100 and v == int(v) for v in vals):
                    continue  # 年份列, 非浓度数据
            all_rows.extend(rows)
            tables_used += 1

        return paper_id, all_rows, f"tables:{tables_used}"

    except Exception as e:
        return paper_id, [], str(e)[:100]


def main():
    # 加载已提取论文 ID
    existing_pids_file = Path(r"C:\Users\曾鸿\Desktop\SRS\outputs\literature_mining\_scripts\existing_pids.txt")
    existing_set = set()
    if existing_pids_file.exists():
        with open(str(existing_pids_file), "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    # 归一化
                    pid = line.replace(".pdf", "").replace("-main", "").replace("%2528", "(").replace("%2529", ")")[:50]
                    existing_set.add(pid)
    print(f"已提取论文: {len(existing_set)}")

    # 获取所有解析目录
    all_dirs = sorted([d for d in os.listdir(str(BASE)) if os.path.isdir(str(BASE / d))])
    print(f"解析目录总数: {len(all_dirs)}")

    # 筛选新增
    all_dirs_set = set()
    new_dirs = []
    for d in all_dirs:
        pid = d.replace(".pdf", "").replace("-main", "").replace("%2528", "(").replace("%2529", ")")[:50]
        all_dirs_set.add(pid)
        if pid not in existing_set:
            new_dirs.append(d)
    print(f"新增: {len(new_dirs)}")

    if not new_dirs:
        print("没有新论文需要处理!")
        return

    all_rows = []
    papers_with_data = 0
    papers_without_data = 0
    errors = 0
    total_rows = 0

    for i, d in enumerate(new_dirs):
        pid, rows, status = process_paper(d, i + 1, len(new_dirs))

        if rows:
            papers_with_data += 1
            total_rows += len(rows)
            all_rows.extend(rows)

            csv_path = OUT_DIR / f"{pid}.csv"
            with open(str(csv_path), "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
        else:
            papers_without_data += 1

        if "no_content" in status or "Error" in status:
            errors += 1

        if (i + 1) % 100 == 0:
            print(f"  [{i+1}/{len(new_dirs)}] data={papers_with_data} no_data={papers_without_data} err={errors} rows={total_rows}")

    # 保存全量汇总
    if all_rows:
        all_csv = OUT_DIR / "_all_raw_batch2.csv"
        with open(str(all_csv), "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=all_rows[0].keys())
            writer.writeheader()
            writer.writerows(all_rows)

        pollutants = Counter(r["pollutant_std"] for r in all_rows)
        papers = Counter(r["paper_id"] for r in all_rows)

        print(f"\n{'='*60}")
        print(f"Phase 14 第二批提取完成")
        print(f"{'='*60}")
        print(f"新增处理: {len(new_dirs)}")
        print(f"有数据的论文: {papers_with_data}")
        print(f"无数据的论文: {papers_without_data}")
        print(f"错误: {errors}")
        print(f"总数据行: {total_rows}")
        print(f"唯一论文: {len(papers)}")
        print(f"唯一污染物: {len(pollutants)}")
        print(f"\nTop 20 污染物:")
        for p, c in pollutants.most_common(20):
            print(f"  {p}: {c}")
        print(f"\nTop 10 论文 (按行数):")
        for p, c in papers.most_common(10):
            print(f"  {p}: {c}")
        print(f"\n输出: {all_csv}")
    else:
        print("No data extracted!")

    return total_rows

if __name__ == "__main__":
    main()
