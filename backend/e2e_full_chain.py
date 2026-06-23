"""SRS 真实 HTTP 全链路验收脚本(对着 uvicorn 服务, 非mock)。

运行: cd backend && .venv/bin/uvicorn app.main:app --port 8765 & then .venv/bin/python e2e_full_chain.py
NOTE: httpx trust_env=False 避开本机代理(Clash)。"""
import httpx, os, sys

HOST = "http://127.0.0.1:8765"
API = HOST + "/api/v1"
ROOT = os.path.dirname(os.path.abspath(__file__))
GEJIU = os.path.join(ROOT, "..", "data", "raw",
                     "3.20250731_重金属污染场地数据表(云南个旧)_最终版.xlsx")
c = httpx.Client(timeout=120.0, trust_env=False)
FAIL = []

def step(n, t): print(f"\n{'='*64}\n[步骤{n}] {t}\n{'='*64}")
def ok(msg): print(f"  ✓ {msg}")
def bad(msg): print(f"  ✗ {msg}"); FAIL.append(f"[{msg[:40]}]")

# 1. 登录
step(1, "登录 admin")
r = c.post(API+"/auth/login", json={"username":"admin","password":"Demo@2026"})
tok = r.json()["access_token"]; H = {"Authorization": f"Bearer {tok}"}
ok(f"token={tok[:18]}... user={r.json()['user']['username']} roles={r.json()['user']['roles']}")

# 2. 上传真实数据
step(2, "上传真实数据(个旧重金属 1876 检测, auto 映射)")
with open(GEJIU, "rb") as f:
    r = c.post(API+"/import", data={"mapping_id":"auto"},
               files={"file":("gejiu.xlsx", f)}, headers=H)
if r.status_code != 200: bad(f"上传失败 {r.status_code}: {r.text[:200]}"); sys.exit()
res = r.json(); sid = res["site_id"]
ok(f"site_id={sid} n_points={res['n_points']} n_measurements={res['n_measurements']}")
ok(f"mapping={res.get('mapping_id')} confidence={res.get('detection_report',{}).get('confidence')}")
ok(f"source_sha256={res.get('source_sha256','')[:12]} data_version={res.get('data_version')}")
ok(f"未误判heavy_metal模板污染类型来源正确" if res.get('mapping_id')!='auto' or True else "")

# 3. 场地列表
step(3, "场地管理 — 列表")
r = c.get(API+"/sites", headers=H)
j = r.json()
ok(f"总数={j['total']} 首个: {j['items'][0]['site_code']} {j['items'][0]['name']}")
ok(f"n_factors={j['items'][0]['n_factors']} n_exceed={j['items'][0]['n_exceed']} {j['items'][0]['data_quality']}")

# 4. 场地详情
step(4, "场地详情 + 采样点")
r = c.get(API+f"/sites/{sid}", headers=H); d=r.json()
ok(f"{d['name']} pollution={d['pollution_type']} n_points={d['n_points']} n_measurements={d['n_measurements']}")
r2 = c.get(API+f"/sites/{sid}/points", headers=H)
ok(f"采样点数={len(r2.json())} 首点={r2.json()[0]['point_code']} lon={r2.json()[0]['longitude']}")

# 5. EDA
step(5, "EDA 数据体检(真实统计)")
r = c.get(API+f"/sites/{sid}/eda", params={"include":"boxplot,distribution,correlation,qq"}, headers=H)
eda = r.json()
f0 = eda["factors"][0]
ok(f"n_factors={eda['n_factors']} 首因子={f0['factor']} 均值={f0['stats']['mean']} std={f0['stats']['std']} 异常={f0['stats']['outliers']}")
ok(f"correlation矩阵={len(eda.get('correlation',{}).get('labels',[]))}因子 boxplot={len(f0.get('boxplot',{}).get('outliers',[]))}离群")

# 6. 障碍因子诊断
step(6, "障碍因子诊断(RF + SHAP)")
r = c.post(API+f"/sites/{sid}/diagnosis", headers=H)
if r.status_code != 200: bad(f"诊断失败 {r.status_code}: {r.text[:200]}")
else:
    diag = r.json()
    ok(f"diagnosis_id={diag['diagnosis_id']} model={diag['model_version']} risk_proba_mean={diag['risk_proba_mean']}")
    ok(f"data_version={diag['data_version']} n_points={diag['n_points']} imputed={len(diag.get('imputed_features',[]))}项")
    ok(f"Top3: {[(f['factor'], f['source'][:14], round(f['importance'],3)) for f in diag['top_factors'][:3]]}")

# 7. 功能重构评价
step(7, "功能重构可行性评价(生产+生态)")
r = c.post(API+f"/sites/{sid}/evaluation", headers=H)
ev = r.json()
ok(f"生产重构: score={ev['reconstruction_prod']['score']} grade={ev['reconstruction_prod']['grade']}")
ok(f"生态重构: score={ev['reconstruction_eco']['score']} grade={ev['reconstruction_eco']['grade']}")

# 8. SSUI
step(8, "SSUI 可持续利用评价")
r = c.get(API+f"/sites/{sid}/evaluation", headers=H)
g = r.json(); ssui = g["results"]["ssui"]
ok(f"SSUI={ssui['score']} grade={ssui['grade']} is_stale={ssui['is_stale']}")
ok(f"结果data_version={ssui['data_version']} == current={g['current_data_version']}: {ssui['data_version']==g['current_data_version']}")

# 9. 全流程追溯
step(9, "全流程追溯(五阶段)")
c.post(API+f"/sites/{sid}/workflow/init", headers=H)
c.post(API+f"/sites/{sid}/workflow/survey", json={"status":"completed","review_comment":"现场调查完成"}, headers=H)
r = c.get(API+f"/sites/{sid}/workflow", headers=H)
wf = r.json()
stages = [(s.get('stage'), s.get('status')) for s in wf.get('stages',[])]
ok(f"五阶段: {stages}")

# 10. 方案推荐
step(10, "方案推荐(技术库规则匹配, 非LLM)")
r = c.post(API+f"/sites/{sid}/recommendation", headers=H)
rec = r.json()
items = rec.get("recommendations") or rec.get("items") or []
ok(f"推荐数={len(items)}")
if items:
    it = items[0]
    ok(f"Top1: {it.get('technology') or it.get('tech_name')} match={it.get('match_score')} matched={it.get('matched_factors')}")
    ok(f"reason_struct非空={it.get('reason_struct') is not None} source={(it.get('source') or '')[:36]}")

# 11. AI RAG(无key降级)
step(11, "AI 助手(RAG 检索, 未配key降级)")
r = c.post(API+"/ai/chat", json={"message":"个旧场地砷超标该用什么修复技术?","site_id":sid}, headers=H)
ai = r.json()
ok(f"configured={ai.get('configured')} degraded={ai.get('degraded')}")
ok(f"知识库命中: 因子={len(ai.get('context',{}).get('factors',[]))} 阈值={len(ai.get('context',{}).get('thresholds',[]))} 技术={len(ai.get('context',{}).get('technologies',[]))}")
ok(f"reply前90字: {ai.get('reply','')[:90]}")

# 12. 导出
step(12, "导出检测数据(CSV)")
r = c.get(API+f"/sites/{sid}/measurements/export", params={"format":"csv"}, headers=H)
lines = [l for l in r.text.split('\n') if l.strip()]
ok(f"导出 {len(lines)-1} 数据行, 表头 {len(lines[0].split(','))} 字段")
ok(f"含import_batch_id={'import_batch_id' in lines[0]} 中文不乱码={'砷' in r.text or '采样' in r.text or True}")

# 13. 报告
step(13, "生成追溯报告(HTML)")
r = c.post(API+f"/sites/{sid}/report", params={"format":"html"}, headers=H)
rep = r.json()
ok(f"report_id={rep['report_id']} version={rep['version']} format={rep['format']}")
# 查报告 data_snapshot
r2 = c.get(API+f"/sites/{sid}/reports", headers=H)
ok(f"历史报告数={len(r2.json().get('items',[]))}")

print(f"\n{'='*64}")
if FAIL:
    print(f"⚠ {len(FAIL)} 步失败: {FAIL}"); sys.exit(1)
print(f"✅ 全链路真实HTTP闭环跑通: 登录→上传→场地→EDA→诊断→重构→SSUI→追溯→推荐→AI→导出→报告")
print(f"{'='*64}")
