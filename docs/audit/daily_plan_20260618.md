# 每日开发计划 — 2026-06-18

> 辛特助自动巡检生成 | [MODE: PLAN] | 裴总确认后可发送 ENTER EXECUTE MODE 执行

---

## 昨日完成（2026-06-16 最后提交）

| commit | 内容 |
|--------|------|
| `230e8ad` | Docker 全面验证 + 桌面打包报告（pytest 71 通过 / 极端闭环 / DMG 174MB） |
| `acc5831` | srs.spec 改 onedir 模式，修复 `.app` 稳定性（peer-review Major 项） |
| `90cdada` | 同步代理改动（config/main/FieldMappingPage/mappings/docs） |
| `fb70587` | EDA 科研级可视化 / 三层离线地图 / 批量导入 / 附件下载 / 报告图件 / 打包自检 |

---

## 当前 MVP 闭环进度评估

| 闭环节点 | 状态 | 说明 |
|---------|------|------|
| 数据导入（Excel/CSV + 批量） | ✅ 完成 | 单文件 + 批量导入均已测试通过 |
| 数据校验 | ✅ 完成 | 校验服务 + 报告已实现 |
| 场地详情 | ✅ 完成 | 场地详情页 + 测点 + EDA 8 Tab |
| 障碍因子识别（RF） | ✅ 完成 | rf_barrier.py，群组交叉验证已正名 |
| RF/SHAP 解释 | ✅ 完成 | shap_service.py，全局+局部解释 |
| 功能重构评价 | ✅ 完成 | reconstruction.py + API |
| SSUI 可持续利用评价 | ✅ 完成 | ssui.py + API |
| 方案推荐 | ✅ 完成 | engine.py + 技术库匹配 |
| 全流程追溯（五阶段） | ✅ 完成 | workflow_service.py，附件下载已补齐 |
| PDF 追溯报告（含地图图件） | ✅ 完成 | 报告含 matplotlib 采样点散点图 |
| 操作日志 | ✅ 完成 | audit_service.py |
| 桌面打包（.app/.dmg） | ✅ 完成（需本机重建） | 黑屏/404/黑图标三项已修复，裴总需本机 `pyinstaller` |

**当前整体 MVP 主干：✅ 全部跑通**

主干已闭环。当前拦截甲方验收的不是功能缺口，而是**工程质量与可信度问题**（peer-review P1 项尚未处理）。

---

## 阻塞项 / 高风险项

1. **打包未本机重建**：黑屏修复代码已入库（`230e8ad`），但 `dist/SRS.app` 是旧版本，裴总需本机执行 `pyinstaller packaging/srs.spec --clean` 生成新 .app，否则演示仍黑屏。

2. **11 处异常吞没（P1 - Major 3 未处理）**：  
   `report_service.py:115/365/427` 已确认 `except Exception: pass`。其余 8 处分散在 `launcher.py`、`evaluation_service.py` 等。运维零感知，甲方审查时无法定位故障。

3. **前端无 React ErrorBoundary（P1 - Major 4 未处理）**：  
   `client.ts` 已有 401 拦截，但所有页面组件（`ObstacleAnalysis`、`ReconstructionAnalysis`、`SSUIAnalysis`、`RecommendationPage`）无 `ErrorBoundary` 包裹，任意 API 异常直接白屏。

---

## 今日最重要的 3 个目标

---

### 目标 1｜修复 11 处异常吞没 → 改为结构化日志（P1-Major3）

**优先级**：🔴 必须（影响甲方审查可观测性）

**文件路径**：
- `backend/app/services/report_service.py`（行 115、365、427）
- `backend/app/services/evaluation_service.py`（需 grep 确认）
- `backend/app/services/diagnosis_service.py`（需 grep 确认）
- `packaging/launcher.py`（行约 262）

**具体任务**：

```text
1. 全局 grep 定位全部 11 处（含 ml/ 模块）：
   grep -rn "except Exception" backend/app/ ml/ packaging/ --include="*.py"

2. 分类处理：
   - 可恢复降级路径（如 matplotlib 画图失败）：
       except Exception as exc:
           logger.warning("地图渲染失败，降级到文字模式: %s", exc)
   - 不可恢复路径（如 pisa PDF 生成失败）：
       except Exception as exc:
           logger.error("PDF 生成失败: %s", exc, exc_info=True)
           return None  # 或 raise

3. 所有模块顶部确保已导入：
       import logging
       logger = logging.getLogger(__name__)

4. report_service.py 的 3 处重点修复（最影响报告质量可观测性）。
```

**验证方式**：

```bash
# 验证吞没全部消除
grep -n "except Exception.*pass\|except Exception.*continue" \
  backend/app/services/*.py ml/**/*.py packaging/launcher.py

# 验证 logger 已导入
grep -l "import logging" backend/app/services/*.py

# 跑已有报告测试确认不崩溃
cd backend && python -m pytest tests/test_workflow_report.py tests/test_remediation_report.py -v
```

**风险**：部分 `except` 是为了让降级路径不崩系统（如报告无图时继续生成），改完后需确认降级逻辑仍工作，不能把 `pass` 直接改成 `raise`。

---

### 目标 2｜前端补 React ErrorBoundary（P1-Major4）

**优先级**：🔴 必须（白屏直接影响演示可信度）

**文件路径**：
- `frontend/src/components/ErrorBoundary.tsx`（新建）
- `frontend/src/App.tsx`（包裹路由）
- 重点页面：`ObstacleAnalysis.tsx`、`ReconstructionAnalysis.tsx`、`SSUIAnalysis.tsx`、`RecommendationPage.tsx`

**具体任务**：

```text
1. 新建 frontend/src/components/ErrorBoundary.tsx：
   - React class component 实现 componentDidCatch + getDerivedStateFromError
   - 降级 UI：显示错误信息 + "重新加载" 按钮 + 回主页链接
   - 接受 fallback prop 支持自定义

2. App.tsx：在根 Router 外层包裹全局 ErrorBoundary（兜底）

3. 算法/评价类页面（ObstacleAnalysis/ReconstructionAnalysis/SSUIAnalysis/RecommendationPage）
   每个页面顶层包裹局部 ErrorBoundary，显示"当前模块加载失败"友好提示，
   避免一个算法接口异常导致整个 SPA 白屏。

4. client.ts 已有 401 自动跳登录，无需重复处理。
   补充：非 401 的 5xx 错误，toast 提示"服务暂不可用，请稍后重试"（用 Ant Design Message）。
```

**验证方式**：

```bash
# 前端 build 通过
cd frontend && npm run build

# 手工验证：
# 1. 临时让 /sites/999/diagnosis 返回 500 → 页面应显示降级 UI 而非白屏
# 2. 断网状态访问算法页 → 显示友好错误框
```

**风险**：ErrorBoundary 只能捕获渲染阶段错误，异步 fetch 错误仍需在 `.catch()` 里处理。两者配合才能完整覆盖。

---

### 目标 3｜本机重建打包并验证（裴总本机执行）

**优先级**：🟠 高（黑屏修复已入库但尚未生成新 .app）

**文件路径**：
- `packaging/srs.spec`（已修复，onedir 模式）
- `backend/app/main.py`（已修复，多路径探测）
- `packaging/srs.icns`（黑图标，需本机用 sips 重生成）

**具体任务（裴总本机执行）**：

```bash
# Step 1: 前端先构建
cd /Users/lensis/Claude/Projects/SRS/frontend
npm run build

# Step 2: 生成多尺寸图标（需有 srs_512.png）
cd /Users/lensis/Claude/Projects/SRS/packaging
mkdir -p srs.iconset
sips -z 16 16   srs_512.png --out srs.iconset/icon_16x16.png
sips -z 32 32   srs_512.png --out srs.iconset/icon_16x16@2x.png
sips -z 128 128 srs_512.png --out srs.iconset/icon_128x128.png
sips -z 256 256 srs_512.png --out srs.iconset/icon_256x256.png
sips -z 512 512 srs_512.png --out srs.iconset/icon_512x512.png
iconutil -c icns srs.iconset -o srs.icns

# Step 3: 重新打包
cd /Users/lensis/Claude/Projects/SRS
backend/.venv/bin/pyinstaller packaging/srs.spec --clean --noconfirm

# Step 4: 验证 .app 内含 frontend/dist
find dist/SRS.app -name "index.html" | head -3

# Step 5: 启动验证（浏览器应显示登录页，不应黑屏）
open dist/SRS.app
```

**验证方式**：

```text
✅ 浏览器 http://127.0.0.1:8000/ 显示登录页（非 {"detail":"not found"}）
✅ 登录后能看到场地列表
✅ Dock 图标有颜色（非黑色方块）
✅ 导入数据不报 FileNotFoundError（knowledge_base 路径已修复）
```

**风险**：
- `srs_512.png` 源文件需存在于 `packaging/` 目录，若不存在需提供。
- macOS Dock 可能缓存旧图标，需 `killall Dock` 刷新。
- 打包约需 3-5 分钟，正常现象。

---

## 今日建议不要动的文件

- `data/raw/` — 原始数据，绝不触碰。
- `ml/models/group_split_training.py` — AUC 正名已完成，勿重复改动。
- `backend/alembic/` — 数据库 schema 稳定，无需迁移。
- `deploy/docker-compose.yml` — Docker 验证已通过，勿引入不稳定变量。

---

## 下一步（今日完成后）

1. **P2-Minor3**：清零 17 处 TODO/FIXME（主要在 `ml/` 和 `backend/app/api/`）
2. **P2-Minor4**：补测试——前端 ErrorBoundary 触发测试、非 401 5xx toast 测试
3. **文档同步**：`docs/audit/peer_review` 对照项打勾，更新验收清单
4. **Stage 3（长期）**：引入真实土壤数据重训模型，添加 PR-AUC / 校准曲线，替代当前"阈值识别器"定位

---

## 风险雷达

| 风险 | 等级 | 说明 |
|------|------|------|
| 异常吞没改错导致降级路径崩溃 | 🟠 中 | 改 except 时需逐处判断是否应 raise 或仅 log |
| ErrorBoundary 未覆盖异步错误 | 🟡 低 | 已有 client.ts 兜底，影响范围可控 |
| 本机打包环境不一致 | 🟡 低 | .venv 已固定依赖，正常可复现 |

---

裴总确认后，可另开 Cowork 任务发送 ENTER EXECUTE MODE 执行。
