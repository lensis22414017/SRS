# 核心模型与数据可信性审核材料（供外部独立审阅）

> **目的**：本文件由开发代理（辛特助）整理，供另一位独立审核者（GPT）从外部视角审查
> SRS 系统的**数据→结论可信性**。开发代理已尽力如实记录，但审核者应保持怀疑，
> 独立验证而非采信本文档的结论。
>
> **审核重点**：不审 UI 美观，只审"数据进来→模型算→结论出去"这条链路的科学严谨性。

---

## 一、系统是什么

**污染场地土壤生态-生产功能重构监管系统（SRS）**

核心功能：给定一个污染场地的土壤检测数据，系统应能：
1. 识别哪些因子构成"障碍"（超标或有阈值依据的因子）
2. 对障碍因子排序（哪个最关键）
3. 评价该场地能否重构为生产用地/生态用地
4. 推荐修复方案

**关键方法学：KOS（Key Obstacle Score）关键障碍因子综合评分**

公式（`ml/ranking/kos_engine_v0.8.py:44,189`）：
```
KOS = B × (0.30·R + 0.25·W + 0.15·M + 0.20·S + 0.10·E)
```
- **B**（障碍判定，0/1）：实测值是否超过阈值。B=0 则该因子不进排名
- **R**（规则严重度，0-1）：超标倍数的对数化 `min(1, log(1+value/limit)/log(11))`
- **W**（用途权重，0-1）：不同用地类型下各因子的 AHP 权重
- **M**（模型贡献度，0-1）：SHAP 归一化贡献份额
- **S**（稳定性，0-1）：⚠️ **当前硬编码为 0.8，所有因子恒定**
- **E**（证据等级，0.3-1.0）：A/B/C/D 四级

设计理念：**规则主导 + 模型辅助**（R 权重 0.30 > M 权重 0.15）

---

## 二、数据流全链路

### 2.1 数据来源
```
甲方Excel检测数据 → import_service.parse() → FieldMapping(人工映射因子列) → ingest → DB
                                                                            ↓
                                                          FactorDictionary（因子字典，中文/符号命名）
                                                          Measurement（检测记录，factor_id 关联字典）
```

### 2.2 诊断调用链
```
POST /api/v1/sites/{id}/kos-diagnosis
  → diagnosis.py:165  从 Measurement join FactorDictionary 取 factor_name → {因子名: 最大值}
  → kos_service.py:117  normalize_factors() 把"镉"→"Cd_mgkg"（VALUE_TO_FEATURE 映射表）
  → kos_engine_v0.8.py:106  compute_kos() 计算 B/R/W/M/S/E → KOS 排序
  → 返回 key_obstacles + model_contribution
```

### 2.3 三套因子命名空间（⚠️ 可信性风险点）

| 层 | 命名样例 | 来源 |
|---|---|---|
| **导入数据（FactorDictionary）** | "镉""铜""pH""有机质""序号""上限""下限" | 甲方Excel列名直接入库 |
| **阈值表（StandardThreshold）** | "Cd""As""Cu""Pb"（纯符号） | GB15618/GB36600 国标 |
| **模型特征（SHAP/KOS）** | "Cd_mgkg""As_mgkg""Cu_mgkg"（符号+单位） | 训练集特征列名 |

`kos_service.py:73-83` 的 `VALUE_TO_FEATURE` 映射表是三套命名空间的**唯一桥梁**：
```python
VALUE_TO_FEATURE = {
    "镉": "Cd_mgkg", "Cd": "Cd_mgkg", "镉_Cd": "Cd_mgkg",
    "铅": "Pb_mgkg", "Pb": "Pb_mgkg",
    ...
}
```
**审核问题**：这个映射表是否完备？如果甲方数据用"镉Cd"或"Cd(镉)"或"Cd_mg/kg"等变体，能否匹配？

---

## 三、已发现的可信性问题（实测证据）

### 问题 A：个旧场地 Cd 完全缺失
**实测**：个旧HM场地（134点真实数据，2412条Measurement）提取的17个因子中
**没有"镉"也没有"Cd"**，只有 Cu/Pb/Zn/Fe。

- KOS 结果 key_obstacles 只有 As/Pb/Cu/Zn 4个，Cd 排不上——**因为数据里没有 Cd**
- 这是**数据层缺失**，非模型问题
- 但 KOS 权重表里 Cd=0.9（最高），说明方法学认为 Cd 最重要——数据与方法学预期不符

**审核问题**：甲方数据是否确实未检测 Cd？还是导入时因子映射遗漏？

### 问题 B：As 值 = 12420 mg/kg 异常
**实测**：个旧场地 As 最大值 = 12420 mg/kg。

- GB15618 砷筛选值 = 40 mg/kg，超标 310 倍
- 12420 mg/kg = 1.24%，这在土壤中极端罕见（锡矿渣区可能，但需核实）
- **可能是单位错误**（原始数据可能是 μg/kg = ppb，或 ppm 但需换算）

**审核问题**：这个值是真实的还是单位/导入错误？如果是错误，KOS 的 R=1.0（封顶）
虽然不受数值绝对量影响，但 R 的对数化计算 `log(1+12420/40)/log(11)` 确实封顶到 1.0，
导致 As 与轻度超标的因子 R 值无法区分。

### 问题 C：S=0.8 硬编码削弱因子区分度
**实测**：4 个 key_obstacles 的 S 全是 0.800。

KOS 的 S 项 = 0.20 × 0.8 = **0.16 恒定常数**，所有因子都获得这 0.16 分。

| 因子 | KOS | R项(0.30) | W项(0.25) | M项(0.15) | S项(0.20) | E项(0.10) |
|---|---|---|---|---|---|---|
| As | 0.8067 | 0.300 | 0.2125 | 0.0342 | **0.160** | 0.100 |
| Pb | 0.7767 | 0.300 | 0.2000 | 0.0167 | **0.160** | 0.100 |
| Cu | 0.7594 | 0.300 | 0.1875 | 0.0119 | **0.160** | 0.100 |
| Zn | 0.7553 | 0.300 | 0.1750 | 0.0203 | **0.160** | 0.100 |

观察：
- R 全是 1.000（全部超标封顶）→ R 项无区分度
- S 全是 0.800 → S 项无区分度
- 实际区分度只来自 W（0.175~0.2125）和 M（0.012~0.034）
- **M 的差异极小**（0.012 vs 0.034，绝对差 0.022），所以排名基本由 W 决定

**审核问题**：KOS 的区分度实际上几乎只取决于 W（用途权重），而非数据本身。
这是否违背了"数据驱动诊断"的初衷？S=0.8 硬编码的合理性？

### 问题 D：R 的对数封顶导致高超标区无区分度
R = min(1.0, log(1 + value/limit) / log(11))

- value/limit = 10 时 R = log(11)/log(11) = 1.0（封顶）
- 超标 10 倍和超标 310 倍的 R 都是 1.0

**审核问题**：封顶设为 10 倍是否合理？个旧这种超高超标场地，所有因子 R 都封顶，
完全丧失了"谁更严重"的区分能力。

### 问题 E：阈值表的简化
`kos_service.py:46-60` 的 PROD_THRESHOLDS 是**硬编码简化版**，非从数据库 StandardThreshold 读取：

```python
PROD_THRESHOLDS = {
    "Cd_mgkg": {"type": "upper", "limit": 0.6},  # GB15618 水田pH≤5.5
    "As_mgkg": {"type": "upper", "limit": 40},   # GB15618 水田pH≤5.5
    ...
}
```

但数据库里有 131 条 StandardThreshold（含 pH 条件、土壤类型条件等细分）。

**审核问题**：硬编码阈值忽略了 pH 分级、旱地/水田差异、农用地/建设用地差异。
这是否会导致误判？例如 pH>7.5 时 Cd 筛选值应是 0.8 而非 0.6。

### 问题 F：model_contribution 与 key_obstacles 口径
- `model_contribution`：从 SHAP CSV 的 `mean_abs_shap/total` 取值（已统一口径）
- `key_obstacles` 的 M：从 kos_engine 的 m_map 取值（也是 `mean_abs_shap/total`）

两者理论一致。但 key_obstacles 只含 B=1（超标）的因子，
model_contribution 含所有 measured 因子（可能含未超标的）。

**审核问题**：用户可能困惑"为什么模型贡献度图里有 Cu，但 key_obstacles 里 Cu 的 M 值不同"。
实际上 key_obstacles 的 Cu M=0.079，与 model_contribution 的 Cu contribution=0.079 一致。✓

---

## 四、AI 诊断结论的可信性

### 4.1 AI 润色 prompt（`ai_service.py:404-415`）
诊断摘要由 GLM-5.2 润色。prompt 要求：
- 禁止给出"优/良/中/差"整体安全性评价
- 禁止使用"安全/低风险/无风险"等结论
- 只复述超标因子、浓度、KOS 排名

### 4.2 事实校验（`ai_service.py:443-449`）
```python
if diagnosis_text and ("超标" in diagnosis_text or "障碍" in diagnosis_text):
    hallucination_kw = ("安全", "低风险", "无风险", "状况良好", "风险很低", "整体状况")
    if any(kw in reply for kw in hallucination_kw):
        return None  # 视为幻觉，回退模板
```

**审核问题**：
- 这个校验是否足够？如果原始诊断含"超标"，AI 输出"风险可控""整体平稳"等变体能否拦截？
- 回退到模板时，模板内容是否可靠？

---

## 五、需要审核者重点验证的问题

1. **数据-模型命名空间断裂**：`VALUE_TO_FEATURE` 映射表是否覆盖甲方所有可能的因子命名变体？
   未匹配的因子会被当作"未知有机物"处理（normalize_factors:104-105），是否合理？

2. **KOS 公式的实际区分度**：当所有超标因子 R 封顶=1.0、S 硬编码=0.8 时，
   KOS 排名是否实际上只反映 W（用途权重）？这算"数据驱动"还是"权重驱动"？

3. **阈值简化vs数据库精度**：硬编码的 11 个 PROD_THRESHOLDS vs 数据库的 131 条
   StandardThreshold（含 pH/土壤类型分级），简化版是否导致系统性误判？

4. **As=12420 mg/kg 数据真实性**：这个值是否反映真实的锡矿渣区砷污染，
   还是单位/导入错误？如果是错误，对整个场地结论的影响有多大？

5. **S=0.8 硬编码**：稳定性分量对所有因子恒定，是否应该改为动态计算
   （如基于重复样方差、检出率）？当前无重复样数据支撑，但恒定 0.8 是否比去掉 S 项更好？

6. **17/18 场地无诊断数据**：除个旧外，其余场地均无 DiagnosisResult。
   系统对这些场地生成的报告，诊断章节只能显示占位说明。这是否意味着
   系统的实际验证范围只覆盖了 1 个真实场地？

7. **AI 润色的幻觉防线**：事实校验只检查 6 个关键词，是否足够？
   审核者可尝试构造"原始诊断含超标，AI 输出看似正面但不含这6个词"的案例。

---

## 六、关键文件索引

| 文件 | 作用 |
|---|---|
| `ml/ranking/kos_engine_v0.8.py` | KOS 核心计算引擎（公式、B/R/W/M/S/E） |
| `backend/app/services/kos_service.py` | KOS 服务层（阈值、权重、因子映射、API调用入口） |
| `ml/explain/shap_contribution_filter.py` | SHAP 三态清洗（measured/family/missing/proxy） |
| `ml/explain/shap_service.py` | SHAP 计算服务 |
| `backend/app/services/ai_service.py` | AI 润色 prompt + 事实校验 |
| `backend/app/api/diagnosis.py:155-184` | KOS 诊断 API（数据提取→调用KOS） |
| `backend/app/services/diagnosis_service.py` | 诊断编排（含 calc_trace 文本生成） |
| `scripts/build_gold_dataset.py` | Gold Dataset v0.8 构建（数据冻结） |
| `reporting/templates/traceability_report.html` | 追溯报告模板 |
| `backend/app/services/report_service.py` | 报告生成（collect→render_html→PDF） |

## 七、可复现的验证命令

```bash
# 运行个旧场地KOS诊断（模拟API）
cd backend
python -c "
import sys; sys.path.insert(0, '.')
from app.db.session import SessionLocal
from app.models import Measurement, FactorDictionary
from app.services.kos_service import run_kos_diagnosis
db = SessionLocal()
rows = (db.query(Measurement.value, FactorDictionary.factor_name, FactorDictionary.factor_code)
        .join(FactorDictionary, Measurement.factor_id == FactorDictionary.id, isouter=True)
        .filter(Measurement.site_id == 1, Measurement.value.isnot(None)).all())
site_values = {}
for value, fname, fcode in rows:
    fn = fname or fcode
    if fn and value is not None:
        try:
            v = float(value)
            if fn not in site_values or v > site_values[fn]: site_values[fn] = v
        except: continue
result = run_kos_diagnosis(site_values, track='prod', subset='all')
for k in result.get('key_obstacles',[]):
    print(k['rank'], k['factor'], k['KOS'], k['components'])
"

# 检查因子命名空间
python -c "
import sys; sys.path.insert(0, '.')
from app.db.session import SessionLocal
from app.models import FactorDictionary, StandardThreshold
db = SessionLocal()
print('FactorDictionary:', [f.factor_name for f in db.query(FactorDictionary).limit(20)])
print('StandardThreshold:', [t.factor_name for t in db.query(StandardThreshold).filter(StandardThreshold.factor_name.isnot(None)).distinct().limit(15)])
"
```

---

*本文档由开发代理于 2026-07-16 整理。审核者应独立验证所有声明，而非采信文档结论。*
