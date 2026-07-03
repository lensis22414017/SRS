#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
run_round6_batch_validation.py — 第二阶段 15+3 场地批量验证(11 环节 × 16 字段)
====================================================================
3 真实场地(DB id 1/2/3, 已导入): 走 API 全 11 环节
15 内部场地(parquet 采样合成): 走 service 直调, 仅 KOS 链路(诚实标注)

11 环节:
  1. 数据导入  2. 数据质量检查  3. KOS生产轨  4. KOS生态轨
  5. 功能重构  6. SSUI  7. 方案推荐  8. PDF报告  9. DOCX报告
  10. 权限隔离  11. 地图截图(占位, 实际由节八 Playwright 产出)

16 字段(裴总要求):
  site_id/site_name/pollution_type/region/n_points
  prod_status/eco_status/reconstruction_status/ssui_status/recommendation_status
  report_pdf_status/report_docx_status/map_status/screenshot_status
  errors/review_required

输出: docs/reports/round6_15plus3_batch_validation.md
====================================================================
"""
import os, sys, json, requests
import pandas as pd
import numpy as np
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)
os.environ.setdefault("DATABASE_URL", "sqlite:///./backend/srs.db")

BASE = "http://127.0.0.1:8000/api/v1"
NOW = datetime.now().strftime("%Y-%m-%d %H:%M")
GOLD = "autoresearch/obstacle_diagnosis_v0.8_gold_training_dataset"


def login(username="admin", password="Demo@2026"):
    try:
        r = requests.post(f"{BASE}/auth/login", json={"username": username, "password": password}, timeout=10)
        if r.status_code == 200:
            return {"Authorization": f"Bearer {r.json()['access_token']}"}
    except Exception:
        pass
    return None


def api_call(H, method, path, **kwargs):
    try:
        r = getattr(requests, method)(f"{BASE}{path}", headers=H, timeout=60, **kwargs)
        return r.status_code, r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text[:200]
    except Exception as e:
        return -1, str(e)[:120]


def sample_internal_sites(n=15):
    """复用 v1 的内部场地采样逻辑"""
    feat = pd.read_parquet(f"{GOLD}/04_feature_tables/model_features_wide_all_v0.8.parquet")
    by_src = feat.groupby("source_id").first().reset_index()
    sites, seen, seed = [], set(), 42
    while len(sites) < n and len(seen) < len(by_src):
        rng = np.random.RandomState(seed)
        remaining = by_src[~by_src["source_id"].isin(seen)]
        if len(remaining) == 0:
            break
        sampled = remaining.sample(n=min(n - len(sites), len(remaining)), random_state=seed)
        seed += 1
        for _, row in sampled.iterrows():
            sid = str(row["source_id"])
            if sid in seen:
                continue
            factors = {}
            for c in feat.columns:
                if c.startswith("x_measured_") and pd.notna(row.get(c)):
                    factors[c.replace("x_measured_", "")] = float(row[c])
            if len(factors) >= 2:
                seen.add(sid)
                hm = any(k in factors for k in ["Cd_mgkg", "Pb_mgkg", "As_mgkg", "Cu_mgkg", "Zn_mgkg"])
                op = any("PAH" in k or "BaP" in k or "DDT" in k for k in factors)
                sites.append({
                    "source_id": sid, "factors": factors,
                    "province": row.get("province", "未知"),
                    "pollution_type": "composite" if (hm and op) else ("organic" if op else "heavy_metal"),
                })
                if len(sites) >= n:
                    break
    return sites


def validate_real_site(H_admin, H_regulator, site_id, name, pollution_type, province, subset):
    """真实场地走 API, 跑 11 环节, 返回 16 字段 dict"""
    row = {
        "site_id": site_id, "site_name": name, "pollution_type": pollution_type,
        "region": province, "n_points": None,
        "prod_status": "—", "eco_status": "—", "reconstruction_status": "—",
        "ssui_status": "—", "recommendation_status": "—",
        "report_pdf_status": "—", "report_docx_status": "—",
        "map_status": "—", "screenshot_status": "待节八",
        "errors": [], "review_required": False,
    }

    # 1. 数据导入(已导入, 验证可查)
    code, data = api_call(H_admin, "get", f"/sites/{site_id}")
    row["n_points"] = data.get("n_points") if isinstance(data, dict) else None
    if code != 200:
        row["errors"].append(f"场地查询失败{code}")

    # 2. 数据质量检查(EDA 端点能返回即视为通过)
    code, _ = api_call(H_admin, "get", f"/sites/{site_id}/eda", params={"include": "boxplot"})
    row.setdefault("_quality", "pass" if code == 200 else f"fail({code})")

    # 3. KOS 生产轨
    code, kos_p = api_call(H_admin, "post", f"/sites/{site_id}/kos-diagnosis?track=prod&subset={subset}")
    if code == 200 and isinstance(kos_p, dict):
        row["prod_status"] = "pass"
        if kos_p.get("review_required"):
            row["review_required"] = True
    else:
        row["prod_status"] = f"fail({code})"
        row["errors"].append(f"KOS生产{code}")

    # 4. KOS 生态轨
    code, kos_e = api_call(H_admin, "post", f"/sites/{site_id}/kos-diagnosis?track=eco&subset={subset}")
    row["eco_status"] = "pass" if (code == 200) else f"fail({code})"
    if code != 200:
        row["errors"].append(f"KOS生态{code}")

    # 5. 功能重构
    code, _ = api_call(H_admin, "post", f"/sites/{site_id}/evaluation")
    row["reconstruction_status"] = "pass" if code in (200, 201) else f"fail({code})"
    if code not in (200, 201):
        row["errors"].append(f"重构{code}")

    # 6. SSUI(含在 evaluation 端点)
    code, ev = api_call(H_admin, "get", f"/sites/{site_id}/evaluation")
    if code == 200 and isinstance(ev, dict):
        row["ssui_status"] = "pass" if ev.get("results", {}).get("ssui") else "no_data"
    else:
        row["ssui_status"] = f"fail({code})"

    # 7. 方案推荐
    code, _ = api_call(H_admin, "post", f"/sites/{site_id}/recommendation")
    row["recommendation_status"] = "pass" if code in (200, 201) else f"fail({code})"

    # 8. PDF 报告
    code, _ = api_call(H_admin, "post", f"/sites/{site_id}/reports?format=pdf")
    row["report_pdf_status"] = "pass" if code in (200, 201) else f"fail({code})"

    # 9. DOCX 报告
    code, _ = api_call(H_admin, "post", f"/sites/{site_id}/reports?format=docx")
    row["report_docx_status"] = "pass" if code in (200, 201) else f"fail({code})"

    # 10. 权限隔离(regulator 无 data:input, 尝试导入应被拒)
    if H_regulator:
        code, _ = api_call(H_regulator, "post", "/sites/import", data={"mapping_id": "test"})
        row["permission_403"] = "pass" if code in (401, 403) else f"leak({code})"
    else:
        row["permission_403"] = "skip(regulator未登录)"

    # 11. 地图(点位端点)
    code, _ = api_call(H_admin, "get", f"/sites/{site_id}/map-layers")
    row["map_status"] = "pass" if code == 200 else f"fail({code})"

    row["errors"] = "; ".join(row["errors"]) if row["errors"] else "无"
    return row


def validate_internal_site(internal, idx):
    """内部场地走 service 直调, 仅 KOS 双轨(诚实标注其余环节不适用)"""
    from backend.app.services.kos_service import run_kos_diagnosis
    sid = internal["source_id"][:10]
    subset = {"heavy_metal": "hm", "organic": "op"}.get(internal["pollution_type"], "all")
    row = {
        "site_id": f"INT-{idx}", "site_name": f"内部#{idx}({sid})",
        "pollution_type": internal["pollution_type"], "region": internal["province"],
        "n_points": len(internal["factors"]),
        "prod_status": "—", "eco_status": "—",
        "reconstruction_status": "N/A(内部)", "ssui_status": "N/A(内部)",
        "recommendation_status": "N/A(内部)", "report_pdf_status": "N/A(内部)",
        "report_docx_status": "N/A(内部)", "map_status": "N/A(内部)",
        "screenshot_status": "待节八", "permission_403": "N/A(内部)",
        "errors": [], "review_required": False,
    }
    try:
        kp = run_kos_diagnosis(internal["factors"], track="prod", subset=subset)
        row["prod_status"] = "pass" if "error" not in kp else f"fail"
        if kp.get("review_required"):
            row["review_required"] = True
    except Exception as e:
        row["prod_status"] = f"fail"
        row["errors"].append(f"KOS生产:{str(e)[:50]}")
    try:
        ke = run_kos_diagnosis(internal["factors"], track="eco", subset=subset)
        row["eco_status"] = "pass" if "error" not in ke else "fail"
    except Exception as e:
        row["eco_status"] = "fail"
        row["errors"].append(f"KOS生态:{str(e)[:50]}")
    row["errors"] = "; ".join(row["errors"]) if row["errors"] else "无"
    return row


def write_report(real_rows, int_rows):
    """生成 docs/reports/round6_15plus3_batch_validation.md"""
    out_dir = "docs/reports"
    os.makedirs(out_dir, exist_ok=True)
    all_rows = real_rows + int_rows
    n_real = len(real_rows)
    n_int = len(int_rows)
    n_prod_ok = sum(1 for r in all_rows if r["prod_status"] == "pass")
    n_eco_ok = sum(1 for r in all_rows if r["eco_status"] == "pass")
    n_recon_ok = sum(1 for r in real_rows if r["reconstruction_status"] == "pass")
    n_ssui_ok = sum(1 for r in real_rows if r["ssui_status"] == "pass")
    n_rec_ok = sum(1 for r in real_rows if r["recommendation_status"] == "pass")
    n_pdf_ok = sum(1 for r in real_rows if r["report_pdf_status"] == "pass")
    n_docx_ok = sum(1 for r in real_rows if r["report_docx_status"] == "pass")
    n_map_ok = sum(1 for r in real_rows if r["map_status"] == "pass")
    n_perm = sum(1 for r in real_rows if r.get("permission_403", "").startswith("pass"))
    n_review = sum(1 for r in all_rows if r["review_required"])

    lines = [
        f"# 第二阶段 15+3 场地批量验证报告 (Round 6)",
        f"",
        f"> 生成时间: {NOW} | 脚本: `scripts/run_round6_batch_validation.py`",
        f"> 真实场地: {n_real} 个(DB id 1/2/3, 走 API 全 11 环节)",
        f"> 内部场地: {n_int} 个(parquet 采样, 走 KOS service 直调, 诚实标注 N/A)",
        f"",
        f"## 一、总体通过率",
        f"",
        f"| 环节 | 通过/总数 | 通过率 |",
        f"|---|---|---|",
        f"| KOS 生产轨 | {n_prod_ok}/{n_real+n_int} | {n_prod_ok/(n_real+n_int)*100:.0f}% |",
        f"| KOS 生态轨 | {n_eco_ok}/{n_real+n_int} | {n_eco_ok/(n_real+n_int)*100:.0f}% |",
        f"| 功能重构 | {n_recon_ok}/{n_real} | {n_recon_ok/n_real*100:.0f}% (仅真实场地) |",
        f"| SSUI | {n_ssui_ok}/{n_real} | {n_ssui_ok/n_real*100:.0f}% (仅真实场地) |",
        f"| 方案推荐 | {n_rec_ok}/{n_real} | {n_rec_ok/n_real*100:.0f}% (仅真实场地) |",
        f"| PDF 报告 | {n_pdf_ok}/{n_real} | {n_pdf_ok/n_real*100:.0f}% |",
        f"| DOCX 报告 | {n_docx_ok}/{n_real} | {n_docx_ok/n_real*100:.0f}% |",
        f"| 地图端点 | {n_map_ok}/{n_real} | {n_map_ok/n_real*100:.0f}% |",
        f"| 权限隔离(403) | {n_perm}/{n_real} | {n_perm/n_real*100:.0f}% |",
        f"| 需人工复核 | {n_review}/{n_real+n_int} | — |",
        f"",
        f"## 二、逐场地明细(16 字段)",
        f"",
        f"| site_id | site_name | type | region | n_points | prod | eco | recon | ssui | recommend | pdf | docx | map | screenshot | errors | review |",
        f"|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in all_rows:
        lines.append(
            f"| {r['site_id']} | {r['site_name']} | {r['pollution_type']} | {r['region']} | {r['n_points']} | "
            f"{r['prod_status']} | {r['eco_status']} | {r['reconstruction_status']} | {r['ssui_status']} | "
            f"{r['recommendation_status']} | {r['report_pdf_status']} | {r['report_docx_status']} | "
            f"{r['map_status']} | {r['screenshot_status']} | {r['errors'][:40]} | {'是' if r['review_required'] else '否'} |"
        )
    lines += [
        f"",
        f"## 三、诚实说明",
        f"",
        f"1. **内部场地仅验证 KOS 双轨链路**: 功能重构/SSUI/方案推荐/报告/地图环节标注 N/A。",
        f"   原因: 内部合成场地无完整阈值上下文与采样点地理坐标, 重构/SSUI/报告无意义。",
        f"2. **权限隔离**: 用 regulator 账号(只读, 无 data:input)尝试导入, 期望返回 401/403。",
        f"3. **截图**: 本表 screenshot_status 标'待节八', 实际由 Playwright round6 脚本产出。",
        f"4. **不写'全部完成'**: 任何 fail/N/A 如实标注。",
        f"",
    ]
    with open(f"{out_dir}/round6_15plus3_batch_validation.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    # CSV
    pd.DataFrame(all_rows).to_csv(f"{out_dir}/round6_15plus3_batch_validation.csv", index=False, encoding="utf-8-sig")
    print(f"报告已写入: {out_dir}/round6_15plus3_batch_validation.md (+ .csv)")


def main():
    print("=" * 64)
    print("Round 6 批量验证 (15+3 场地 × 11 环节)")
    print("=" * 64)
    H_admin = login("admin")
    H_regulator = login("regulator")
    if not H_admin:
        print("❌ admin 登录失败, 请确认后端已启动且 seed_db 已执行")
        return

    real_configs = [
        (1, "云南个旧(HM)", "heavy_metal", "云南", "hm"),
        (2, "南京栖霞(OP)", "organic", "江苏", "op"),
        (3, "乡村复合(HM+OP)", "composite", "未知", "all"),
    ]
    real_rows = []
    print("\n── 3 真实场地(API 全环节)──")
    for sid, name, ptype, prov, subset in real_configs:
        print(f"  验证 {name} (id={sid})...")
        r = validate_real_site(H_admin, H_regulator, sid, name, ptype, prov, subset)
        real_rows.append(r)
        print(f"    prod={r['prod_status']} eco={r['eco_status']} recon={r['reconstruction_status']} perm={r.get('permission_403','—')}")

    print("\n── 15 内部场地(KOS service 直调)──")
    internal = sample_internal_sites(15)
    print(f"  采样到 {len(internal)} 个内部场地")
    int_rows = []
    from backend.app.services.kos_service import run_kos_diagnosis  # noqa: 提前确认可导入
    for i, s in enumerate(internal, 1):
        r = validate_internal_site(s, i)
        int_rows.append(r)
        print(f"  {r['site_name']}: prod={r['prod_status']} eco={r['eco_status']}")

    write_report(real_rows, int_rows)


if __name__ == "__main__":
    main()
