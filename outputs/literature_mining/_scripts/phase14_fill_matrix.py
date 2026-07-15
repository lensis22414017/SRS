"""Phase14 matrix 填充脚本

从每篇论文的 MinerU Markdown 文本中自动推断 matrix (soil/sediment/water/dust/egg/plant)。
策略: 关键词匹配 + 标题/方法部分加权。
"""
from __future__ import annotations
import sys, csv, os, re
from pathlib import Path
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = Path(r"G:\所有文献\14.第十阶段小补充 4 文献解析")
PHASE14_DIR = Path(r"C:\Users\曾鸿\Desktop\SRS\outputs\literature_mining\manual_extract\phase14")
ME_OP = Path(r"C:\Users\曾鸿\Desktop\SRS\outputs\literature_mining\manual_extract\op_only")
ME_HMOP = Path(r"C:\Users\曾鸿\Desktop\SRS\outputs\literature_mining\manual_extract\hm_op")

MATRIX_KEYWORDS = {
    "soil": [
        r"\bsoil\b", r"\bsoils\b", r"\b土壤\b", r"topsoil", r"surface\s*soil",
        r"agricultural\s*(?:soil|land|field)", r"farmland", r"paddy\s*soil",
        r"forest\s*soil", r"grassland\s*soil", r"urban\s*soil", r"park\s*soil",
        r"industrial\s*soil", r"brownfield", r"cultivated\s*soil",
        r"soil\s*sample", r"soil\s*collected", r"soil\s*was", r"soils\s*were",
    ],
    "sediment": [
        r"\bsediment\b", r"\bsediments\b", r"\b沉积物\b", r"\b底泥\b",
        r"river\s*sediment", r"lake\s*sediment", r"marine\s*sediment",
        r"reservoir\s*sediment", r"stream\s*sediment", r"pond\s*sediment",
        r"surface\s*sediment", r"core\s*sediment",
    ],
    "water": [
        r"\bwater\b", r"\bwaters\b", r"\b水样\b", r"\b水体\b", r"\b水质\b",
        r"surface\s*water", r"groundwater", r"wastewater", r"pore\s*water",
        r"river\s*water", r"lake\s*water", r"sea\s*water",
    ],
    "dust": [
        r"\bdust\b", r"\bdusts\b", r"\b灰尘\b", r"\b粉尘\b",
        r"road\s*dust", r"street\s*dust", r"house\s*dust", r"indoor\s*dust",
        r"atmospheric\s*dust", r"deposited\s*dust",
    ],
    "sediment": [
        r"\bsediment\b", r"\bsediments\b", r"\b沉积物\b", r"\b底泥\b",
    ],
}


def get_paper_md(dir_name):
    """找到论文的 Markdown 文件路径。"""
    full = BASE / dir_name
    if not full.exists():
        return None
    try:
        inner_name = os.listdir(str(full))[0]
        inner = full / inner_name / "auto"
        md_files = list(inner.glob("*.md"))
        if md_files:
            return md_files[0]
    except Exception:
        pass
    return None


def infer_matrix_from_text(text):
    """从论文全文 Markdown 推断主要介质类型。返回 (matrix, confidence)。"""
    text_lower = text.lower()
    scores = Counter()

    # 标题加权 (前500字符 = 标题+摘要)
    title_text = text[:500].lower()

    for matrix_type, patterns in MATRIX_KEYWORDS.items():
        for pat in patterns:
            matches = re.findall(pat, title_text, re.IGNORECASE)
            scores[matrix_type] += len(matches) * 3  # 标题命中 ×3
            matches_body = re.findall(pat, text_lower, re.IGNORECASE)
            scores[matrix_type] += len(matches_body)

    if not scores:
        return "soil", "default"  # 默认假设土壤

    # 取最高分
    best = scores.most_common(1)[0]
    matrix_type = best[0]
    score = best[1]

    # 置信度
    if score >= 20:
        conf = "high"
    elif score >= 10:
        conf = "medium"
    else:
        conf = "low"

    return matrix_type, f"score={score}:{conf}"


def infer_site_type_from_text(text):
    """从文本推断场地类型。"""
    text_lower = text.lower()
    rules = [
        ("agricultural", [r"agricultur", r"farmland", r"paddy", r"cropland", r"农田", r"耕地", r"水稻"]),
        ("industrial", [r"industr", r"工厂", r"工业", r"abandoned", r"brownfield"]),
        ("mining", [r"mining", r"mine", r"矿", r"tailings", r"尾矿"]),
        ("e_waste", [r"e-waste", r"electronic waste", r"电子垃圾", r"电子废弃物"]),
        ("urban", [r"urban", r"城市", r"residential", r"居住"]),
        ("oilfield", [r"oilfield", r"oil field", r"油田", r"石油"]),
        ("coking", [r"coking", r"coke", r"焦化", r"coal tar"]),
    ]
    for stype, patterns in rules:
        if any(re.search(p, text_lower, re.IGNORECASE) for p in patterns):
            return stype
    return "other"


def get_paper_text_from_dir(dir_name):
    """获取论文全文 Markdown。"""
    md_path = get_paper_md(dir_name)
    if md_path:
        try:
            with open(str(md_path), "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            return ""
    return ""


def main():
    # 1. 收集所有需要填充 matrix 的论文 (来自 Phase14)
    p14_pids = set()
    for sub in [PHASE14_DIR / "op_only", PHASE14_DIR / "hm_op"]:
        if sub.exists():
            p14_pids.update(f.stem for f in sub.glob("*.csv"))

    print(f"Phase14 论文: {len(p14_pids)}")

    # 2. 建立 dir_name → paper_id 映射
    # Phase14 目录名可能包含 paper_id
    all_dirs = [d for d in os.listdir(str(BASE)) if os.path.isdir(str(BASE / d))]
    dir_to_pid = {}
    for d in all_dirs:
        pid = d.replace(".pdf", "").replace("-main", "").replace("%2528", "(").replace("%2529", ")")[:50]
        # 也需要更宽松的匹配
        for target_pid in p14_pids:
            if target_pid in pid or pid in target_pid:
                dir_to_pid[target_pid] = d
                break

    print(f"  dir 映射: {len(dir_to_pid)}")

    # 3. 逐个处理已写入 manual_extract 的 Phase14 CSV
    # 目标: 填充 matrix, site_type, province
    stats = {"filled": 0, "skipped": 0, "errors": 0}
    matrix_counts = Counter()
    site_type_counts = Counter()

    for pid in p14_pids:
        # 查找对应的 Phase14 目录
        phase14_dir = None
        if pid in dir_to_pid:
            phase14_dir = dir_to_pid[pid]

        # 读取论文文本
        paper_text = ""
        if phase14_dir:
            paper_text = get_paper_text_from_dir(phase14_dir)

        # 推断 matrix 和 site_type
        if paper_text:
            matrix, matrix_note = infer_matrix_from_text(paper_text)
            site_type = infer_site_type_from_text(paper_text)
        else:
            matrix, matrix_note = "soil", "no_text:default"
            site_type = "other"

        matrix_counts[matrix] += 1
        site_type_counts[site_type] += 1

        # 4. 更新 manual_extract 中的 CSV
        for target_dir in [ME_OP, ME_HMOP]:
            csv_path = target_dir / f"{pid}.csv"
            if not csv_path.exists():
                continue

            # 读取现有行
            with open(str(csv_path), "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames
                rows = list(reader)

            modified = False
            for r in rows:
                if not r.get("matrix") or r["matrix"] == "":
                    r["matrix"] = matrix
                    modified = True
                if not r.get("site_type") or r["site_type"] == "":
                    r["site_type"] = site_type
                    modified = True
                # 更新 extract_notes
                notes = r.get("extract_notes", "")
                if "phase14_auto" not in notes:
                    r["extract_notes"] = f"phase14_auto; matrix={matrix_note}"

            if modified:
                with open(str(csv_path), "w", newline="", encoding="utf-8-sig") as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(rows)
                stats["filled"] += 1
            else:
                stats["skipped"] += 1

        if len(stats) % 50 == 0:
            print(f"  ... 已处理 {stats['filled']} 篇")

    print(f"\n{'='*60}")
    print(f"Matrix 填充完成")
    print(f"{'='*60}")
    print(f"填充: {stats['filled']} 篇, 跳过: {stats['skipped']}, 错误: {stats['errors']}")
    print(f"Matrix 分布: {dict(matrix_counts.most_common())}")
    print(f"Site type 分布: {dict(site_type_counts.most_common())}")

    return stats

if __name__ == "__main__":
    main()
