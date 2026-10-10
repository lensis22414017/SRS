"""v1.2.1(R08): 演示数据包独立校验器 — 不导入 SRS 应用代码, 只用 openpyxl 与标准库。

检查:
  1. metadata.json 登记的每个文件(A–E 与 v1.2.1 补充场景 F/G)SHA-256 一致;
  2. 每个数据文件名与内容含“模拟数据”标签;
  3. 从课题三工作簿的 D1–D25 得分独立重算 SSUI(权重来自 data/standards/ssui_weights_pptx_v1.json,
     公式 SSUI = (1+0.03t)·Σ_c W_c·Σ_i w_i·s_i · M), 与 expected.json 一致(|Δ|<1e-5);
  4. 经济 JSON 的派生关系(total_cost=Σ组分, revenue=yield×price, ratio=revenue/cost)成立,
     且 metadata 明确经济 JSON 不参与 SSUI;
  5. 若存在 actual/comparison.json, 所有比对项通过。
用法: python scripts/validate_demo_package.py --demo demo/mc_v12 [--weights data/standards/ssui_weights_pptx_v1.json]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

LABEL_TOKENS = ("模拟数据", "仅供测试", "模拟材料")


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def main(demo: str, weights: str) -> dict:
    from openpyxl import load_workbook
    meta = json.load(open(os.path.join(demo, "metadata.json"), encoding="utf-8"))
    exp = json.load(open(os.path.join(demo, "expected.json"), encoding="utf-8"))
    W = json.load(open(weights, encoding="utf-8"))
    checks = []

    def chk(name, ok, detail=None):
        checks.append({"check": name, "passed": bool(ok), "detail": detail})
    files = dict(meta.get("files", {}))
    files.update((meta.get("cases_v121") or {}).get("files", {}))
    files.update((meta.get("cases_v122") or {}).get("files", {}))
    bad = [f for f, h in files.items() if not os.path.isfile(os.path.join(demo, f)) or sha(os.path.join(demo, f)) != h]
    chk(f"SHA-256 与 metadata 一致({len(files)} 个文件)", not bad, bad[:5])
    unl = [f for f in files if not any(t in os.path.basename(f) for t in LABEL_TOKENS) and not os.path.basename(f).startswith("F0")]
    chk("数据文件名含模拟数据标签", not unl, unl[:5])
    no_label = []
    for f in files:
        if f.endswith(".xlsx"):
            wb = load_workbook(os.path.join(demo, f), read_only=True)
            txt = " ".join(str(c) for ws in wb.worksheets for row in ws.iter_rows(max_row=12, values_only=True) for c in row if c)
            if not any(t in txt for t in LABEL_TOKENS) and not os.path.basename(f).startswith("F0"):
                no_label.append(f)
    chk("工作簿内容含模拟数据标签", not no_label, no_label[:5])
    inds = W["indicators"]

    def _ssui(path, track, t, M):
        ws = load_workbook(path, read_only=True)["指标得分"]
        scores = [r[6] for r in ws.iter_rows(min_row=2, max_row=26, values_only=True)]
        by_c = {}
        for ind, s in zip(inds, scores):
            by_c[ind["criterion"]] = by_c.get(ind["criterion"], 0.0) + ind["w_" + track] * float(s)
        return (1 + 0.03 * t) * sum(W["criterion_weights"][track][c] * x for c, x in by_c.items()) * M
    # v1.2.2(T01): 演示期望 SSUI 全部落在等级定义域 [0, 1]; v1.2.1 旧得分保留为域外回归夹具
    dom = [(c, tr, ex["ssui"][tr]["ssui"]) for c, ex in exp["scenarios"].items() for tr in ("production", "ecology")]
    chk("A–E 期望 SSUI 均在等级定义域 [0, 1] 内", all(0 <= v <= 1 for _, _, v in dom), [d for d in dom if not 0 <= d[2] <= 1])
    for k, fx in (exp.get("ssui_out_of_domain_fixtures") or {}).items():
        code, track = k.split("_", 1)
        ex = exp["scenarios"][code]["ssui"][track]
        v = _ssui(os.path.join(demo, fx["file"]), track, ex["t"], ex["M"])
        chk(f"[夹具 {k}] 旧得分独立重算 = {fx['ssui']} 且状态 {fx['status']}", abs(v - fx["ssui"]) < 1e-5
            and (fx["status"] == "out_of_domain") == (v > 1.0), round(v, 6))
    h = ((meta.get("cases_v122") or {}).get("cases") or {}).get("H")
    if h:
        chk("[H] 五阶段各有一份模拟材料且文件名含“模拟材料”", len(h["stages"]) == 5 and all("模拟材料" in s["file"] for s in h["stages"]),
            [s["file"] for s in h["stages"]])
        chk("[H] 审核身份为模拟审核员(非真实官员)", "模拟审核员" in h["users"]["reviewer"]["display_name"], h["users"]["reviewer"]["display_name"])
    for code, ex in exp["scenarios"].items():
        d = os.path.join(demo, f"site_{code}")
        for track, pre in (("production", "03_"), ("ecology", "04_")):
            fn = [x for x in sorted(os.listdir(d)) if x.startswith(pre)][0]
            ws = load_workbook(os.path.join(d, fn), read_only=True)["指标得分"]
            scores = [r[6] for r in ws.iter_rows(min_row=2, max_row=26, values_only=True)]
            by_c = {}
            for ind, s in zip(inds, scores):
                by_c[ind["criterion"]] = by_c.get(ind["criterion"], 0.0) + ind["w_" + track] * float(s)
            crit = W["criterion_weights"][track]
            t, M = ex["ssui"][track]["t"], ex["ssui"][track]["M"]
            v = (1 + 0.03 * t) * sum(crit[c] * x for c, x in by_c.items()) * M
            chk(f"[{code}] {track} SSUI 独立重算 = expected", abs(v - ex["ssui"][track]["ssui"]) < 1e-5,
                {"recomputed": round(v, 6), "expected": ex["ssui"][track]["ssui"]})
        e = ex["economics"]
        tc = sum(e[k] for k in ("labour_cost", "machinery_cost", "fertilizer_cost", "seed_cost", "irrigation_cost"))
        chk(f"[{code}] 经济 JSON 派生关系成立", abs(tc - e["total_cost"]) < 0.11 and abs(e["yield_kg"] * e["price_yuan_per_kg"] - e["revenue"]) < 0.2
            and abs(e["revenue"] / e["total_cost"] - e["benefit_cost_ratio"]) < 1e-3, {"total_cost": e["total_cost"], "Σ": round(tc, 1)})
    chk("metadata 声明经济 JSON 不参与 SSUI", "不读取经济 JSON" in (meta.get("economic_inputs_note") or ""), meta.get("economic_inputs_note"))
    cmp_p = os.path.join(demo, "actual", "comparison.json")
    if os.path.isfile(cmp_p):
        cmp_ = json.load(open(cmp_p, encoding="utf-8"))
        s = cmp_.get("summary", {})
        chk(f"actual/comparison.json 全部通过({s.get('passed')}/{s.get('checks')})", s.get("failed") == 0 and s.get("checks"), s)
    res = {"demo": os.path.abspath(demo), "checks": checks, "passed": sum(c["passed"] for c in checks), "total": len(checks),
           "all_passed": all(c["passed"] for c in checks)}
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ap.add_argument("--demo", default=os.path.join(root, "demo", "mc_v12"))
    ap.add_argument("--weights", default=os.path.join(root, "data", "standards", "ssui_weights_pptx_v1.json"))
    ap.add_argument("--json")
    a = ap.parse_args()
    r = main(a.demo, a.weights)
    for c in r["checks"]:
        print(("[PASS] " if c["passed"] else "[FAIL] ") + c["check"])
    print(f"{r['passed']}/{r['total']}")
    if a.json:
        json.dump(r, open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    sys.exit(0 if r["all_passed"] else 1)
