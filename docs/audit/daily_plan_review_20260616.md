# SRS 今日 PLAN / REVIEW — 2026-06-16

裴总,辛特助本次围绕"打包后压根不能用"的反馈,做了真因定位与修复(不是猜)。核心结论:**绝大多数"弱智问题"是同一类打包路径 bug + 模板靠人工选导致的连锁反应**,已逐项修复。

## [MODE: REVIEW] 真因定位(均经沙箱/代码核验)

| 现象 | 真因 | 证据 | 处理 |
|---|---|---|---|
| 导入后被强制塞进重金属场地 | 导入页只有一个模板下拉、默认 `yunnan_gejiu`;选错/默认时,解析器用个旧列名套别的文件,site 块写死重金属 | 沙箱复现:个旧文件配错模板→sheet 不存在报错;反向→静默落重金属 | 新增**按 sheet+列签名自动识别模板**,默认 auto;识别不到则提示用 Wizard |
| 年底/其他数据不能导入 | 同上 + 模板与文件结构不符时直接抛错 | parse 抛 `Worksheet not found` | auto 识别 + 失败信息明确指向自定义 Wizard |
| 数据可视化图全空 | `/eda` 依赖 `ml/eda/profile.py`,打包未收录;且路径 `../../../ml/eda` 打包后错到 Contents | 代码核查 + Resources 落点实测 | spec 收录 `ml/eda`;`/eda` 改用 `resource_root()` |
| 诊断无法实施 | `diagnosis_service` 运行时 `sys.path.insert(ml/models, ml/explain)` 但这些 .py 未打包;ROOT 路径错 | 包内 `Resources/ml` 仅 artifacts | spec 收录 `ml/{models,explain,recommend,evaluation,etl}`;服务 ROOT 全改 `resource_root()` |
| 矢量地图加载不出 | `map.py::_geo_root()` 用 `../../../` 打包后错到 Contents,geo 文件 503 | 代码核查 | `_geo_root()` 改 `resource_root()` |
| 真实(卫星)地图加载不出 | 高德瓦片代理需外网;`.env` 未打包,打包后无 key(高德其实免 key,但 tianditu 需 key) | map.py 优先 MBTiles>高德>天地图 | 路径修复后高德代理可用(需外网);天地图需 key 时给 503 提示 |
| AI 功能不可用 | `.env`(SiliconFlow/Qwen key)是 gitignore 文件,**不随 .app 分发**,打包后 AI 无配置 | spec datas 不含 .env | 已加**运行时 AI 配置**(系统管理→AI 模型配置,本机 JSON 存 key),默认 GLM 官方免费 |
| 黑屏 + `{"detail":"Not Found"}`(前序) | `sys._MEIPASS=Contents/Resources`,前端 dist 解析候选不全 | 实测 | 多候选解析 + 请求时重解析(已修,已验证生效) |

**共性根因**:多处用 `os.path.dirname(__file__)/../../..` 推项目根。打包成 `.app` 后 `__file__` 在 `Contents/Resources` 下,`../../..` 多爬一级到 `Contents`,而数据在 `Contents/Resources/...` → 全线 FileNotFoundError/503/空图。已统一为 `app.core.config.resource_root()`(探测含 `data/knowledge_base` 的真实落点)。

## [MODE: PLAN] 本次已落地改动

1. `backend/app/core/config.py` — 新增 `resource_root()`。
2. 路径统一(7+处):`pipeline / evaluation_service / recommend_service / diagnosis_service / report_service / db/load_kb / db/seed_db(seed_tech) / db/load_remediation_cases / api/map(_geo_root) / api/data(/eda)`。
3. `import_service.py` — `detect_mapping()` 按 sheet/列签名自动选模板;`api/data.py` `/import`、`/import/batch` 支持 `mapping_id=auto`,返回识别到的模板。
4. `frontend/DataUpload.tsx` — 默认"自动识别模板",结果表显示识别到的模板。
5. `packaging/srs.spec` — 收录 `ml/{etl,models,explain,recommend,evaluation,cleaning,eda}` 源码。
6. AI 可配置接入(前次):`core/ai_config.py` + `/system/ai-config` + 系统管理页表单,默认 GLM 官方免费。
7. 权限矩阵中文化 + 全列居中(前次)。
8. 黑屏/404 多候选 dist 解析(前次,已实测进登录页)。

全部 `py_compile` + 前端 `tsc --noEmit` 通过;`detect_mapping` 沙箱实测个旧文件→个旧模板(14/14 命中)。

## 仍存在的缺口(需裴总知悉/后续)

1. **地图 市/县级 geojson 缺失**:`data/geo` 仅有 `china_provinces.json`,无 `prefectures/`、`counties/`。省界可显示,放大到市/县会 404。需跑 `scripts/download_admin_boundaries.py` 补齐(需外网)或离线导入 MBTiles。
2. **南京栖霞 / 乡村复合的 raw xlsx 不在 `data/raw`**:目前仅个旧文件在库。三场地完整 E2E 需把另两个 xlsx 放入 `data/raw`(其 sheet 名须为 `南京栖霞完整数据` / `乡村建设用地完整数据`,与映射一致)。
3. **AI 默认模型名 `GLM-4.7-Flash`**:请在"AI 模型配置"页确认智谱实际可用模型名(如限流可切 DeepSeek/SiliconFlow)。
4. 打包 .env 不分发:这是有意为之(密钥不外泄),AI key 改由本机配置页录入。

## 验证(裴总本机执行)

源码态一键冒烟(真实库,逐接口 PASS/FAIL):
```bash
cd /Users/lensis/Claude/Projects/SRS
bash scripts/dev_smoke.sh "data/raw/3.20250731_重金属污染场地数据表(云南个旧)_最终版.xlsx"
```
重新打包验证(含上述全部修复):
```bash
cd frontend && npm run build && cd ..
backend/.venv/bin/pyinstaller packaging/srs.spec --clean --noconfirm
pkill -9 -f "SRS.app/Contents/MacOS/SRS"; lsof -ti tcp:8000 | xargs kill -9 2>/dev/null
rm -f ~/Library/Application\ Support/SRS/srs.db
open dist/SRS.app
```
打开后建议闭环走查:登录 → 数据导入(选自动识别)→ 场地详情(图表)→ 障碍因子诊断 → SSUI → 方案推荐 → 地图 → 系统管理/AI 配置。
