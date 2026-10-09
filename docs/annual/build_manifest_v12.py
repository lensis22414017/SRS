"""生成 MODEL_DEPENDENCY_MANIFEST_v1.2.0.md: 模型工件(LFS 指针/实体 sha256)、标准阈值与权重数据、后端/前端依赖。"""
import hashlib, json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
V = open(os.path.join(ROOT, "VERSION")).read().strip()

def sha(p):
    h = hashlib.sha256(); h.update(open(p, "rb").read()); return h.hexdigest()

def kind(p):
    head = open(p, "rb").read(200)
    return "LFS 指针" if head.startswith(b"version https://git-lfs") else "实体文件"

L = [f"# SRS v{V} 模型与依赖清单", "", "由 `docs/annual/build_manifest_v12.py` 从源码树生成。sha256 均为文件内容哈希（LFS 对象取指针中的 oid）。", "",
     "## 1 模型工件（课题一 KOS，p3_alpha，未重训）", "", "| 文件 | 类型 | 字节 | sha256 |", "|---|---|---|---|"]
d = os.path.join(ROOT, "ml", "artifacts", "p3_alpha")
for f in sorted(os.listdir(d)):
    p = os.path.join(d, f)
    if os.path.isfile(p):
        if kind(p) == "LFS 指针":
            t = dict(l.split(" ", 1) for l in open(p, encoding="utf-8").read().splitlines() if " " in l)
            L.append(f"| ml/artifacts/p3_alpha/{f} | LFS 对象 | {t['size']} | `{t['oid'].split(':')[1]}` |")
        else:
            L.append(f"| ml/artifacts/p3_alpha/{f} | 实体文件 | {os.path.getsize(p)} | `{sha(p)}` |")
L += ["", "## 2 方法与标准数据", "", "| 文件 | 用途 | sha256 |", "|---|---|---|"]
for rel, use in (("data/standards/gb36600_2018_official.csv", "GB 36600-2018 表1/表2 官方转录"),
                 ("data/standards/gb36600_2018_v12.csv", "GB 36600 运行时阈值表"),
                 ("data/standards/gb15618_2018_official.csv", "GB 15618-2018 表1–3 官方转录"),
                 ("data/standards/gb15618_2018_v12.csv", "GB 15618 运行时阈值表"),
                 ("data/standards/ssui_weights_pptx_v1.json", "课题三 SSUI 权重（方法 PPT 第13/14页）"),
                 ("ml/evaluation/reconstruction_m2025.py", "课题二 冻结方法 M-REC-2025"),
                 ("ml/models/feature_mapping.json", "特征映射")):
    p = os.path.join(ROOT, rel)
    L.append(f"| {rel} | {use} | `{sha(p) if os.path.exists(p) else '缺失'}` |")
L += ["", "## 3 后端依赖（backend/requirements.txt）", "", "```"] + open(os.path.join(ROOT, "backend", "requirements.txt"), encoding="utf-8").read().strip().splitlines() + ["```"]
pk = json.load(open(os.path.join(ROOT, "frontend", "package.json"), encoding="utf-8"))
L += ["", "## 4 前端依赖（frontend/package.json）", "", "| 包 | 版本 |", "|---|---|"]
L += [f"| {k} | {v} |" for k, v in sorted(pk.get("dependencies", {}).items())]
L += ["", "## 5 打包工具", "", "- Python 3.11（Windows 构建，actions/setup-python）；PyInstaller（`packaging/srs.spec`）", "- Inno Setup 6（`packaging/srs_setup.iss`）", "- Node 20（前端构建）", ""]
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "docs", "annual", f"MODEL_DEPENDENCY_MANIFEST_v{V}.md")
open(out, "w", encoding="utf-8").write("\n".join(L)); print(out, len(L))
