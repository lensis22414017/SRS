"""鲁棒性批量测试(裴总: 再切5 OP + 5 HM+OP 场地测系统鲁棒性, 方法同 deep_function_test)。

逐场地: 导入→诊断→评价→推荐→SSUI, 统计成功率/有机SHAP/推荐数/SSUI有效率。
运行: cd backend && .venv/bin/python ../scripts/robustness_test.py
"""
import os, sys, glob, httpx, subprocess, time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BACKEND = os.path.join(ROOT, "backend")
PORT = 8770
API = f"http://127.0.0.1:{PORT}/api/v1"

# 5 OP + 5 HM+OP (裴总指定配额)
OP_SITES = sorted(glob.glob(os.path.join(ROOT, "data", "test_datasets", "site_*_OP_*.xlsx")))[:5]
HMOP_SITES = sorted(glob.glob(os.path.join(ROOT, "data", "test_datasets", "site_*_HM+OP_*.xlsx")))[:5]


def start():
    db = os.path.join(BACKEND, "robust_test.db")
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{db}"
    if os.path.exists(db):
        os.remove(db)
    subprocess.run([os.path.join(BACKEND, ".venv", "bin", "python"), "-m", "app.db.bootstrap"],
                   cwd=BACKEND, env=env, capture_output=True, timeout=60)
    subprocess.run([os.path.join(BACKEND, ".venv", "bin", "python"), "-m", "app.db.load_kb"],
                   cwd=BACKEND, env=env, capture_output=True, timeout=60)
    proc = subprocess.Popen([os.path.join(BACKEND, ".venv", "bin", "python"), "-m", "uvicorn",
                             "app.main:app", "--port", str(PORT), "--no-access-log"],
                            cwd=BACKEND, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    c = httpx.Client(timeout=200, trust_env=False)
    for _ in range(20):
        try:
            if c.get(f"http://127.0.0.1:{PORT}/health").status_code == 200:
                return proc, c, db
        except Exception:
            time.sleep(0.5)
    raise RuntimeError("服务启动超时")


def test_site(c, H, path, tag):
    """单场地全链路: 返回结果字典。"""
    r = {"tag": tag, "file": os.path.basename(path)}
    try:
        with open(path, "rb") as f:
            imp = c.post(API + "/import", data={"mapping_id": "auto"},
                         files={"file": (os.path.basename(path), f)}, headers=H, timeout=120)
        if imp.status_code != 200:
            r["status"] = f"导入失败{imp.status_code}"; return r
        sid = imp.json()["site_id"]
        r["n"] = imp.json().get("n_measurements", 0)
        diag = c.post(API + f"/sites/{sid}/diagnosis", headers=H, timeout=120).json()
        r["top1"] = diag.get("top_factors", [{}])[0].get("factor", "") if diag.get("top_factors") else ""
        tops = diag.get("top_factors", [])
        # 有机SHAP命中(因子名含PAH/TPH/BaP/DDT/PCB/HCH/OCP)
        org_keywords = ["PAH", "TPH", "BaP", "DDT", "PCB", "HCH", "OCP", "苯", "芘", "烃", "氯", "滴滴"]
        r["org_in_top"] = [t["factor"] for t in tops if any(k in str(t.get("factor", "")) for k in org_keywords)][:3]
        ev = c.post(API + f"/sites/{sid}/evaluation", headers=H, timeout=120).json()
        r["prod_grade"] = ev.get("reconstruction_prod", {}).get("grade", "")
        r["eco_grade"] = ev.get("reconstruction_eco", {}).get("grade", "")
        ssui = c.get(API + f"/sites/{sid}/evaluation", headers=H).json().get("results", {}).get("ssui", {})
        r["ssui"] = ssui.get("score")
        rec = c.post(API + f"/sites/{sid}/recommendation", headers=H, timeout=120).json().get("recommendations", [])
        r["n_rec"] = len(rec)
        r["status"] = "✓"
    except Exception as e:
        r["status"] = f"异常:{e}"
    return r


def main():
    proc, c, db = start()
    try:
        tok = c.post(API + "/auth/login", json={"username": "admin", "password": "Demo@2026"}).json()["access_token"]
        H = {"Authorization": f"Bearer {tok}"}
        print(f"=== 鲁棒性批量测试: {len(OP_SITES)} OP + {len(HMOP_SITES)} HM+OP ===\n")
        all_results = []
        for path in OP_SITES:
            res = test_site(c, H, path, "OP"); all_results.append(res)
            print(f"[OP] {res['file'][:35]:35} n={res.get('n','-'):>4} top={res.get('top1','')[:10]:10} 有机SHAP={len(res.get('org_in_top',[]))} 推荐={res.get('n_rec','-')} SSUI={res.get('ssui','-')} {res['status']}")
        for path in HMOP_SITES:
            res = test_site(c, H, path, "HM+OP"); all_results.append(res)
            print(f"[HM+OP] {res['file'][:35]:35} n={res.get('n','-'):>4} top={res.get('top1','')[:10]:10} 有机SHAP={len(res.get('org_in_top',[]))} 推荐={res.get('n_rec','-')} SSUI={res.get('ssui','-')} {res['status']}")

        # 汇总
        ok = [r for r in all_results if r["status"] == "✓"]
        op_r = [r for r in all_results if r["tag"] == "OP"]
        hmop_r = [r for r in all_results if r["tag"] == "HM+OP"]
        print(f"\n{'='*60}")
        print(f"总场地: {len(all_results)} | 成功: {len(ok)} ({len(ok)/len(all_results)*100:.0f}%)")
        print(f"OP场地: {len(op_r)} | 成功 {sum(1 for r in op_r if r['status']=='✓')} | 平均推荐 {sum(r.get('n_rec',0) for r in op_r)/max(len(op_r),1):.1f}")
        print(f"HM+OP: {len(hmop_r)} | 成功 {sum(1 for r in hmop_r if r['status']=='✓')} | 平均推荐 {sum(r.get('n_rec',0) for r in hmop_r)/max(len(hmop_r),1):.1f}")
        print(f"有机SHAP命中场地: {sum(1 for r in all_results if r.get('org_in_top'))}/{len(all_results)}")
        print(f"SSUI有效场地: {sum(1 for r in all_results if r.get('ssui') is not None)}/{len(all_results)}")
        fails = [r for r in all_results if r["status"] != "✓"]
        if fails:
            print(f"⚠ 失败: {[(r['file'][:25], r['status']) for r in fails]}")
        else:
            print("✅ 鲁棒性测试全通过: 10场地全部导入+诊断+评价+推荐成功")
        print(f"{'='*60}")
    finally:
        try:
            proc.terminate(); proc.wait(timeout=10)
        except Exception:
            proc.kill()
        for p in (db, db + "-wal", db + "-shm"):
            if os.path.exists(p):
                try: os.remove(p)
                except OSError: pass


if __name__ == "__main__":
    main()
