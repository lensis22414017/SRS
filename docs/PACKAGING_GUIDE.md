# SRS 打包清单与文件分类指南

> 目的：理清仓库中哪些是**打包必备**（缺失会导致功能不可用），哪些是**过程文件**（开发/训练用，打包可省略）。

---

## 一、打包必备文件（缺一不可）

### 1.1 后端核心
| 路径 | 作用 | 缺失后果 |
|---|---|---|
| `backend/app/**/*.py` | FastAPI 应用全部源码 | 系统无法启动 |
| `backend/app/services/mappings/*.json` | 场地数据导入映射（个旧/栖霞/复合/通用） | 无法导入数据 |
| `packaging/launcher.py` | 桌面启动器（pywebview窗口+环境自检） | 无入口 exe |
| `packaging/srs.spec` | PyInstaller 打包配置 | 无法打包 |

### 1.2 前端构建产物
| 路径 | 作用 | 缺失后果 |
|---|---|---|
| `frontend/dist/` | Vite 构建的静态资源（index.html + assets/） | 页面空白 |
| ⚠️ 打包前必须执行 `cd frontend && npm run build` | — | — |

### 1.3 数据与知识库
| 路径 | 作用 | 大小 | 缺失后果 |
|---|---|---|---|
| `data/knowledge_base/*.csv` | 统一障碍因子知识库、技术库、修复案例 | ~2MB | 诊断/推荐无依据 |
| `data/geo/` | 离线行政区 GeoJSON（省/地市/县三级金字塔） | ~27MB | 地图无边界 |
| `reporting/templates/traceability_report.html` | 报告 Jinja2 模板 | 254行 | 无法生成报告 |

### 1.4 ML 模型工件
| 路径 | 作用 | 大小 | 缺失后果 |
|---|---|---|---|
| `ml/artifacts/p3_alpha/*.joblib` | 随机森林模型（4个：all/op × prod/eco） | ~50MB | 诊断功能不可用 |
| `ml/artifacts/p3_alpha/*_shap_global.parquet` | SHAP 全局贡献值 | ~5MB | 无障碍因子排名 |
| `ml/artifacts/p3_alpha/*_metrics.json` | 模型指标 | <1KB | 无模型版本信息 |
| `ml/artifacts/model_registry_v0.8.json` | 模型注册表 | <1KB | 模型管理异常 |
| `ml/ranking/kos_engine_v0.8.py` | KOS 核心计算引擎 | — | KOS 诊断不可用 |
| `ml/explain/*.py` | SHAP 计算/清洗 | — | 诊断不可用 |

### 1.5 安装包组件
| 路径 | 作用 |
|---|---|
| `packaging/srs_setup.iss` | Inno Setup 安装脚本 |
| `packaging/srs_icon_v2.ico` | 应用图标（多尺寸） |
| `docs/USER_GUIDE.md` | 首次使用说明 |

---

## 二、过程文件（打包可省略）

### 2.1 开发工具与配置
| 路径 | 说明 |
|---|---|
| `backend/.venv/` | Python 虚拟环境（每个安装机自行建） |
| `frontend/node_modules/` | npm 依赖（构建后可删） |
| `frontend/src/` | 前端源码（已编译进 dist/，打包不需要） |
| `backend/tests/` | 测试代码 |
| `backend/conftest.py` | pytest 配置 |
| `.zcode/` | ZCode agent 会话（开发过程记录） |

### 2.2 原始数据与训练
| 路径 | 说明 |
|---|---|
| `data/raw/*.xlsx` | 甲方原始 Excel（3份真实数据） |
| `data/covariates/*.csv` | GEE 协变量合并表（训练用） |
| `autoresearch/` | 研究过程产物（映射审计/阈值库/特征工程） |
| `ml/autoresearch/` | 模型训练日志 |
| `scripts/build_*.py` | 数据集构建脚本（一次性运行） |
| `scripts/audit_*.py` | 数据审计脚本 |

### 2.3 文档与截图
| 路径 | 说明 |
|---|---|
| `artifacts/` | 运行截图、演示报告 |
| `AUDIT_FOR_GPT.md` | 内部审核文档 |
| `CHANGELOG.md` | 变更日志 |
| `srs-*-snapshot.md` | 开发调试快照 |

---

## 三、打包流程（完整步骤）

```bash
# 0. 前置确认（在项目根目录）
cd C:\Users\曾鸿\Desktop\SRS

# 1. 构建前端
cd frontend && npm run build && cd ..

# 2. 确认 ML 工件存在
ls ml/artifacts/p3_alpha/*.joblib  # 应有4个模型文件

# 3. 确认离线地图数据存在
ls data/geo/*.geojson | wc -l       # 应有省/地市/县级GeoJSON

# 4. PyInstaller 打包（生成 dist/SRS/）
cd backend
.venv\Scripts\pyinstaller ..\packaging\srs.spec --clean
cd ..

# 5. 验证打包产物
ls dist/SRS/SRS.exe                 # 应存在

# 6. 冒烟测试（直接运行）
dist\SRS\SRS.exe                    # 应打开窗口

# 7. Inno Setup 编译安装包
#    用 Inno Setup Compiler 打开 packaging/srs_setup.iss → Build
#    输出: packaging/Output/SRS_Setup_v1.0.0.exe
```

---

## 四、已知限制与降级行为

| 组件 | 状态 | 降级行为 |
|---|---|---|
| weasyprint (PDF高质量) | ❌ 缺GTK库 | 降级到 xhtml2pdf（格式略简但可用） |
| Redis 缓存 | ❌ 未安装 | 内存缓存替代，核心功能不受影响 |
| AI 大模型 | 取决于 key | 未配置时降级为知识库检索 |
| 高德卫星影像 | 取决于 key | 未配置时只有行政区矢量底图 |
| 天地图MBTiles | ❌ 未下载 | 无离线影像（需联网用高德） |

---

## 五、交付物清单（给甲方）

| 文件 | 说明 | 大小(估) |
|---|---|---|
| `SRS_Setup_v1.0.0.exe` | 安装包（双击安装） | ~280-350MB |
| `data/demo_sites/*.xlsx` (18份) | 演示数据（导入用） | ~0.5MB |
| `data/raw/*.xlsx` (3份) | 真实数据（备份） | ~2MB |
| `docs/USER_GUIDE.md` | 使用说明（已内置安装包） | — |
