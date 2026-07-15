# EXPERIMENTS

## Exp #000 | 2026-07-15
假设: ExtraTrees可作为中小表格数据的稳健基线。
改动: 180棵树，max_features=0.7，min_samples_leaf=3。
指标: mean_cv_spearman=0.6385；worst=0.4208；mean_mae=0.0371。
裁决: KEEP（基线）。

## Exp #001 | 2026-07-15
假设: LightGBM原生缺失处理能改善稀疏OP任务。
改动: LGBM 250轮，lr=0.04，叶子31。
指标: mean=0.5900；worst=0.3501；mean_mae=0.0351。
裁决: REVERT（主指标与最差任务均明显下降，虽HM提升）。

## Exp #002 | 2026-07-15
假设: 提高每次分裂可见特征并降低叶节点平滑，可保留稀疏OP信号。
改动: ExtraTrees 240棵，max_features=1.0，min_samples_leaf=2。
指标: mean=0.6841；worst=0.4754；mean_mae=0.0317。
裁决: KEEP（六任务总体与最差任务均提升）。

## Exp #003 | 2026-07-15
假设: 取消叶节点平滑能保留稀疏复合污染样本的有效排序信号。
改动: min_samples_leaf 2→1。
指标: mean=0.7174；worst=0.5173；mean_mae=0.0284。
裁决: KEEP（六任务全部继续改善）。

## Exp #004 | 2026-07-15
假设: 不同数据密度应采用不同模型族，HM保留LightGBM优势，稀疏OP/HM+OP保留ExtraTrees。
改动: HM→LightGBM；OP/HM+OP→Exp#003 ExtraTrees。
指标: mean=0.7306；worst=0.5173；mean_mae=0.0266。
裁决: KEEP（新best；测试集仍未用于迭代）。

## Exp #005 | 2026-07-15
假设: 用标准SimpleImputer替代本地转换函数，可获得跨进程可加载的等价HM管线。
改动: HM预处理改为SimpleImputer(median,+indicator)。
指标: mean=0.7261；worst=0.5173；mean_mae=0.0269。
裁决: KEEP（主指标轻微下降0.0045，但修复了产物无法反序列化的硬性部署缺陷）。
