# 沙箱验证结果 + 本机测试/打包指引 — 2026-06-13

> 审计代理运行于隔离 Linux 沙箱(**无 docker / 无外网 / 无 fastapi·sqlalchemy·sklearn·shap / 无 hdiutil**)。
> 完整 pytest、`npm run build`、Docker、dmg 打包**无法在沙箱执行**(dmg 仅 macOS 可做),必须本机运行。下列如实区分"已验证"与"待本机"。

## 一、沙箱内已真实验证(通过)
| 项 | 结果 |
|---|---|
| 全量 `py_compile`(backend+ml+scripts) | ✅ 语法全通过 |
| 切分零泄漏复核(真实 splits CSV, DOI+Source 双键) | ✅ 0 对泄漏 |
| 三类真实场地映射解析 | ✅ 个旧 134点/14因子(HM)、栖霞 49点/18因子(OP)、乡村 8点/14因子(复合) |
| 切分泄漏纯算法测试(3 用例) | ✅ 全通过 |
| 字段标准化(省→大区/LandUse/污染类型) | ✅ |
| 重构/SSUI 计算轨迹 | ✅ 生产 47.64 不可行、SSUI 有值且 calculation_trace 保存 |
| 前端本地 import 解析 | ✅ 无缺失;14 页面 / 5 组件 |
| 代码/文档明文密钥扫描 | ✅ 无(仅 backend/.env,已 gitignore) |

## 二、🔴 必须裴总/codex 确认的发现:data/raw 真实训练表被替换
- `data/raw/真实数据集.csv` 当前为 **11690×136(F1–F127 中文特征 + 省市/经纬度/风险等级/标签/用地)**;
- 数据集源头 `数据集/2.模型训练集/真实数据集.csv` 仍是 **1119×34(原始真实训练集)**;
- 两者 sha256 不同(`b7ad8be5…` vs `83b1f106…`)→ **data/raw 内该文件已被覆盖**。
- 风险:① 违反"raw 不可变";② 文件名仍叫"真实数据集",若其中含合成/扩增行,则触及"模拟不得冒充真实"。
- 建议:确认该 136 列表的来源(真实 or 真实+合成扩增);若为扩增,应改名(如 `train_feature_v2.csv`)并显式标 `is_synthetic`/`evidence_level`,原始 1119×34 以不可变命名保留;泛化指标只用纯真实子集。

## 三、本机完整验证命令(沙箱跑不了的)
```bash
cd /Users/lensis/Claude/Projects/SRS
bash scripts/run_tests.sh            # 完整 pytest(需 venv)
cd frontend && npm run build && cd ..
cd backend && .venv/bin/python ../scripts/test_ai.py && cd ..   # GLM RAG, 429 降级
# Docker(由 codex 最终跑)
docker build -f backend/Dockerfile -t srs-backend .
docker run --rm srs-backend pytest -q
```

## 四、打包 macOS .dmg 指引(本机执行)
dmg 必须在 macOS 上做。推荐 **Tauri**(产物即 .dmg,自带壳):
```bash
# 1) 前端构建
cd frontend && npm run build && cd ..
# 2) 后端打成单可执行(sidecar)
cd backend && source .venv/bin/activate
pyinstaller --onefile --name srs-backend \
  --add-data "../data:data" --add-data "../ml:ml" \
  --collect-all sklearn --collect-all shap \
  app/main_entry.py    # 需写 uvicorn.run 入口(见 deployment_desktop §4)
cd ..
# 3) Tauri 壳(首次): npm create tauri-app, 配 dist 为前端、srs-backend 为 externalBin
cd src-tauri && cargo tauri build      # 产物: src-tauri/target/release/bundle/dmg/*.dmg
```
轻量替代(仅后端打 dmg 验证): `pip install create-dmg` 或 `brew install create-dmg`,对 PyInstaller 产物 `create-dmg SRS.dmg dist/`。
注意:① AI/天地图 key 留后端 `.env`,不进前端包;② 打包后天地图走后端瓦片代理,无需前端 key;③ PyInstaller 需 `--collect-all` 收齐 sklearn/shap/weasyprint 资源。

## 五、结论
沙箱可验证项全绿;**dmg/Docker/全量测试需本机**;**data/raw 训练表被替换一事须先确认**再继续,以免污染"真实泛化"口径。
