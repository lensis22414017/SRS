"""Phase 14 批量数据提取脚本

从 MinerU 解析的 content_list.json 中提取 HTML 表格 → 结构化 long-format CSV。
策略: Python 机械化提取 (HTML parse + regex + 污染物字典匹配), 歧义标记留待 Workflow 核查。

输出: manual_extract/phase14/{paper_id}.csv (单个论文)
      manual_extract/phase14/_all_raw.csv (全量汇总)
"""
from __future__ import annotations
import sys, os, json, csv, re, io
from html.parser import HTMLParser
from pathlib import Path
from collections import defaultdict

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
    # Sum aggregates
    "Sum_PAH_ngg": re.compile(r"(?:∑|Σ|total|sum|total\s+)?\s*PAHs?\b|polycyclic\s*aromatic|多环芳烃|total\s+16\s+PAH", re.I),
    "SumPCB_ngg": re.compile(r"(?:∑|Σ|total|sum)?\s*PCBs?\b|polychlorinated\s*biphenyl|多氯联苯", re.I),
    "SumDDT_ngg": re.compile(r"(?:∑|Σ|total|sum)?\s*DDTs?\b|dichlorodiphenyl|滴滴涕", re.I),
    "SumHCH_ngg": re.compile(r"(?:∑|Σ|total|sum)?\s*HCHs?\b|hexachlorocyclohexane|六六六|BHC", re.I),
    "SumPBDE_ngg": re.compile(r"(?:∑|Σ|total|sum)?\s*PBDEs?\b|polybrominated\s*diphenyl|多溴二苯醚", re.I),
    "SumOCP_ngg": re.compile(r"(?:∑|Σ|total|sum)?\s*OCPs?\b|organochlorine\s*pesticide|有机氯农药", re.I),
    "TotalPHC_mgkg": re.compile(r"(?:total\s+)?(?:petroleum\s*hydrocarbon|TPHs?\b|PHCs?\b|石油烃)", re.I),
    "SumPAE_ngg": re.compile(r"(?:∑|Σ|total|sum)?\s*PAEs?\b|phthalate\s*ester|邻苯二甲酸酯", re.I),
    # PAH monomers (16 EPA)
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
    # Antibiotics
    "SMZ_ngg": re.compile(r"\b(?:SMZ|sulfamethazine|磺胺二甲嘧啶)\b", re.I),
    "CTC_ngg": re.compile(r"\b(?:CTC|chlortetracycline|金霉素)\b", re.I),
    "OTC_ngg": re.compile(r"\b(?:OTC|oxytetracycline|土霉素)\b", re.I),
    "ENRO_ngg": re.compile(r"\b(?:ENRO|enrofloxacin|恩诺沙星)\b", re.I),
    "SDZ_ngg": re.compile(r"\b(?:SDZ|sulfadiazine|磺胺嘧啶)\b", re.I),
    # OPE
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

# 单位检测: 从表头提取
def detect_unit(text):
    """从文本中检测单位。返回 (unit_str, multiplier_to_target)。"""
    for unit, pat in UNIT_PATTERNS.items():
        if pat.search(text):
            return unit
    # 常见中文单位
    if re.search(r"(?:mg\s*·\s*kg|mg\s*kg|毫克每千克|毫克/千克)", text):
        return "mg/kg"
    if re.search(r"(?:ng\s*·\s*g|ng\s*g|纳克每克|纳克/克)", text):
        return "ng/g"
    if re.search(r"(?:μg\s*·\s*kg|ug\s*·\s*kg|微克每千克)", text):
        return "ug/kg"
    return "Unknown"

def normalize_value(val_str):
    """将表格单元格值转为 float, 处理 nd/ND/未检出/—/na/NA/<检出限 等情况。"""
    if not val_str:
        return None, ""
    v = str(val_str).strip()
    if not v:
        return None, ""
    # 非数值标记
    if v.lower() in ("nd", "n.d.", "n.d", "bdl", "ndl", "未检出", "—", "–", "-", "na", "n/a", "nr", "nm"):
        return None, "below_detection"
    # 范围值 (取均值)
    range_match = re.match(r"([\d.]+)\s*[-–—to]+\s*([\d.]+)", v)
    if range_match:
        try:
            return (float(range_match.group(1)) + float(range_match.group(2))) / 2, "range_mean"
        except ValueError:
            return None, "unparseable_range"
    # 小于检出限
    lt_match = re.match(r"[<＜]\s*([\d.]+)", v)
    if lt_match:
        try:
            return float(lt_match.group(1)), "less_than_detection_limit"
        except ValueError:
            return None, "unparseable_lt"
    # > 值 (保留)
    gt_match = re.match(r"[>＞]\s*([\d.]+)", v)
    if gt_match:
        try:
            return float(gt_match.group(1)), "greater_than"
        except ValueError:
            return None, "unparseable_gt"
    # 纯数值 (含科学记数法)
    try:
        return float(v.replace(",", "").replace(" ", "")), ""
    except ValueError:
        return None, "not_numeric"


# ===== 污染物匹配 =====
def match_pollutant(text):
    """将表头/行标签匹配到 SRS 标准污染物名。返回 [(pollutant_std, confidence)]。"""
    matches = []
    # 先匹配聚合指标
    for name, pat in OP_PATTERNS.items():
        if pat.search(text):
            matches.append((name, "high"))
    for name, pat in HM_PATTERNS.items():
        if pat.search(text):
            matches.append((name, "high"))
    for name, pat in PHYS_CHEM_PATTERNS.items():
        if pat.search(text):
            matches.append((name, "high"))
    # 低置信度匹配 (仅关键词命中)
    if not matches:
        if re.search(r"heavy\s*metal|重金属", text, re.I):
            matches.append(("HM_total", "low"))
        if re.search(r"organic\s*pollutant|有机污染", text, re.I):
            matches.append(("OP_total", "low"))
    return matches


def extract_from_table(table_item, paper_id, paper_md_text=""):
    """从一张 MinerU content_list 表格中提取所有数据行。

    table_item: dict with keys type, table_caption, table_body, page_idx
    返回: list of dict (long-format rows)
    """
    body = table_item.get("table_body", "")
    if not body:
        return []

    caption = " ".join([str(c) for c in table_item.get("table_caption", [])]) if table_item.get("table_caption") else ""
    page_idx = table_item.get("page_idx", 0)

    # 解析 HTML 行
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

    # 寻找表头行 — 通常是第一行 (但可能有多行表头)
    header_row = parsed_rows[0]

    # 判断表头方向: 横表头(列名=采样点) vs 纵表头(行名=污染物)
    # 简单策略: 如果第一列是污染物名, 则是纵表头; 否则横表头

    # 先匹配表头列中的污染物
    header_pollutants = []
    for ci, cell in enumerate(header_row):
        pm = match_pollutant(cell)
        if pm:
            header_pollutants.append((ci, pm))

    # 先匹配第一列中的污染物
    first_col_pollutants = []
    for ri, row in enumerate(parsed_rows[1:], start=1):
        if row:
            pm = match_pollutant(row[0])
            if pm:
                first_col_pollutants.append((ri, row[0], pm))

    results = []

    # Strategy 1: 横表头 — 列名是站点, 行名是污染物
    if first_col_pollutants and len(first_col_pollutants) >= 2:
        # 找到数据列 (非污染物名、非统计指标)
        sample_cols = []
        for ci, cell in enumerate(header_row[1:], start=1):
            cell_clean = cell.strip()
            if cell_clean and not re.match(r"^(mean|average|median|sd|std|min|max|range|cv|变异|平均|均值|中位|标准|范围|检出|频率|detection|frequency)$", cell_clean, re.I):
                sample_cols.append((ci, cell_clean))

        if sample_cols:
            for ri, pollutant_name, pms in first_col_pollutants:
                for ci, sample_id in sample_cols:
                    if ci < len(parsed_rows[ri]):
                        val_str = parsed_rows[ri][ci].strip()
                        val, val_flag = normalize_value(val_str)
                        if val is not None:
                            for p_std, conf in pms:
                                results.append({
                                    "paper_id": paper_id,
                                    "sample_id": f"{paper_id}_{sample_id.replace(' ','_')}",
                                    "site_label": sample_id,
                                    "pollutant_std": p_std,
                                    "value": str(val),
                                    "unit": "Unknown",
                                    "value_flag": val_flag,
                                    "confidence": conf,
                                    "evidence_location": f"table_p{page_idx}_ri{ri}_ci{ci}",
                                    "source_caption": caption[:200],
                                })

    # Strategy 2: 横表头 — 列名是污染物, 行名是站点
    elif header_pollutants:
        for ri, row in enumerate(parsed_rows[1:], start=1):
            if not row:
                continue
            sample_id = row[0].strip() if row[0] else f"S{ri}"
            # 过滤非数据行
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
                                "unit": "Unknown",
                                "value_flag": val_flag,
                                "confidence": conf,
                                "evidence_location": f"table_p{page_idx}_ri{ri}_ci{ci}",
                                "source_caption": caption[:200],
                            })

    # Strategy 3: 混合表头 — 行名=污染物, 多列=多站点, 多子表头 (如不同深度/年份)
    # 这个比较复杂, 标记为需要 agent 处理
    if not results and len(parsed_rows) >= 3:
        # 尝试模糊解析: 找同时含数字和污染物名的行
        for ri, row in enumerate(parsed_rows[1:], start=1):
            if len(row) < 2:
                continue
            # 检查是否至少有一个数值列
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
                                "unit": "Unknown",
                                "value_flag": "",
                                "confidence": "medium",
                                "evidence_location": f"table_p{page_idx}_ri{ri}_ci{ci}",
                                "source_caption": caption[:200],
                            })

    return results


def extract_text_content(content_list_json):
    """从 content_list.json 提取全文文本 (用于坐标提取和上下文理解)。"""
    texts = []
    for item in content_list_json:
        if isinstance(item, dict) and item.get("type") == "text":
            texts.append(str(item.get("text", "")))
    return "\n".join(texts)


def extract_coords_from_text(text):
    """从文本中提取 GPS 坐标。返回 [(lat, lon, site_name)]。"""
    coords = []
    # 模式1: N/S + 度分秒 或 十进制
    lat_pattern = re.compile(r"(?:lat(?:itude)?|N)[:\s]*([\d.]+)\s*[°\s]*([\d.]*)[′\s]*([\d.]*)[″\s]*", re.I)
    lon_pattern = re.compile(r"(?:lon(?:gitude)?|E)[:\s]*([\d.]+)\s*[°\s]*([\d.]*)[′\s]*([\d.]*)[″\s]*", re.I)
    # 简化版: 十进制度数 (最常见)
    dms_lat = re.findall(r"(?:latitude|lat)[:\s]*(\d{2}\.\d+)", text, re.I)
    dms_lon = re.findall(r"(?:longitude|lon|lng)[:\s]*(\d{2,3}\.\d+)", text, re.I)
    if dms_lat and dms_lon:
        # 简单配对
        for i in range(min(len(dms_lat), len(dms_lon))):
            coords.append((float(dms_lat[i]), float(dms_lon[i]), "from_text"))
    return coords


def process_paper(dir_name, paper_idx, total):
    """处理一篇论文。返回 (paper_id, rows, errors)。"""
    paper_id = dir_name.replace(".pdf", "").replace("-main", "").replace("%2528", "(").replace("%2529", ")")[:50]
    full_path = BASE / dir_name

    try:
        inner_name = os.listdir(str(full_path))[0]
        inner_path = full_path / inner_name / "auto"

        # 读取 content_list.json (优先非 v2 版本)
        cl_files = sorted([f for f in os.listdir(str(inner_path)) if "content_list" in f and "v2" not in f])
        if not cl_files:
            return paper_id, [], "no_content_list"

        cl_path = inner_path / cl_files[0]
        with open(str(cl_path), "r", encoding="utf-8") as f:
            content = json.load(f)

        # 提取全文文本
        full_text = extract_text_content(content)

        # 提取坐标
        coords = extract_coords_from_text(full_text)

        # 过滤表格
        tables = [item for item in content if isinstance(item, dict) and item.get("type") == "table"]

        # 过滤浓度相关表格
        conc_keywords = ['μg/g','ng/g','mg/kg','mg·kg','concentr','μg·g','ng·g',
                         'soil','sediment','toc','organic carbon',
                         'pah','pcb','ddt','hch','pbde','ope','ocp']

        all_rows = []
        tables_used = 0
        for t in tables:
            caption = " ".join([str(c) for c in t.get("table_caption", [])]) if t.get("table_caption") else ""
            body = t.get("table_body", "")[:5000]  # 截断超长表格
            combined = (caption + " " + body).lower()
            if not any(kw.lower() in combined for kw in conc_keywords):
                continue
            rows = extract_from_table(t, paper_id, full_text)
            all_rows.extend(rows)
            tables_used += 1

        return paper_id, all_rows, f"tables:{tables_used} coords:{len(coords)}"

    except Exception as e:
        return paper_id, [], str(e)[:100]


def main():
    all_dirs = sorted([d for d in os.listdir(str(BASE)) if os.path.isdir(str(BASE / d))])
    print(f"Total dirs: {len(all_dirs)}")

    all_rows = []
    papers_with_data = 0
    papers_without_data = 0
    errors = 0
    total_rows = 0

    for i, d in enumerate(all_dirs):
        pid, rows, status = process_paper(d, i + 1, len(all_dirs))

        if rows:
            papers_with_data += 1
            total_rows += len(rows)
            all_rows.extend(rows)

            # 保存单个论文 CSV
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
            print(f"  [{i+1}/{len(all_dirs)}] data={papers_with_data} no_data={papers_without_data} err={errors} rows={total_rows}")

    # 保存全量汇总
    if all_rows:
        all_csv = OUT_DIR / "_all_raw.csv"
        with open(str(all_csv), "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=all_rows[0].keys())
            writer.writeheader()
            writer.writerows(all_rows)

        # 统计
        from collections import Counter
        pollutants = Counter(r["pollutant_std"] for r in all_rows)
        papers = Counter(r["paper_id"] for r in all_rows)

        print(f"\n{'='*60}")
        print(f"Phase 14 提取完成")
        print(f"{'='*60}")
        print(f"总目录: {len(all_dirs)}")
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
        print(f"\n输出目录: {OUT_DIR}")
        print(f"全量汇总: {OUT_DIR / '_all_raw.csv'}")
    else:
        print("No data extracted!")

    return total_rows

if __name__ == "__main__":
    main()
