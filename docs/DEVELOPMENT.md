# SRS 系统开发规范

## 1. 项目定位

**污染场地土壤生态-生产功能重构监管系统（SRS）**

面向污染场地全过程监管的系统闭环：

```
导入场地数据 → 数据校验 → 场地详情 → 障碍因子识别 → RF/SHAP 解释
→ 功能重构可行性评价 → SSUI 可持续利用评价 → 重构方案推荐
→ 五阶段追溯记录 → PDF 追溯报告生成
```

## 2. 技术栈

**前端**：React 18 + TypeScript + Ant Design 5 + ECharts 5 + Leaflet
**后端**：Python FastAPI + SQLAlchemy + Pydantic
**数据库**：SQLite（单机演示）/ PostgreSQL（生产部署）
**算法**：scikit-learn RandomForest + SHAP + GEE 空间协变量
**报告**：Jinja2 模板 + WeasyPrint PDF + python-docx
**部署**：Docker + Nginx + 桌面端 PyInstaller 打包

## 3. 目录结构

```
/backend   — FastAPI 后端（API、服务、模型、数据库）
/frontend  — React 前端（页面、组件、主题、API 客户端）
/ml        — 算法模块（RF 训练、SHAP、GEE 协变量、模型产物）
/reporting — 报告生成（HTML 模板、PDF/DOCX 引擎）
/data      — 数据（raw 原始 / processed 清洗 / knowledge_base 知识库）
/docs      — 设计与验收文档
/deploy    — 部署配置（Docker、Nginx、初始化脚本）
/packaging — 桌面端打包
```

## 4. 数据库设计原则

- 检测数据使用"长表"设计（site_id + sample_id + factor_id + value），不为每个污染物创建宽字段
- 后续可扩展 PFAS、抗生素、微塑料、TPH、PAHs 等新型污染物
- 阈值规则、用地类型、风险等级、权重配置等必须入库或进配置文件，不得硬编码

核心表：users / roles / permissions / sites / sampling_points / measurements / factor_dictionary / threshold_rules / ml_models / diagnosis_results / evaluation_results / technology_library / recommendations / workflow_records / report_records / audit_logs / file_objects / dataset_versions / project_authorizations

## 5. 编码规范

- 简洁优先：解决问题所需的最小代码，不添加需求之外的功能
- 精准修改：只触碰必须改的，不重构无关模块
- 每行变更必须能追溯到需求
- 不伪造数据、不伪造标准、不伪造模型性能
- 所有写操作记录审计日志
- 密码哈希存储，不得明文保存密钥

## 6. 测试

```bash
# 后端测试
cd backend
pytest tests/ -v

# 前端类型检查与构建
cd frontend
npx tsc --noEmit
npm run build

# UI 验收截图
cd frontend
npx playwright test e2e/capture-ui-audit.spec.ts --reporter=list --timeout=120000
```

## 7. 启动

```bash
# 后端
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 前端
cd frontend
npm run dev   # → http://localhost:5173
```

默认管理员账号：admin / Demo@2026（首次登录后请修改密码）

## 8. 数据真实性原则

- 原始数据只放入 `data/raw/`，不得覆盖或手动改值
- 所有清洗结果放入 `data/processed/`
- 不得伪造缺失字段、不得将示例数据当成真实数据
- 模型输出必须包含模型版本、训练数据版本、特征清单、指标
- 统计接口未覆盖的字段应显示"暂无统计"，不得用占位数据冒充真实数据

## 9. 权限模型

四角色 RBAC：

| 角色 | 定位 |
|------|------|
| 系统管理员 | 全功能访问、用户审核、系统配置 |
| 企业用户 | 本企业场地数据录入、方案生成、流程上传 |
| 第三方机构 | 检测/评估，按 ProjectAuthorization 授权访问场地 |
| 监管人员 | 政府监管，查看监管范围内数据与审计 |

企业用户数据隔离到本企业（organization_id 行级过滤）；第三方机构须通过项目授权表获得场地访问权。
