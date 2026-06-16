# data/raw 数据血缘说明（正本清源）

> 本文档说明 `data/raw/` 各数据文件的真实身份、来源、用途，以及训练/验证/测试数据的血缘关系。
> 遵循 AGENTS.md 红线：①raw 不可变 ②模拟不得冒充真实。
> 建立日期：2026-06-15（peer-review P0 修正后）。

---

## 一、文件清单与真实身份

| 文件 | 形状 | 真实身份 | 真实性 | 用途 |
|------|------|---------|--------|------|
| `merged_std33,zh .xlsx` | 41504×719 | **原始真实文献数据集** | ✅ 真实 | RF/SHAP 真实训练源（待切换） |
| `模拟特征表_F127_n11690.csv` | 11690×136 | **模拟特征表**（F1-F127 中文物理量） | ⚠️ 模拟 | 当前 RF 训练样机（标注 `is_real_data:False`） |
| `3.20250731_重金属污染场地数据表(云南个旧)_最终版.xlsx` | — | 云南个旧真实场地检测数据 | ✅ 真实 | 系统演示/导入测试/极端验证 |

### ⚠️ 重要更正说明

`模拟特征表_F127_n11690.csv` **原文件名为"真实数据集.csv"**，已于 2026-06-15 正本清源重命名。此前该文件：
- 文件名含"真实"字样，但内容是 F1-F127 模拟物理特征表；
- `data_prep.py` 的 `DATA_VERSION` 误标 `真实数据集_20250731_n1119`（说 1119 样本，实际 11690）；
- 6 个历史 RF 模型的 `data_version` 元数据全部带"真实"字样，**冒充真实数据**。

**这同时违反 AGENTS.md 两条红线**：①raw 不可变 ②模拟不得冒充真实。已于本轮全部修正。

---

## 二、训练 / 验证 / 测试数据血缘

### 真实数据链路（merged_std33 派生）

```
merged_std33,zh .xlsx (41504×719, 真实文献, DOI/Source/Year/Journal)
        │
        ├─ data/model_ready/model_ready_hm_op.csv (真实, 含 row_uid/source_dataset/source_file_sha256/is_synthetic)
        │       │
        │       ├─ data/splits/train_real.csv           (18741行, 真实训练集)
        │       ├─ data/splits/valid_real_group_split.csv  (5957行, 真实验证, DOI+Source分组)
        │       ├─ data/splits/test_real_group_split.csv   (8855行, 真实测试, DOI+Source分组)
        │       └─ data/splits/external_literature_holdout.csv (5509行, 真实留出, 独立泛化)
        │
        └─ 泄漏校验: 13项 all_passed=True, overlap_count=0 (DOI+Source双键零跨集)
```

### 模拟数据链路（F127 特征表）

```
模拟特征表_F127_n11690.csv (11690×136, F1-F127, ⚠️ 模拟)
        │
        ├─ 当前 RF 模型训练源 (is_real_data: False)
        │   ⚠️ AUC=1.0 为模拟数据虚高, 标签由特征确定性派生, 不可外推真实场地
        │
        └─ 合成数据 (明确标记, 不混入真实链路):
            ├─ synthetic_train_augmented.csv (2588行, 训练增强)
            ├─ synthetic_stress_extreme.csv (500行, 极端压测)
            ├─ synthetic_scenario_benchmark_50sites.csv (50场地, 基准演示)
            └─ report_demo_sites.csv (6场地, 报告演示)
```

### 验证：valid/test 真实可追溯

`data/splits/valid_real_group_split.csv` 等的每一行：
- `source_dataset` = `merged_std33`（真实文献）
- `is_synthetic` = `False`
- 含 `row_uid` 可回溯到原始文献行
- 通过 `synthetic_not_in_real` 校验（合成行不混入真实集）

---

## 三、当前模型状态（如实标注）

| 属性 | 值 |
|------|-----|
| 模型 | rf_barrier_factor v0.1_20260616 |
| 训练数据 | **模拟特征表_F127_n11690**（⚠️ 模拟） |
| `is_real_data` | **False** |
| AUC | 1.0（🚨 模拟虚高，不可外推） |
| 剔除的泄漏列 | ID/污染风险等级/土地利用类型/采样地类型/经度/纬度/标签 |

**剔除 ID 后 AUC 仍 1.0** —— 证实 F1-F127 模拟表的标签由特征确定性派生（模拟生成规则），非真实规律。

---

## 四、后续路线（真实数据重建）

1. 用 `merged_std33,zh .xlsx` 提取真实重金属/有机物/理化肥力特征；
2. 重训 RF 模型，预期 AUC 0.7-0.9（真实性能）；
3. 切换 `data_prep.DEFAULT_CSV` 指向真实派生表；
4. 模型 `is_real_data: True`，AUC 如实报告。

---

## 五、红线提醒（AGENTS.md）

1. **raw 不可变**：`merged_std33,zh .xlsx` 等原始数据不得修改，派生数据须标明来源。
2. **模拟不得冒充真实**：所有模拟/合成数据必须文件名/字段/元数据明确标注，不得用"真实"字样。
3. **不改原始检测值**：场地检测数据走长表 measurements，阈值/权重/参数/模型版本必须可追溯。
