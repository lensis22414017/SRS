"""prepare.py (L1 锁定) — SRS autoresearch 评估基础设施。

定义客观指标 + evaluate() 在固定预算内跑 15 真实切片全链路。
agent 只改 L2(ml/recommend/engine.py 等), 本文件锁定保证评估可比。

指标(15切片: 4HM + 5OP + 6HM+OP):
  pass_rate          导入+诊断+评价+推荐 HTTP 全 200 的场地比例
  recommend_coverage 有≥1条推荐的比例 (OP缺口: baseline 0)
  diagnosis_top_valid 诊断有有效Top因子(非"无Top")的比例
  ssui_valid         SSUI 非 None 的比例
  op_recommend_avg   OP场地平均推荐数 (baseline 0, 目标≥3)
  overall            加权综合(0-1), 优化目标
"""
import glob, os, subprocess, sys, time, signal
import httpx

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BACKEND = os.path.join(ROOT, "backend")
SLICES = sorted(glob.glob(os.path.join(ROOT, "data", "test_datasets", "site_*.xlsx")))
BUDGET_SECONDS = 180  # 15切片全链路一次
PORT = 8766  # autoresearch 专用端口, 避免与手动测试冲突

PROBES = ["个旧场地砷超标"]  # AI 探针(轻量, 不计入主指标)


def _ttype(fn):
    if "HM+OP" in fn: return "复合"
    if "_OP_" in fn: return "有机"
    return "重金属"


def start_fresh_server(db_path):
    """启动干净 uvicorn 服务(显式env+绝对路径DB), 返回 (proc, httpx_client)。"""
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{db_path}"
    for p in (db_path, db_path + "-wal", db_path + "-shm"):
        if os.path.exists(p):
            os.remove(p)
    py = os.path.join(BACKEND, ".venv", "bin", "python")
    subprocess.run([py, "-m", "app.db.bootstrap"], cwd=BACKEND, env=env,
                   capture_output=True, timeout=60)
    subprocess.run([py, "-m", "app.db.load_kb"], cwd=BACKEND, env=env,
                   capture_output=True, timeout=60)
    proc = subprocess.Popen(
        [py, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
         "--port", str(PORT), "--no-access-log"],
        cwd=BACKEND, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    c = httpx.Client(timeout=300, trust_env=False)
    for _ in range(20):
        try:
            if c.get(f"http://127.0.0.1:{PORT}/health").status_code == 200:
                return proc, c
        except Exception:
            time.sleep(0.5)
    raise RuntimeError("服务启动超时")


def stop_server(proc):
    try:
        proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=10)
    except Exception:
        proc.kill()


def evaluate() -> dict:
    """跑15切片全链路, 返回指标 dict(含 overall)。固定预算 BUDGET_SECONDS。"""
    db = os.path.join(BACKEND, "autoresearch_eval.db")
    proc, c = start_fresh_server(db)
    try:
        API = f"http://127.0.0.1:{PORT}/api/v1"
        tok = c.post(API + "/auth/login",
                     json={"username": "admin", "password": "Demo@2026"}).json()["access_token"]
        H = {"Authorization": f"Bearer {tok}"}
        recs = []
        for sp in SLICES:
            label = os.path.basename(sp).replace(".xlsx", "")
            tt = _ttype(label)
            r = {"场地": label, "类型": tt, "pass": False, "rec_n": 0,
                 "top_valid": False, "ssui_valid": False}
            try:
                with open(sp, "rb") as f:
                    ir = c.post(API + "/import", data={"mapping_id": "auto"},
                                files={"file": (label + ".xlsx", f)}, headers=H, timeout=120)
                    if ir.status_code != 200:
                        recs.append(r); continue
                    sid = ir.json()["site_id"]
                dr = c.post(API + f"/sites/{sid}/diagnosis", headers=H, timeout=120)
                if dr.status_code != 200:
                    recs.append(r); continue
                d = dr.json()
                tf = d.get("top_factors", [])
                r["top_valid"] = bool(tf) and tf[0].get("factor") not in (None, "")
                er = c.post(API + f"/sites/{sid}/evaluation", headers=H, timeout=120)
                if er.status_code != 200:
                    recs.append(r); continue
                ev = er.json()
                ssui = ev.get("ssui", {}).get("ssui")
                r["ssui_valid"] = ssui is not None
                rr = c.post(API + f"/sites/{sid}/recommendation", headers=H, timeout=120)
                rec_n = len(rr.json().get("recommendations", [])) if rr.status_code == 200 else 0
                r["rec_n"] = rec_n
                r["pass"] = True  # 全 HTTP 200
            except Exception as e:
                r["err"] = str(e)[:60]
            recs.append(r)
    finally:
        c.close()
        stop_server(proc)
        for p in (db, db + "-wal", db + "-shm"):
            if os.path.exists(p):
                try: os.remove(p)
                except OSError: pass

    n = len(recs) or 1
    op = [r for r in recs if r["类型"] == "有机"]
    metrics = {
        "pass_rate": sum(r["pass"] for r in recs) / n,
        "recommend_coverage": sum(r["rec_n"] > 0 for r in recs) / n,
        "diagnosis_top_valid": sum(r["top_valid"] for r in recs) / n,
        "ssui_valid": sum(r["ssui_valid"] for r in recs) / n,
        "op_recommend_avg": (sum(r["rec_n"] for r in op) / len(op)) if op else 0,
        "n_slices": len(recs),
    }
    # overall 加权: 推荐覆盖(核心缺口) + 诊断有效 + ssui有效 + pass
    metrics["overall"] = round(
        0.35 * metrics["recommend_coverage"] +
        0.25 * min(metrics["op_recommend_avg"] / 3, 1) +  # OP推荐目标≥3
        0.20 * metrics["diagnosis_top_valid"] +
        0.10 * metrics["ssui_valid"] +
        0.10 * metrics["pass_rate"], 4)
    metrics["_recs"] = recs
    return metrics


if __name__ == "__main__":
    m = evaluate()
    print(f"\n=== SRS autoresearch baseline 指标 (n={m['n_slices']}) ===")
    for k in ("pass_rate", "recommend_coverage", "diagnosis_top_valid",
              "ssui_valid", "op_recommend_avg", "overall"):
        print(f"  {k}: {m[k]}")
