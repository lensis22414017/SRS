"""生态阈值库 PCB/二噁英 科学计数法文本→数值修复 (Wave B 前置, 裴总#3)。

问题: data/knowledge_base/阈值库/生态/thresholds.csv 第210-215行
  threshold_value="≤1×10⁻⁴mg/kg" 等科学计数法文本,
  _parse_thr_val 正则只抓首数字→1.0(放大10000倍), 致超毒物系统性漏判。
修复: ×10⁻ⁿ → 小数, 保留 ≤mg/kg 格式(_parse_thr_val 可正确解析 ≤0.0001→0.0001)。
仅修科学计数法行, 不动其他阈值(≤X/区间已正确)。备份 .bak_sci。

验证: 修后跑 _parse_thr_val 确认 ≤0.0001→0.0001 正确。
"""
import csv
import re
import os
import shutil
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ECO = os.path.join(ROOT, "data", "knowledge_base", "阈值库", "生态", "thresholds.csv")
SUP = {"⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4", "⁵": "5",
       "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9", "⁻": "-", "⁺": "+"}


def parse_sci(s):
    """'≤1×10⁻⁴mg/kg' → 0.0001 (float)。None=非科学计数法。"""
    m = re.search(r"([\d.]+)\s*[×x]\s*10([⁻⁺]?[⁰¹²³⁴⁵⁶⁷⁸⁹]+)", s)
    if not m:
        return None
    mantissa = float(m.group(1))
    exp_str = "".join(SUP.get(c, c) for c in m.group(2))
    return mantissa * (10 ** int(exp_str))


def main():
    with open(ECO, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)
    fixed = 0
    for r in rows:
        v = r.get("threshold_value", "")
        sci = parse_sci(v)
        if sci is not None:
            prefix = "≤" if "≤" in v else ""
            munit = re.search(r"(mg/kg|g/cm³|ug/kg|%)", v)
            unit = munit.group(1) if munit else ""
            sci_str = f"{sci:.10f}".rstrip("0").rstrip(".")  # 定点非科学计数法(_parse_thr_val正则不认e)
            new_v = f"{prefix}{sci_str}{unit}"
            print(f"  {r['factor']} | {v} → {new_v}")
            r["threshold_value"] = new_v
            fixed += 1
    shutil.copy(ECO, ECO + ".bak_sci")
    with open(ECO, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    print(f"\n✓ 修复 {fixed} 行科学计数法阈值 → {ECO}")
    print(f"  备份: {ECO}.bak_sci")

    # 验证 _parse_thr_val 能正确解析修复后的值
    sys.path.insert(0, os.path.join(ROOT, "ml", "etl"))
    from build_training_splits import _parse_thr_val  # noqa
    print("\n=== 验证 _parse_thr_val 解析修复后值 ===")
    with open(ECO, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if "PCB" in r.get("factor", "") or "二噁英" in r.get("factor", ""):
                v = _parse_thr_val(r["threshold_value"])
                print(f"  {r['factor']}: '{r['threshold_value']}' → {v}")


if __name__ == "__main__":
    import sys
    main()
