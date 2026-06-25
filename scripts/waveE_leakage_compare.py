"""Wave E 路径C 标签泄漏对照汇总 (裴总2026-06-25拍板路径C)。

读 16 meta.json (full×8 含浓度 + barrier×8 X_barrier纯协变量),
按 (块×轨) 配对对比 AUC, ΔAUC > 0.15 = 标签泄漏实证 (Hu 2026 Commun Earth Environ 铁证复现)。

判据来自 plan E3: row_random/group_split 虚高对照, ΔAUC<0.15 才算无泄漏。
诚实标注: full组AUC虚高不可作独立泛化证据; barrier组AUC低反映协变量覆盖率不足。

运行: cd backend && .venv/bin/python ../scripts/waveE_leakage_compare.py
"""
import os
import json
import glob
from collections import defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ARTIFACTS = os.path.join(ROOT, "ml", "artifacts")
OUT_JSON = os.path.join(ROOT, "docs", "audit", "waveE_leakage_compare.json")
LEAK_THRESHOLD = 0.15  # plan E3: ΔAUC>0.15 = 标签泄漏显著


def main():
    pairs = defaultdict(dict)  # (block, track) -> {group: meta}
    scanned = 0
    for p in sorted(glob.glob(os.path.join(ARTIFACTS, "rf_barrier_factor_*.meta.json"))):
        try:
            with open(p, encoding="utf-8") as f:
                meta = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        scanned += 1
        blk = meta.get("block", "")
        # block 字段 = "hm_prod_full" → rsplit → [hm, prod, full]
        if not blk.endswith(("_full", "_barrier")):
            continue  # 旧单轨模型 或 非路径C产物, 跳过
        parts = blk.rsplit("_", 2)
        if len(parts) != 3:
            continue
        block, track, group = parts
        pairs[(block, track)][group] = meta

    print(f"\n{'=' * 78}")
    print("Wave E 路径C 标签泄漏对照 (full=含浓度 vs barrier=X_barrier纯协变量)")
    print(f"{'=' * 78}")
    print(f"扫描 meta.json: {scanned} | 路径C配对: {len(pairs)} 组 (块×轨)")
    print(f"\n{'块':<11}{'轨':<5}{'full_AUC':<11}{'barrier_AUC':<13}{'ΔAUC':<9}{'full_feat':<11}{'barrier_feat'}")
    print("-" * 78)

    summary = []
    for (block, track), g in sorted(pairs.items()):
        full = g.get("full", {})
        bar = g.get("barrier", {})
        fa = (full.get("metrics") or {}).get("auc")
        ba = (bar.get("metrics") or {}).get("auc")
        delta = round(fa - ba, 4) if fa is not None and ba is not None else None
        ff = full.get("n_features", "?")
        bf = bar.get("n_features", "?")
        print(f"{block:<11}{track:<5}{str(fa):<11}{str(ba):<13}{str(delta):<9}{str(ff):<11}{bf}")
        summary.append({
            "block": block, "track": track,
            "full_auc": fa, "barrier_auc": ba, "delta_auc": delta,
            "full_n_features": ff, "barrier_n_features": bf,
            "full_warning": full.get("leakage_warning"),
            "barrier_warning": bar.get("leakage_warning"),
        })

    deltas = [s["delta_auc"] for s in summary if s["delta_auc"] is not None]
    avg_delta = round(sum(deltas) / len(deltas), 4) if deltas else None
    print("-" * 78)
    print(f"平均 ΔAUC(full−barrier) = {avg_delta}")

    verdict = None
    if avg_delta is not None:
        if avg_delta > LEAK_THRESHOLD:
            verdict = (f"⚠️ 标签泄漏实证: full组AUC显著高于barrier组(平均Δ={avg_delta}>"
                       f"{LEAK_THRESHOLD}), 证明污染物浓度特征致标签泄漏(Hu2026铁证复现)。"
                       f"full组AUC虚高不可作独立泛化证据; barrier组AUC低反映理化协变量覆盖率不足"
                       f"(当前仅SoilpH/OC_pct), 需外部协变量增强(ECA/ITM/GSM/TLDA/PFE)。")
        else:
            verdict = (f"Δ={avg_delta}<{LEAK_THRESHOLD}, group_split口径下标签泄漏不显著"
                       f"(可能浓度-标签关系被group_split部分打散)。")
    print(f"\n结论: {verdict}")

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump({
            "n_pairs": len(pairs),
            "avg_delta_auc": avg_delta,
            "leak_threshold": LEAK_THRESHOLD,
            "verdict": verdict,
            "pairs": summary,
        }, f, ensure_ascii=False, indent=2)
    print(f"\n→ {OUT_JSON}")


if __name__ == "__main__":
    main()
