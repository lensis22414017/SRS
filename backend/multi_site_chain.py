"""真实多场地批量鲁棒性验收(15 切片: 4 HM + 5 OP + 6 HM+OP)。

每步 try/except 记录成败, 暴露系统对有机/复合/小样本的真实支持情况。
运行: cd backend && .venv/bin/uvicorn app.main:app --port 8765 & \
      .venv/bin/python multi_site_chain.py
"""
import glob, httpx, os, re, time
API = "http://127.0.0.1:8765/api/v1"
c = httpx.Client(timeout=300, trust_env=False)
tok = c.post(API+"/auth/login", json={"username":"admin","password":"Demo@2026"}).json()["access_token"]
H = {"Authorization": f"Bearer {tok}"}

def try_post(path, **kw):
    try:
        r = c.post(API+path, headers=H, **kw)
        if r.status_code == 200: return r.json(), None
        return None, f"HTTP{r.status_code}:{r.text[:80]}"
    except Exception as e: return None, f"{type(e).__name__}:{e}"


def ttype(fn):
    if "HM+OP" in fn: return "复合"
    if "_OP_" in fn: return "有机"
    return "重金属"

slices = sorted(glob.glob("../data/test_datasets/site_*.xlsx"))
print(f"=== 真实多场地鲁棒性验收: {len(slices)} 切片 ===\n")
rows = []
t0 = time.time()
for sp in slices:
    label = os.path.basename(sp).replace(".xlsx","")
    tt = ttype(label)
    row = {"场地": label, "类型": tt, "点": "—", "检": "—", "导入": "✗",
           "诊断": "✗", "评价": "✗", "SSUI": "—", "推荐": "✗", "Top": "—", "备注": ""}
    with open(sp, "rb") as f:
        j, err = try_post("/import", data={"mapping_id":"auto"},
                          files={"file":(label+".xlsx", f)})
    if err: row["备注"] = f"导入{err}"; rows.append(row); print(f"✗ {label} 导入失败 {err}"); continue
    sid = j["site_id"]; row["导入"]="✓"; row["点"]=j["n_points"]; row["检"]=j["n_measurements"]
    row["备注"] = f"sha={j.get('source_sha256','')[:6]}"
    # 诊断
    d, err = try_post(f"/sites/{sid}/diagnosis")
    if err: row["诊断"]=f"✗{err[:25]}"; row["备注"]+=" 诊断"+err[:30]
    else:
        row["诊断"]="✓"
        tf = d.get("top_factors",[])
        row["Top"] = (tf[0]["factor"]+"("+tf[0].get("source","")[:6]+")") if tf else "无Top"
    # 评价
    ev, err = try_post(f"/sites/{sid}/evaluation")
    if err: row["评价"]=f"✗{err[:25]}"; row["备注"]+=" 评价"+err[:30]
    else:
        row["评价"]="✓"; row["SSUI"]=ev["ssui"]["ssui"]
    # 推荐
    rec, err = try_post(f"/sites/{sid}/recommendation")
    if err: row["推荐"]=f"✗{err[:25]}"
    else: row["推荐"]=f"✓{len(rec.get('recommendations',[]))}条"
    rows.append(row)
    print(f"✓ {label} [{tt}] {row['点']}点/{row['检']}检 导入{row['导入']} 诊断{row['诊断']} 评价{row['评价']} SSUI={row['SSUI']} 推荐{row['推荐']}")

print(f"\n{'='*110}\n耗时 {time.time()-t0:.0f}s")
print(f"{'场地':<28}{'类型':<6}{'点':>4}{'检':>6}{'导入':>5}{'诊断':>7}{'评价':>7}{'SSUI':>8}{'推荐':>9}  {'Top因子':<14}备注")
print("-"*110)
for tt_order in ["重金属","有机","复合"]:
    for r in [x for x in rows if x["类型"]==tt_order]:
        print(f"{r['场地']:<28}{r['类型']:<6}{r['点']:>4}{r['检']:>6}{r['导入']:>5}{str(r['诊断']):>7}{str(r['评价']):>7}{str(r['SSUI']):>8}{str(r['推荐']):>9}  {r['Top']:<14}{r['备注']}")
print(f"{'='*110}")
n_ok = sum(1 for r in rows if r['导入']=='✓' and '✗' not in str(r['诊断']) and '✗' not in str(r['评价']))
print(f"全链路无错: {n_ok}/{len(rows)}; 其余见备注(系统鲁棒性边界)")
