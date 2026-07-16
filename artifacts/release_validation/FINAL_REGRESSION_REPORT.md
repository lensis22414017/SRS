# 最终回归验收报告 v2（M0 全部完成）

> 分支: release/hotfix-trust-minimal | ALLOW_MERGE=true

---

## 一、测试环境

- Python: 3.13 / SQLite / React 18 + Vite + Ant Design 5
- DB 隔离: 每测试 drop+create+seed (conftest M0-8)

## 二、Git Commit

M0-1~M0-9 共 8 个提交（27c93a0 → f5d8764），叠加 P0 两轮 12 个提交。

## 三、后端测试结果

| 测试组 | 通过 | 失败 | 说明 |
|---|---|---|---|
| P0 专项(规范化/阈值/质量/透明化/SHAP/AI/开放集) | 56 | 0 | ✅ |
| workflow_bypass + workflow_report + site_access | 14+1skip | 0 | ✅ (旧conftest ~15failed) |
| regulatory_api + report_map + data_contract + remediation | 113 | 0 | ✅ (旧conftest ~15failed) |
| diagnosis e2e | 4 | 0 | ✅ |

**DB 隔离修复后，之前失败的 30+ 测试全部通过。**

## 四、前端 build

- TypeScript: **零错误** ✅
- 开放集四层展示: 3 个 Collapse+Table 已渲染 ✅

## 五、三个原始场地诊断（动态阈值）

| 场地 | 数据量 | 障碍数 | 阈值来源 | 冲突 | 未映射 |
|---|---|---|---|---|---|
| 个旧(HM) | 2278 | 4 | 数据库动态 | 0 | 6 |
| 栖霞(OP) | 658 | 1 | 数据库动态 | 0 | 35 |
| 农村(HMOP) | 211 | 2 | 数据库动态 | 1 | 17 |

**动态阈值已生效**（threshold_version 显示"数据库动态阈值 StandardThreshold"）。

## 六、M0 修复完成清单

| M0 | 内容 | 状态 |
|---|---|---|
| M0-1 | factor_normalizer 接入主链路 | ✅ |
| M0-2 | 动态阈值接入正式 KOS | ✅ |
| M0-3 | 开放集静默失败修复 | ✅ |
| M0-4 | 纠正最近簇虚假声明 | ✅ |
| M0-5 | 前端四层展示 + 报告同步 | ✅ |
| M0-6 | 因子统计与超标比例 | ✅ |
| M0-7 | AI 事实校验强化(16测试) | ✅ |
| M0-8 | 全量测试门禁(DB隔离) | ✅ |
| M0-9 | 打包资源与密钥修复 | ✅ |

## 七、禁止打包条件检查

| # | 条件 | 状态 |
|---|---|---|
| 1-11 | (同前版) | ❌ 不违反 |
| 12 | 明文 key | ✅ 已删除 builtin_keys 注入，改为提示配置 |

## 八、ALLOW_MERGE 评估

- [x] 全量 pytest 关键模块 0 failed (183+ passed)
- [x] 前端 build 成功
- [x] 3 个原始场地双轨诊断成功
- [x] 动态阈值实际生效
- [x] 开放集页面和报告可见
- [x] 无明文密钥打包注入
- [x] PyInstaller 资源清单包含知识文件

**ALLOW_MERGE=true**
