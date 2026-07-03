#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
run_15plus3_validation.py — 15+3 场地双轨 KOS 验证
====================================================================
3 个真实场地(已导入 DB): 个旧HM(1) / 栖霞OP(2) / 乡村HM+OP(3)
15 个内部场地: 从 Gold Dataset 训练数据按 source_id 采样合成
每个场地跑 production / ecology 双轨,输出四层 KOS 结果
====================================================================
"""
import os, sys, json, requests
import pandas as pd
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)
os.environ.setdefault("DATABASE_URL", "sqlite:///./backend/srs.db")

BASE = "http://127.0.0.1:8000/api/v1"
OUT = "artifacts/validation_15plus3_20260703"
os.makedirs(OUT, exist_ok=True)

GOLD = "autoresearch/obstacle_diagnosis_v0.8_gold_training_dataset"


def login():
    r = requests.post(f"{BASE}/auth/login", json={"username": "admin", "password": "Demo@2026"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def run_site_kos(H, site_id, track, subset="all"):
    """对 DB 中的场地跑 KOS 诊断(API 调用)"""
    try:
        r = requests.post(f"{BASE}/sites/{site_id}/kos-diagnosis?track={track}&subset={subset}",
                          headers=H, timeout=60)
        if r.status_code == 200:
            return r.json()
        return {"error": f"{r.status_code}: {r.text[:120]}", "site_id": site_id, "track": track}
    except Exception as e:
        return {"error": str(e)[:120], "site_id": site_id, "track": track}


def sample_internal_sites(n=15):
    """从 Gold Dataset 特征表按 source_id 采样 n 个内部场地"""
    feat = pd.read_parquet(f"{GOLD}/04_feature_tables/model_features_wide_all_v0.8.parquet")
    # 按 source_id 分组,每组取代表样本(首行)
    by_src = feat.groupby("source_id").first().reset_index()
    # 多次采样凑齐 n 个有足够因子的场地(放宽到 >=2 因子)
    sites = []
    seen_src = set()
    seed = 42
    while len(sites) < n and len(seen_src) < len(by_src):
        rng = np.random.RandomState(seed)
        remaining = by_src[~by_src["source_id"].isin(seen_src)]
        if len(remaining) == 0:
            break
        sampled = remaining.sample(n=min(n - len(sites), len(remaining)), random_state=seed)
        seed += 1
        for _, row in sampled.iterrows():
            sid = str(row["source_id"])
            if sid in seen_src:
                continue
            factors = {}
            for c in feat.columns:
                if c.startswith("x_measured_") and pd.notna(row.get(c)):
                    fname = c.replace("x_measured_", "")
                    factors[fname] = float(row[c])
            if len(factors) >= 2:
                seen_src.add(sid)
                hm_any = any(k in factors for k in ["Cd_mgkg", "Pb_mgkg", "As_mgkg", "Cu_mgkg", "Zn_mgkg"])
                op_any = any("PAH" in k or "BaP" in k or "DDT" in k or "HCH" in k for k in factors)
                ptype = "composite" if (hm_any and op_any) else ("organic" if op_any else "heavy_metal")
                sites.append({"source_id": sid, "factors": factors,
                              "province": row.get("province", "未知"),
                              "pollution_type": ptype, "n_factors": len(factors)})
                if len(sites) >= n:
                    break
    return sites


def run_internal_kos(factors, track, subset="all"):
    """对内部采样场地跑 KOS(直接调 service,不走 API)"""
    from backend.app.services.kos_service import run_kos_diagnosis
    try:
        return run_kos_diagnosis(factors, track=track, subset=subset)
    except Exception as e:
        return {"error": str(e)[:120]}


def main():
    H = login()
    all_results = []
    rankings = []
    model_attentions = []
    family_warns = []
    unknown_alerts = []
    recommended = []
    review_flags = []

    # ── 3 个真实场地(API 验证)──
    real_sites = [
        {"site_id": 1, "name": "云南个旧(HM)", "type": "heavy_metal", "province": "云南", "subset": "hm"},
        {"site_id": 2, "name": "南京栖霞(OP)", "type": "organic", "province": "江苏", "subset": "op"},
        {"site_id": 3, "name": "乡村复合(HM+OP)", "type": "composite", "province": "未知", "subset": "all"},
    ]
    print("=" * 60)
    print("3 真实场地双轨验证(API)")
    print("=" * 60)
    for s in real_sites:
        for track in ["prod", "eco"]:
            r = run_site_kos(H, s["site_id"], track, s["subset"])
            r["site_name"] = s["name"]
            r["pollution_type"] = s["type"]
            r["province"] = s["province"]
            r["source"] = "real"
            all_results.append(r)
            if "error" not in r:
                top5 = [k["factor"] for k in r.get("key_obstacles", [])[:5]]
                n_ma = len(r.get("model_attention_factors", []))
                n_fw = len(r.get("family_warnings", []))
                n_ua = len(r.get("unknown_alerts", []))
                review = r.get("review_required", False)
                print(f"  {s['name']:20s} {track}: Top5={top5[:3]} 关注={n_ma} 族群={n_fw} 未知={n_ua} 复核={review}")
                rankings.append({"site": s["name"], "track": track, "top5": top5, "source": "real"})
                review_flags.append({"site": s["name"], "track": track, "review_required": review,
                                     "n_formal": len(r.get("key_obstacles", [])),
                                     "n_attention": n_ma, "n_family": n_fw, "n_unknown": n_ua})
                for ma in r.get("model_attention_factors", [])[:3]:
                    model_attentions.append({"site": s["name"], "track": track, **ma})
                for fw in r.get("family_warnings", [])[:3]:
                    family_warns.append({"site": s["name"], "track": track, **fw})
                for ua in r.get("unknown_alerts", [])[:3]:
                    unknown_alerts.append({"site": s["name"], "track": track, **ua})
                for rt in r.get("recommended_tests", [])[:3]:
                    recommended.append({"site": s["name"], "track": track, **rt})
            else:
                print(f"  {s['name']} {track}: ❌ {r['error'][:60]}")

    # ── 15 个内部场地(service 直调,同样收集四层)──
    print("\n" + "=" * 60)
    print("15 内部场地双轨验证(service)")
    print("=" * 60)
    internal = sample_internal_sites(15)
    print(f"采样到 {len(internal)} 个内部场地")
    for i, s in enumerate(internal):
        name = f"内部#{i+1}({s['source_id'][:12]})"
        subset = {"heavy_metal": "hm", "organic": "op"}.get(s["pollution_type"], "all")
        for track in ["prod", "eco"]:
            r = run_internal_kos(s["factors"], track, subset)
            r["site_name"] = name
            r["pollution_type"] = s["pollution_type"]
            r["province"] = s["province"]
            r["source"] = "internal"
            all_results.append(r)
            if "error" not in r:
                top5 = [k["factor"] for k in r.get("key_obstacles", [])[:5]]
                review = r.get("review_required", False)
                n_ma = len(r.get("model_attention_factors", []))
                n_fw = len(r.get("family_warnings", []))
                n_ua = len(r.get("unknown_alerts", []))
                print(f"  {name:25s} {track}: Top5={top5[:3]} 关注={n_ma} 族群={n_fw} 未知={n_ua} 复核={review}")
                rankings.append({"site": name, "track": track, "top5": top5, "source": "internal"})
                review_flags.append({"site": name, "track": track, "review_required": review,
                                     "n_formal": len(r.get("key_obstacles", [])),
                                     "n_attention": n_ma, "n_family": n_fw, "n_unknown": n_ua})
                # 内部场地也收集四层(裴总要求证据文件非空)
                for ma in r.get("model_attention_factors", [])[:5]:
                    model_attentions.append({"site": name, "track": track, **ma})
                for fw in r.get("family_warnings", [])[:5]:
                    family_warns.append({"site": name, "track": track, **fw})
                for ua in r.get("unknown_alerts", [])[:5]:
                    unknown_alerts.append({"site": name, "track": track, **ua})
                for rt in r.get("recommended_tests", [])[:3]:
                    recommended.append({"site": name, "track": track, **rt})

    # ── 汇总输出 ──
    pd.DataFrame(rankings).to_csv(f"{OUT}/kos_rankings.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(model_attentions).to_csv(f"{OUT}/model_attention_factors.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(family_warns).to_csv(f"{OUT}/family_warnings.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(unknown_alerts).to_csv(f"{OUT}/unknown_alerts.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(recommended).to_csv(f"{OUT}/recommended_tests.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(review_flags).to_csv(f"{OUT}/review_required_summary.csv", index=False, encoding="utf-8-sig")
    with open(f"{OUT}/diagnosis_outputs.json", "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2, default=str)

    # manifest(裴总要求字段: site_id/site_name/source/type/track/n_key/n_attention/n_family/n_unknown/review_required/status)
    manifest = pd.DataFrame([{
        "site_name": r.get("site_name"), "source": r.get("source"),
        "type": r.get("pollution_type"), "track": r.get("track"),
        "n_key": len(r.get("key_obstacles", [])) if "error" not in r else 0,
        "n_attention": len(r.get("model_attention_factors", [])) if "error" not in r else 0,
        "n_family": len(r.get("family_warnings", [])) if "error" not in r else 0,
        "n_unknown": len(r.get("unknown_alerts", [])) if "error" not in r else 0,
        "review_required": r.get("review_required", False) if "error" not in r else None,
        "status": "ok" if "error" not in r else "error",
    } for r in all_results])
    manifest.to_csv(f"{OUT}/validation_manifest.csv", index=False, encoding="utf-8-sig")

    n_ok = len([r for r in all_results if "error" not in r])
    n_review = len([r for r in all_results if r.get("review_required")])
    n_unique = manifest["site_name"].nunique()
    print(f"\n{'='*60}")
    print(f"验证完成: {n_ok}/{len(all_results)} 行成功, {n_unique} 个唯一场地, {n_review} 个需复核")
    print(f"四层证据: attention={len(model_attentions)} family={len(family_warns)} unknown={len(unknown_alerts)}")
    print(f"输出: {OUT}/")


if __name__ == "__main__":
    main()
