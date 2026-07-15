# SRS 文献挖掘执行计划 — OP & HM_OP 数据补强

- 生成时间：2026-07-07
- 执行人：辛特助（代裴总）
- 任务来源：裴总 `/deep-research` + "自行完成、留工作记录与成果文件" 授权
- 工作记录：见 `WORKLOG.md`

---

## 1. Context（为什么做）

SRS 障碍诊断模型 `hm_op`（重金属+有机污染复合）训练子集当前 **244 样本 / 45 source_groups**，未达 `MIN_TRAIN_SAMPLES=1000` 门槛，`08_training_ready/hm_op/` 的 parquet 已被删除（留 `NOT_READY_REASON.md`），所以 `train_config_hm_op_prod.yaml` 显示 `train_n=0`。

**目标**：从 `G:\文献整理_最终`（11755 篇已解析文献）挖掘中国境内 sample-level OP 与 HM_OP 数据，**追加补强**现有 244 样本，缩小到 1000 门槛差距，提升 OP/HM_OP 泛化能力。

**裴总硬约束**：不先优化模型；只用真实文献数据；禁止合成；优先同采样点 HM+OP；不训练除非 HM_OP training_ready ≥100 sample_id 且 source_groups ≥10。

---

## 2. 侦察结论（事实 + 代码证据）

| # | 发现 | 证据 |
|---|------|------|
| F1 | hm_op 当前 244 样本 < 1000 门槛（非零样本） | `06_dataset_subsets/dataset_hm_op_v0.8.parquet` + `seal_pack_repair_v0.8.py` |
| F2 | **HM_OP 判定 = sample_id 级**，hm_raw×8 + op_raw×10 列非空 | `scripts/build_gold_dataset.py:371-384` |
| F3 | OI fallback 阈值仅覆盖 HM8 + BaP + SumHCHs + SumDDTs | `build_gold_dataset.py:258-263` |
| F4 | OI = Σ(B·R·W·D·rel)/Σ(W·D)，R=log(1+val/U)/log(1+cap), cap=50 | `build_gold_dataset.py:253-334` |
| F5 | 文献库 11755 篇 / China 5667 / OP 命中 1890 / HM+OP 复合 508 | grep `文献目录_literature_catalog.csv` |
| F6 | 物理结构 `{stem}/{paper.pdf, metadata.json, parsed/{paper.md, images/}}` | PowerShell 探测 |
| F7 | metadata.json 极简（folder/category/indexed_at），元数据依赖 catalog CSV | Read P00113 |
| F8 | paper.md 多为叙述+图片引用，结构化表格稀缺 → 多数候选需数字化 | Read P00113 paper.md |
| F9 | GEE credentials 已缓存，16 协变量脚本就绪 | `ml/covariates/gee_fetch.py` + `.config/earthengine/credentials` |
| F10 | catalog CSV 含 NULL 字节 `\0`，读取需 utf-8-sig + 清理 | grep binary match |

**hm_raw / op_raw 清单（build_gold_dataset.py:371-373）**：
- `hm_raw`: Cd_mgkg, Pb_mgkg, As_mgkg, Cr_mgkg, Hg_mgkg, Cu_mgkg, Zn_mgkg, Ni_mgkg
- `op_raw`: Sum_PAH_ngg, BaP_ngg, SumDDTs_ngg, SumHCHs_ngg, SumOCP_ngg, SumPCB_ngg, SumPBDE_ngg, SumPFAS_ngg, SumPAE_ugkg, TotalPHC_mgkg

---

## 3. 北极星指标

- **主**：新增 sample-level HM_OP 共观测数（同 sample_id 同时有 hm_raw 和 op_raw 非空）
- **次**：新增 OP-only 样本数（扩 OP 子模型）
- **约束**：source_groups ≥ 10（裴总门槛）；理想 ≥5/fold 让 GroupKFold outer_folds=5 可行
- **红线**：禁止伪复合（跨论文拼接 / 全省均值 / 风险指数 / 模型预测图）

---

## 4. 输出文件清单

路径：`C:\Users\曾鸿\Desktop\SRS\outputs\literature_mining\`

| 文件 | 阶段 | 内容 |
|------|------|------|
| `EXECUTION_PLAN.md` | 事前 | 本文件 |
| `WORKLOG.md` | 全程 | 工作记录（审计入口） |
| `candidate_literature_op_hmop.csv` | P1 | A/B/C/D 分级 |
| `rejected_literature_log.csv` | P1 | 排除原因 |
| `extracted_observations_long_op_hmop.csv` | P2 | long format 观测（28 列对齐） |
| `site_dataset_summary_op_hmop.csv` | P3 | 场地统计+可训练标签 |
| `qa_summary.json` | P4 | QA + GroupKFold 可行性 |
| `extraction_report.md` | P5 | 中文报告 |
| `gee_covariates_*.csv` | P6 | GEE 协变量 |
| `_scripts/*.py` | 全程 | 可复跑脚本 |

---

## 5. 执行阶段（原子化）

### P0 共享工具骨架
- `_scripts/common.py`：catalog 读取（NULL 清理）、stem→Path 映射、单位换算表、OP 族命名对齐、PowerShell 调用封装
- 复用：`data/knowledge_base/OP_factor_naming_alignment.py`、`ml/cleaning/standardize.py`
- **验证**：`python -c "from common import *; print(load_catalog().shape)"` → (11755, 14)

### P1 候选筛选（全量脚本）
- 输入：catalog 11755 行
- 逻辑：关键词正则（摘要+标题）+ SI 状态 + region=China
- 分级：A=采样点级 HM+OP + SI + 中国；B=同场地 HM&OP 图表级；C=OP-only 中国；D=综述/模型/无数据 → rejected
- 优先标记裴总 14 强候选（题名/DOI 匹配）
- **验证**：508 复合信号全在 A+B + 14 强候选全部定位

### P2 A/B 级精读抽取（Workflow 并行）
- 输入：P1 的 A+B 级（预计 50-200 篇）
- 编排：Workflow `pipeline(candidates, locate, extract, selfcheck)`
- 每篇：读 paper.md + metadata + images + SI 线索 → long 抽取 → 单位标准化 → 单体 PAH 聚合为 Sum_PAH_ngg → 自检
- **验证**：每行 evidence_location 可追溯 + conversion_note 完整 + 无伪复合

### P3 训练可用性判定
- 按 source_id+sample_id 判定 training_ready_hm_op / site_level_hm_op_only / op_only_ready / not_training_ready
- 防伪复合四红线检查
- **验证**：HM_OP 样本全 sample_id 级共现

### P4 QA
- 5 检查：去重 / 非负 / 换算 / 共现 / GroupKFold 分组
- source_id 与现有 1158 组无交叉
- **验证**：红旗显式 + GroupKFold 可行

### P5 报告 + WORKLOG
- extraction_report.md（中文）：漏斗、top10、样本数、与 1000 门槛差距、待人工 top10
- **验证**：裴总可独立复核

### P6 GEE 采样
- 复用 `ml/covariates/gee_fetch.py`，对 (lat,lon) 采 16 协变量
- 合并到两份数据集，列名正常（soc/cec/ndvi），备注来源
- **边界**：credentials 过期需裴总 OAuth
- **验证**：协变量覆盖率 + 合并无误

---

## 6. 关键技术约束

### 6.1 防伪复合（最高优先级）
- HM_OP 判定必须在 **source_id 内部** 的 **同一 sample_id** 上
- 禁止：跨论文拼接；全省/全国均值当 sample；风险指数（Igeo/RI/HQ）当浓度；模型预测图当实测（除非标 proxy_covariate + is_proxy=True，不进 measured）

### 6.2 单位标准化
| 族 | unit_std | 换算 |
|----|----------|------|
| HM (Cd/Pb/As/Cr/Hg/Cu/Zn/Ni) | mg/kg | 原值 |
| PAH 单体 (Nap/BaP/...) | ng/g | μg/kg×1, mg/kg×1000 |
| Sum_PAH/SumHCHs/SumDDTs/SumOCP/SumPCB/SumPBDE/SumPFAS | ng/g | 同上 |
| SumPAE | μg/kg | 保留（build 脚本用 ugkg） |
| TotalPHC/TPH | mg/kg | 保留（build 脚本用 mgkg） |
| 不确定 | 保留原值 | qa_flag=unit_uncertain |

### 6.3 source_id 规范
- 优先 DOI（如 `10.1016/j.jhazmat.2025.140728`）
- 无 DOI 的中文期刊：`CN_{paper_id}`（如 `CN_P03103`）
- 绝不与现有 1158 source_id 交叉

### 6.4 evidence_level
- `A_sample_table`：paper.md 结构化表格，采样点级
- `B_site_summary`：场地统计汇总（均值±sd）
- `C_figure_digitized`：图表数字化（censoring_flag=estimated_from_figure）
- `D_text_only`：仅文本 → 不进 extracted

### 6.5 表格抽取策略
- 优先 paper.md 的 markdown 表格（`| --- |`）
- 无表格：检查 images/ 表图（OCR），标 needs_digitization
- PDF 表格：pdfplumber（已装）；复杂表选装 camelot-py

---

## 7. 可复用资产

| 资产 | 路径 | 复用方式 |
|------|------|----------|
| OP 族命名对齐 | `data/knowledge_base/OP_factor_naming_alignment.py` | import 命名映射 |
| 单位/省份标准化 | `ml/cleaning/standardize.py` | import 标准化函数 |
| GEE 采样 | `ml/covariates/gee_fetch.py` | 直接调用，16 协变量 |
| GEE 持久化 | `ml/etl/enrich_sites_gee.py` | 参考 DB 逻辑 |
| HM_OP 判定 | `scripts/build_gold_dataset.py:371-384` | 抄逻辑不 import |
| long format schema | `clean_observations_long_v0.8.csv` | 28 列对齐 |

---

## 8. Workflow 编排设计（P2）

```js
phase('Extract')
pipeline(
  AB_candidates,
  paper => agent(read+locate,   {schema: LOCATE}),  // 定位表格/图表/SI
  loc   => agent(extract_long,  {schema: OBS}),     // long 抽取+单位+族群聚合
  obs   => agent(selfcheck,     {schema: VERDICT})  // 自检
)
```
- 并发 cap = min(16, cpu-2)
- 每篇独立 context
- 失败 item 进 needs_review，不阻塞其他

---

## 9. 边界声明（诚实）

1. **token 约束**：5667 中国文献无法逐篇精读。P1 全量初筛，P2 只精读 A+B 级（预计 50-200 篇）。
2. **GEE OAuth**：credentials 已缓存，辛特助可跑；过期则需裴总本地 `earthengine authenticate`。
3. **乐观上界**：508 复合候选 → 实际 A 级可能仅 5-15 篇。HM_OP 新增可能远小于 1000 门槛。按真实结果报告，不凑数。
4. **OP 阈值缺口**：SumPAH/SumPCB/SumPBDE/SumPFAS/SumPAE/TotalPHC 无 OI fallback 阈值，即使抽取也只扩样本量不驱动 OI。报告指出。
5. **不训练模型**：除非 HM_OP training_ready ≥100 sample_id 且 source_groups ≥10，否则只交付数据 + 缺口分析。

---

## 10. 验证总表

| 阶段 | 验证方法 | 通过标准 |
|------|----------|----------|
| P0 | import + shape | (11755, 14) 无错 |
| P1 | count + 强候选 | 508 复合全命中 + 14 强定位 |
| P2 | evidence_location + conversion_note | 每行可追溯 |
| P3 | sample_id 共现 | HM_OP 全 sample 级 |
| P4 | 5 检查 + GroupKFold | 红旗显式 + fold 可行 |
| P5 | 裴总复核 | 完整可审计 |
| P6 | 协变量覆盖 | 合理覆盖率 |

---

*本计划基于 4 轮侦察制定。执行中遇偏离需记录到 WORKLOG.md 并标注原因。*
