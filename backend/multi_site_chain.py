"""真实多场地批量全链路验收(4 个从全国数据集切分的真实场地)。

运行: cd backend && .venv/bin/uvicorn app.main:app --port 8765 & \
      .venv/bin/python multi_site_chain.py
"""
import glob, httpx, os
API = "http://127.0.0.1:8765/api/v1"
c = httpx.Client(timeout=180, trust_env=False)
tok = c.post(API+"/auth/login", json={"username":"admin","password":"Demo@2026"}).json()["access_token"]
H = {"Authorization": f"Bearer {tok}"}

slices = sorted(glob.glob("../data/test_datasets/site_*.xlsx"))
print(f"=== 真实多场地批量验收: {len(slices)} 个切分数据集 ===\n")
rows = []
for sp in slices:
    label = os.path.basename(sp).replace(".xlsx","")
    with open(sp, "rb") as f:
        r = c.post(API+"/import", data={"mapping_id":"auto"},
                   files={"file":(label+".xlsx", f)}, headers=H)
    if r.status_code != 200:
        print(f"✗ {label} 导入失败: {r.text[:120]}"); continue
    j = r.json(); sid = j["site_id"]
    # 诊断
    d = c.post(API+f"/sites/{sid}/diagnosis", headers=H).json()
    top1 = d["top_factors"][0] if d.get("top_factors") else {}
    # 评价
    ev = c.post(API+f"/sites/{sid}/evaluation", headers=H).json()
    # 推荐
    rec = c.post(API+f"/sites/{sid}/recommendation", headers=H).json().get("recommendations",[])
    r0 = rec[0] if rec else {}
    rows.append({
        "场地": label, "sid": sid, "点数": j["n_points"], "检测": j["n_measurements"],
        "sha": j.get("source_sha256","")[:8], "Top因子": f"{top1.get('factor')}({top1.get('source','')[:8]})",
        "生产": ev["reconstruction_prod"]["grade"], "生态": ev["reconstruction_eco"]["grade"],
        "SSUI": ev["ssui"]["ssui"], "推荐数": len(rec),
        "Top1技术": (r0.get("tech_name") or r0.get("technology") or "—")[:18],
    })
    print(f"✓ {label}: {j['n_points']}点/{j['n_measurements']}检 sha={rows[-1]['sha']} Top={rows[-1]['Top因子']} SSUI={rows[-1]['SSUI']}")

print(f"\n{'='*90}\n{'场地':<26}{'点':>4}{'检':>6}{'Top因子':<16}{'生产':<8}{'生态':<8}{'SSUI':>7}{'推荐':>5}{'Top1技术':<20}")
print("-"*90)
for r in rows:
    print(f"{r['场地']:<26}{r['点数']:>4}{r['检测']:>6}{r['Top因子']:<16}{r['生产']:<8}{r['生态']:<8}{r['SSUI']:>7}{r['推荐数']:>5}{r['Top1技术']:<20}")
print(f"{'='*90}")
print(f"✅ {len(rows)}/{len(slices)} 真实切分场地全链路跑通(导入→诊断→重构→SSUI→推荐)")
