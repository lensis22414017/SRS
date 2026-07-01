# 打包后黑屏 + {"detail":"not found"} + 黑图标 修复 — 2026-06-16

## 症状
打开 .dmg 安装的 App,窗口黑屏,内容为 `{"detail":"not found"}`;Dock 图标背景黑。

## 根因
1. **黑屏 + 404**:WebView 打开 `http://127.0.0.1:8000/`,但打包后 `app/main.py` 的 `_frontend_dist_dir()` 在 `.app` 内未解析到 `frontend/dist`(macOS `.app` 的 `sys._MEIPASS` / COLLECT 落点与原候选路径不一致)→ SPA 路由未注册 → 根路由命中后端默认 404 JSON。
2. **黑图标**:`packaging/srs.icns` 仅含单一 `icp4`(16×16)条目,缺多尺寸 → Dock/Finder 大图标位渲染异常。

## 修复(已改代码)
`backend/app/main.py`:
- `_candidate_dist_dirs()` 枚举所有布局:`sys._MEIPASS/frontend/dist`、`exe_dir/frontend/dist`、`../Resources/...`、`../Frameworks/...`、`_internal/...`、源码相对路径、CWD。
- 新增 `_resolve_dist()`,**请求时再解析**(不依赖导入时 chdir 时序)。
- dist 缺失时根路由返回**清晰诊断页**(不再黑屏+裸 404);保留前缀(api/health/docs/assets)正常 404,其余回退 index.html。
- 已 py_compile 通过;保留前缀守卫与 SPA 回退逻辑沙箱验证正确。

## 本机重新打包(项目组执行)
```bash
cd /Users/lensis/大语言模型/Projects/SRS
# 1) 先构建前端(确保 frontend/dist 最新)
cd frontend && npm run build && cd ..
# 2) 重新打包(spec 已含 (frontend/dist, frontend/dist))
backend/.venv/bin/pyinstaller packaging/srs.spec --clean --noconfirm
# 3) 验证 .app 内确实含 dist(产物在 dist/, 不是 backend/dist/!)
find dist/SRS.app -path "*frontend/dist/index.html"
# 实测落点: dist/SRS.app/Contents/Resources/frontend/dist/index.html
# 4) 启动验证(应显示登录页,而非 {"detail":"not found"})
open dist/SRS.app
#    或先验后端: dist/SRS.app/Contents/MacOS/SRS --no-tray  然后浏览器开 http://127.0.0.1:8000/
```

> ⚠️ 路径修正:PyInstaller 输出目录是项目根的 `dist/`(日志末行 "results are available in: .../SRS/dist")。
> macOS `.app` 的 datas 落在 `Contents/Resources/`,而 `sys._MEIPASS`=`Contents/Frameworks/` —— 旧代码只找前者外的 MEIPASS 故 404。本次修复已加 `../Resources/frontend/dist` 候选,实测命中。

## 修复黑图标(生成多尺寸 .icns,本机执行)
```bash
cd /Users/lensis/大语言模型/Projects/SRS/packaging
mkdir -p srs.iconset
sips -z 16 16     srs_512.png --out srs.iconset/icon_16x16.png
sips -z 32 32     srs_512.png --out srs.iconset/icon_16x16@2x.png
sips -z 32 32     srs_512.png --out srs.iconset/icon_32x32.png
sips -z 64 64     srs_512.png --out srs.iconset/icon_32x32@2x.png
sips -z 128 128   srs_512.png --out srs.iconset/icon_128x128.png
sips -z 256 256   srs_512.png --out srs.iconset/icon_128x128@2x.png
sips -z 256 256   srs_512.png --out srs.iconset/icon_256x256.png
sips -z 512 512   srs_512.png --out srs.iconset/icon_256x256@2x.png
sips -z 512 512   srs_512.png --out srs.iconset/icon_512x512.png
cp srs_512.png    srs.iconset/icon_512x512@2x.png    # 理想用 1024 源图
iconutil -c icns srs.iconset -o srs.icns
# 重新打包后图标即正常。若 Dock 仍缓存旧图标: killall Dock
```
> 提示:`srs_512.png` 仅 512;`icon_512x512@2x` 理想需 1024 源图。若有 1024 PNG 更佳。

## 追加修复:打包后数据文件 FileNotFoundError(2026-06-16 第二轮)

### 症状
黑屏修好后,导入数据报 `FileNotFoundError: .../SRS.app/Contents/data/knowledge_base/统一障碍因子知识库_V1.0.csv`。

### 根因
多个服务用 `ROOT = dirname(__file__)/../../..` 推导项目根。实测 `sys._MEIPASS = Contents/Resources`,而 `../../..` 从 `Resources/app/services` 多爬一级到 **`Contents`**,且数据实际在 `Contents/Resources/data/...`。
连带:`seed_db.seed_tech()` 同样路径错,被 `if not exists` 静默跳过 → 打包 DB 里**技术库为空**(推荐无技术可匹配)。
另:`ml/{etl,models,explain,recommend,evaluation}` 的 .py 源码未打进包,运行期 `sys.path.insert` 后 import 会失败。

### 修复(已改代码)
- `backend/app/core/config.py` 新增 `resource_root()`:探测 `_MEIPASS / ../Resources / ../Frameworks` 中含 `data/knowledge_base` 的真正落点;源码模式回退项目根。
- 改用 `resource_root()`:`pipeline.py`、`evaluation_service.py`、`recommend_service.py`、`diagnosis_service.py`、`report_service.py`、`db/load_kb.py`、`db/seed_db.py(seed_tech)`。
- `packaging/srs.spec` 增打包 `ml/{etl,models,explain,recommend,evaluation,cleaning,eda}` 源码。
- 全部 py_compile 通过;`import_service.MAPPINGS_DIR` 用 `dirname(__file__)` 已正确(因 `_MEIPASS=Resources`),无需改。

### 重打包并重置本机 DB(项目组执行)
```bash
cd /Users/lensis/大语言模型/Projects/SRS
cd frontend && npm run build && cd ..
backend/.venv/bin/pyinstaller packaging/srs.spec --clean --noconfirm
# 关键: 删除旧 DB, 让 seed 重跑(旧 DB 建库时技术库被跳过, 否则推荐为空)
pkill -9 -f "SRS.app/Contents/MacOS/SRS"; lsof -ti tcp:8000 | xargs kill -9 2>/dev/null
rm -f ~/Library/Application\ Support/SRS/srs.db
open dist/SRS.app
```
> `srs.db` 是可由种子重建的本机演示库,删除仅清空演示数据,不影响 data/raw。

## 验收
- App 打开显示**登录页**(非 404 JSON、非黑屏)。
- Dock/Finder 图标显示正常 logo(非黑底)。
- 仍黑屏时:终端跑 `Contents/MacOS/SRS` 看日志,确认 `frontend/dist` 是否在包内(步骤3)。
