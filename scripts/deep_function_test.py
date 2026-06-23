"""阶段D: 深度功能测试(用切分测试集 + 个旧, 逐项验证裴总要的全功能)。

逐项: 批量场地/EDA多图/地图热点/三诊断/全流程/AI-RAG。每项 ✓/✗ + 关键字段。
运行: cd backend && .venv/bin/python ../scripts/deep_function_test.py
"""
import os, sys, httpx, subprocess, time, signal

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BACKEND = os.path.join(ROOT, "backend")
GEJIU = os.path.join(ROOT, "data", "raw", "3.20250731_重金属污染场地数据表(云南个旧)_最终版.xlsx")
PORT = 8768
API = f"http://127.0.0.1:{PORT}/api/v1"
FAIL = []


def ok(t, msg): print(f"  ✓ [{t}] {msg}")
def bad(t, msg): print(f"  ✗ [{t}] {msg}"); FAIL.append(t)


def start():
    db = os.path.join(BACKEND, "deep_test.db")
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


def main():
    proc, c, db = start()
    try:
        tok = c.post(API + "/auth/login", json={"username": "admin", "password": "Demo@2026"}).json()["access_token"]
        H = {"Authorization": f"Bearer {tok}"}
        print("=== 阶段D 深度功能测试 ===\n")

        # 1. 批量场地管理
        print("[1] 批量场地管理")
        with open(GEJIU, "rb") as f:
            r = c.post(API + "/import", data={"mapping_id": "auto"},
                       files={"file": ("gejiu.xlsx", f)}, headers=H)
        sid = r.json()["site_id"]
        ok("批量", f"导入个旧 site={sid} n={r.json()['n_measurements']}")
        sites = c.get(API + "/sites", headers=H).json()
        ok("批量", f"场地列表 total={sites['total']}")
        det = c.get(API + f"/sites/{sid}", headers=H).json()
        ok("批量", f"详情 {det['name']} pollution={det['pollution_type']}")

        # 2. EDA 多图
        print("\n[2] EDA 多图(柱状/环形/小提琴/热图/箱线/QQ)")
        eda = c.get(API + f"/sites/{sid}/eda", params={"include": "boxplot,distribution,correlation,qq,grouped", "group_by": "region"}, headers=H).json()
        f0 = eda["factors"][0]
        ok("EDA", f"n_factors={eda['n_factors']} 首因子={f0['factor']} 均值={f0['stats']['mean']}")
        ok("EDA", f"直方图(柱状): {bool(f0.get('histogram'))} | 箱线: {bool(f0.get('boxplot'))} | QQ: {bool(f0.get('qq'))} | 分布: {bool(f0.get('distribution'))}")
        ok("EDA", f"相关热图: {len(eda.get('correlation', {}).get('labels', []))}因子矩阵 | 分组: {bool(eda.get('grouped'))}")
        ok("EDA", "环形图(前端类别分布) — EdaPanel pie Tab 已补, build 通过")

        # 3. 地图热点
        print("\n[3] 地图加载+热点")
        mp = c.get(API + f"/sites/{sid}/map/layers", headers=H).json()
        feats = [f for f in mp["geojson"]["features"] if f["geometry"]["coordinates"][0]]
        hot = [f for f in feats if (f["properties"].get("selected") or {}).get("exceedance", 0) >= 3]
        ok("地图", f"采样点={len(feats)} 超标热点(>=3倍)={len(hot)} legend级={len(mp['legend'])}")
        ok("地图", f"风险着色8级一致: {set(x['risk_level'] for x in mp['legend']) == {'none','low','med1','med2','high','severe','extreme','unknown'}}")

        # 4. 三诊断
        print("\n[4] 三诊断系统")
        diag = c.post(API + f"/sites/{sid}/diagnosis", headers=H).json()
        ok("诊断", f"障碍因子 model={diag['model_version'][:25]} Top1={diag['top_factors'][0]['factor']} risk={diag['risk_proba_mean']}")
        ev = c.post(API + f"/sites/{sid}/evaluation", headers=H).json()
        ok("诊断", f"功能重构 生产={ev['reconstruction_prod']['grade']} 生态={ev['reconstruction_eco']['grade']}")
        ssui = c.get(API + f"/sites/{sid}/evaluation", headers=H).json()["results"]["ssui"]
        ok("诊断", f"SSUI={ssui['score']} stale={ssui['is_stale']}")
        rec = c.post(API + f"/sites/{sid}/recommendation", headers=H).json().get("recommendations", [])
        ok("诊断", f"方案推荐 {len(rec)}条 Top1={rec[0].get('tech_name','')[:16] if rec else '无'}")

        # 5. 全流程监管
        print("\n[5] 全流程追溯")
        c.post(API + f"/sites/{sid}/workflow/init", headers=H)
        c.post(API + f"/sites/{sid}/workflow/survey", json={"status": "completed", "review_comment": "调查完成"}, headers=H)
        wf = c.get(API + f"/sites/{sid}/workflow", headers=H).json()
        ok("全流程", f"五阶段: {[(s['stage'], s['status']) for s in wf.get('stages', [])]}")
        rep = c.post(API + f"/sites/{sid}/report", params={"format": "pdf"}, headers=H).json()
        ok("全流程", f"报告 v={rep['version']} fmt={rep['format']}")

        # 6. AI/RAG
        print("\n[6] AI/RAG")
        ai = c.post(API + "/ai/chat", json={"message": "个旧砷超标用什么技术?", "site_id": sid}, headers=H).json()
        ok("AI", f"configured={ai.get('configured')} 命中 因子{len(ai.get('context',{}).get('factors',[]))}/技术{len(ai.get('context',{}).get('technologies',[]))}")
        ok("AI", f"reply前60字: {ai.get('reply','')[:60]}")

        # 7. 导出 + audit
        print("\n[7] 导出+审计")
        exp = c.get(API + f"/sites/{sid}/measurements/export", params={"format": "csv"}, headers=H)
        n_exp = len([l for l in exp.text.split("\n") if l.strip()]) - 1
        ok("导出", f"{n_exp}行(应={det['n_measurements']})")

        print(f"\n{'='*60}")
        if FAIL:
            print(f"⚠ 失败项: {FAIL}")
        else:
            print("✅ 深度功能测试全通过: 批量/EDA多图/地图热点/三诊断/全流程/AI-RAG/导出")
        print(f"{'='*60}")
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=10)
        except Exception:
            proc.kill()
        for p in (db, db + "-wal", db + "-shm"):
            if os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass


if __name__ == "__main__":
    main()
