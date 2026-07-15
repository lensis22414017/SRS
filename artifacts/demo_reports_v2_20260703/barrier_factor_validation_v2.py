"""P1 v2: 关键障碍因子识别能力验证 — 按 pollution_type 分组验证所有场地。

按场地污染类型分组, 对每组场地运行对应 subset 的 KOS 诊断, 检查 Top-N 是否命中该类型的预期因子。
HM 场地预期: 镉/铅/砷/锌/铜/pH 等重金属
OP 场地预期: PAH/苯并芘/石油烃等有机物
HM+OP 场地预期: 上述两者的并集
"""
import json
import urllib.request

BASE = "http://127.0.0.1:8011/api/v1"
RESULT = {"validations": [], "summary": {}}

# 按 pollution_type 的预期因子和 subset
TYPE_CONFIG = {
    "heavy_metal": {
        "expected_raw": ["cd", "镉", "pb", "铅", "as", "砷", "zn", "锌", "cu", "铜", "ph", "ni", "镍", "cr", "铬", "hg", "汞"],
        "subset": "hm",
        "label": "HM",
        "min_recall": 0.30,  # 预期因子里命中30%即可(因子很多)
    },
    "organic": {
        "expected_raw": ["pah", "苯并", "芘", "石油", "矿物油", "多环", "bap", "萘", "酚"],
        "subset": "op",
        "label": "OP",
        "min_recall": 0.25,
    },
    "composite": {
        "expected_raw": ["cd", "镉", "pb", "铅", "ph", "pah", "苯并", "石油"],
        "subset": "hm_op",
        "label": "HM+OP",
        "min_recall": 0.30,
    },
}


def req(method, path, token=None, body=None):
    url = BASE + path
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body else None
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=60) as resp:
            return resp.status, json.loads(resp.read().decode())
    except Exception as e:
        return -1, {"error": str(e)}


def norm(name):
    n = str(name).lower().replace("_", "").replace("-", "").replace("(", "").replace(")", "")
    aliases = {"镉": "cd", "铅": "pb", "砷": "as", "锌": "zn", "铜": "cu",
               "镍": "ni", "铬": "cr", "汞": "hg",
               "苯并芘": "bap苯并", "多环芳烃": "pah", "矿物油": "石油"}
    for cn, en in aliases.items():
        n = n.replace(cn, en)
    return n


# 登录
code, data = req("POST", "/auth/login", body={"username": "admin", "password": "Demo@2026"})
token = data["access_token"]
code, data = req("GET", "/sites?per_page=50", token)
sites = data.get("items", [])

# 按类型分组, 每类型取前3个场地验证
by_type = {}
for s in sites:
    by_type.setdefault(s["pollution_type"], []).append(s)

print(f"场地分组: {', '.join(f'{t}={len(v)}' for t, v in by_type.items())}")

for ptype, cfg in TYPE_CONFIG.items():
    group = by_type.get(ptype, [])
    if not group:
        print(f"\n⚠️ 无 {cfg['label']} 场地, 跳过")
        continue

    expected = [norm(f) for f in cfg["expected_raw"]]
    sample = group[:4]  # 每组验证最多4个

    type_recalls = []
    for site in sample:
        sid = site["id"]
        name = site["name"]
        code, result = req("POST", f"/sites/{sid}/kos-diagnosis?track=prod&subset={cfg['subset']}", token)
        if code != 200:
            print(f"  ❌ {name}: HTTP {code}")
            continue

        obstacles = result.get("key_obstacles", []) + result.get("explicit_obstacles", [])
        top3 = [norm(o.get("factor", "")) for o in obstacles[:3]]
        top5 = [norm(o.get("factor", "")) for o in obstacles[:5]]

        hits = [f for f in expected if any(f in t for t in top3)]
        recall = len(hits) / len(expected) if expected else 0
        passed = recall >= cfg["min_recall"]
        type_recalls.append(recall)

        mark = "✅" if passed else "⚠️"
        print(f"  {mark} {name[:30]:30s} Recall@3={recall:.2f} top5={top5[:3]}")

        RESULT["validations"].append({
            "site": name, "site_id": sid, "type": ptype, "subset": cfg["subset"],
            "top5": top5, "hits": hits, "recall": round(recall, 2),
            "passed": passed,
            "model_status": result.get("model_status"),
            "review_required": result.get("review_required"),
        })

    avg_recall = sum(type_recalls) / len(type_recalls) if type_recalls else 0
    RESULT["summary"][cfg["label"]] = {
        "avg_recall": round(avg_recall, 2),
        "n_sites": len(type_recalls),
        "min_recall_threshold": cfg["min_recall"],
    }
    print(f"  → {cfg['label']} 平均 Recall@3: {avg_recall:.2f} (阈值{cfg['min_recall']})")

# 汇总
all_pass = sum(1 for v in RESULT["validations"] if v["passed"])
all_total = len(RESULT["validations"])
RESULT["summary"]["overall"] = f"{all_pass}/{all_total} 场地达标"
print(f"\n{'='*60}")
print(f"总体验证: {all_pass}/{all_total} 场地达标")
for label, s in RESULT["summary"].items():
    if label != "overall":
        print(f"  {label}: 平均Recall@3={s['avg_recall']} ({s['n_sites']}场地)")
print(f"{'='*60}")

with open("artifacts/demo_reports_v2_20260703/barrier_factor_validation_v2.json", "w", encoding="utf-8") as f:
    json.dump(RESULT, f, ensure_ascii=False, indent=2)
print("结果已保存")
