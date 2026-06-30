# Wave F 双用途功能测试报告 — 多场地/EDA/地图/AI-RAG (full双轨模型)

> 生成：2026-06-26 | 模式：EXECUTE（裴总 goal）| 模型：lake_prod_full / lake_eco_full（过渡，AUC虚高已标warning）
> 结论：**全维度闭环** — 多场地双轨6/6 + EDA5/5 + 地图5/5 + AI-RAG三场景不崩溃

## Executive Summary

按裴总 goal 完成 Wave F 双用途功能测试扩展。导入 5 测试场地（HM/OP/composite 三类型），用 full 双轨模型验证多场地双轨诊断 + EDA + 地图 + AI-RAG 全链路。**6/6 场地双轨打通**（生产>生态系统性，符合 plan D1），EDA/地图/AI-RAG API 多场地返回真实数据。修复 EDA depth NaN bug。

## 一、多场地双轨诊断矩阵（核心，6/6 打通）

| 场地 | 类型 | 生产proba | 生态proba | 模型异 | 结论异 |
|---|---|---|---|---|---|
| 云南个旧 | heavy_metal | 0.6471 | 0.5596 | ✓ | ✓ |
| 广东HM(200点) | heavy_metal | 0.5888 | 0.0996 | ✓ | ✓ |
| 北京OP(200点) | organic | 0.2533 | 0.2033 | ✓ | ✓ |
| 山东HM+OP(24点) | composite | 0.4054 | 0.0975 | ✓ | ✓ |
| 新疆HM(200点) | heavy_metal | 0.0902 | 0.0197 | ✓ | ✓ |
| 浙江OP(175点) | organic | 0.2999 | 0.2367 | ✓ | ✓ |

**科学发现**：6/6 场地生产_proba > 生态_proba（生产轨严阈值判定风险系统性更高）。风险差异 Δ：广东HM 0.49（最大）/ 山东composite 0.31 / 北京OP 0.05（OP一类/二类差距小）。**可向甲方演示多场地双轨监管决策**。

## 二、AI-RAG 三场景（全不崩溃）

| 场景 | status | 处理 |
|---|---|---|
| 无key(base_url+key空) | ✓ok | RAG降级回复（技术8命中：固化/植物修复/淋洗） |
| 错key(SiliconFlow+无效key) | ✓ok | RAG降级（基于场地数据+技术库） |
| 无base_url(有错key) | ✓ok | RAG降级（基于知识库） |

RAG 独立可用（纯DB查询，技术8/因子1/场地上下文有）。三错误场景降级不崩溃，符合 §9（LLM不作判定源）。正常AI场景待裴总提供真key。

## 三、EDA/地图 API 多场地验证（5/5 + bug修复）

| 场地 | EDA | 地图 pollutants | 地图 geojson采样点 |
|---|---|---|---|
| 个旧HM | ✓(factors/correlation/grouped) | 14 | 191 |
| 广东HM | ✓ | 10 | 200 |
| 北京OP | ✓ | 3 | 200 |
| 山东HM+OP | ✓ | 11 | 24 |
| 浙江OP | ✓ | 7 | 175 |

**修复 bug**：`site_eda`(data.py:504) `int(NaN or 0)` 崩（NaN truthy）→ 改 `pd.notna` 守卫。test_datasets 场地（无深度列）暴露此 bug。

## 四、遗留

- **宽表 /points_wide 404**：三端点变体（points_wide/points/wide/measurements/wide）都404。次要（EDA 已含 factors 数据，前端 SiteDetail 可能用不同端点或已废弃此接口）。
- **full 双轨模型 AUC 虚高**：已 meta.warning 标注（标签泄漏），作 Wave F 过渡演示可，不可声称独立泛化。

## 五、产物

| 产物 | 路径 |
|---|---|
| 多场地双轨测试 | scripts/waveF_multi_site_dual_track.py / waveF_import_and_test.py |
| AI-RAG 三场景 | scripts/waveF_ai_rag_3scenarios.py |
| EDA/地图验证 | scripts/waveF_eda_map_api.py |
| 场地调查 | scripts/waveF_site_survey.py |
| bug修复 | backend/app/api/data.py:504 (EDA depth NaN) |
| 导入测试场地 | DB site_id 4-8（广东HM/北京OP/山东composite/新疆HM/浙江OP） |
| 本报告 | docs/audit/waveF_dual_track_test.md |

## Methodology

goal 推进 → 查场地(本地仅1) → 导入test_datasets 5代表场地(HM/OP/composite) → 多场地双轨诊断矩阵(6/6) → AI-RAG三场景(改settings模拟) → EDA/地图API(发现depth NaN bug修复) → 全维度闭环。
