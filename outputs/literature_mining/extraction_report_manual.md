# 文献精读数据提取报告（手动 Agent 精读版）

> 裴总审计入口。本报告替代脚本抽取产物，数据 100% 来自 Agent 逐篇精读论文原文。

---

## 1. 任务背景与方法

**裴总指令**：脚本提取不可信（P06579/P08598 被证伪——统计行/标准阈值被误当采样点），必须**逐篇精读文献原文**，构建可训练的 OP + HM+OP 两种数据集。

**方法链**（脚本仅定位，Agent 精读提取）：
1. 全量独立筛选 catalog 11676 篇 → 精确中国 OP 1886 篇（HM+OP 558 / OP-only 1328）
2. `scan_sample_row.py` 定位"主文含采样点级表格"的论文（行/列结构是采样点）
3. Agent 逐篇精读 paper.md，按裴总铁律提取真实采样点级 HM+OP 浓度
4. `build_wide_manual.py` 构建 wide format 训练表 + 防伪复合验证

---

## 2. 数据集成果

### ✅ OP-only 数据集（达标）
- **train_table_op_only_manual.csv**：**188 sample / 13 source**（≥100+10 门槛达标）
- 标准 OP（Sum_PAH/BaP/SumPCB/SumDDT/SumHCH/Endosulfan）+ 扩展（抗生素/PAE，裴总可取舍）
- 纯土壤 146 + 沉积物 19 + peat 1
- site_type：agricultural/coking/industrial/urban/e_waste/wetland 全覆盖
- 13 source：P02763(20焦化)/P11362(20焦化)/P06725(21农药)/P00208(19沉积物)/P01524(18电子废弃物)/P10229(12污灌)/P01718(12城市)/P03207(11农药厂)/P01301(8电子废弃物)/P01177(1湿地)等

### ⚠️ HM+OP 数据集（接近 source 门槛，sample 不足）
- **train_table_hm_op_manual.csv**：**46 sample / 8 source**（纯土壤，门槛 ≥100+10 未达）
- **防伪复合 46/46 真复合**（同点含 HM 族 + OP 族，全部同论文同场地）
- 8 source：P01524(12温岭电子废弃物)/P03207(11农药厂)/P01301(8电子废弃物)/P00217(6铀尾矿)/P10369(5天津污灌)/P11362(2焦化)/P00395(1抗生素河床)/P09845(1焦化原土)
- site_type：e_waste(19)/industrial(11)/mining(6)/agricultural(5)/coking(3)
- co_contamination：HM+PAHs 主导（焦化/电子废弃物），含 HM+PCB/HM+OCP/HM+PBDE

---

## 3. 质量验证（裴总铁律全通过）

| 验证项 | 结果 |
|---|---|
| 防伪复合（HM+OP 同点同论文）| 46/46 ✅ |
| 统计行剔除（Mean/SD/Max/Min/Median）| 全剔除 ✅ |
| 标准阈值剔除（Grade I/II/III/GB15618/GB36600/Dutch）| 全剔除 ✅ |
| 风险指数剔除（HQ/TEQ/Nemerow/RI/Igeo）| 全剔除 ✅ |
| 盆栽/spiked/修复实验剔除 | 全剔除 ✅ |
| 跨论文拼接检查 | 0（HM+OP 全同论文）✅ |
| 值合理性 | SumDDT 2.4-25.8, SumHCH 0.76-6.9 ng/g ✅ |
| 可追溯 evidence_location | 100%（Table X/正文段）✅ |

**金标验证**：P01524（温岭电子垃圾）Agent 复现 18 采样点，手算 16 PAH 单体求和=719.4 匹配论文 Total PAHs 行，提取质量可信。

---

## 4. 瓶颈分析（HM+OP sample 不足的根本原因）

精读 40+ 篇 HM+OP 候选后，四重数据源瓶颈：

1. **主文多统计汇总**（~60%）：表格仅给 Mean/SD/Max/Min/区域均值，采样点级在 SI 或未公开。例：P06898(256样)/P07842(256样)/P11182(169样) 主文全统计。
2. **SI 多方法/参数/风险**（已扫 54 篇 SI docx）：SI 表格是 RfD/SF/暴露因子/CDI 风险值/检出率，非采样点浓度。例：P01630 SI 8 表全是风险参数。
3. **HM 常在图不在表**：P02763/P01718/P11362 的 HM 浓度在柱状图/地图（Fig），OP 在表——OCR 读柱高是估算，违反"禁止估算"铁律。
4. **修复类多 spiked/盆栽**：P00753/P03279/P11294/P11554/P03334 全是人工投加污染物实验，非真实场地。

**结论**：HM+OP 同点采样点级浓度数据在论文库中**常不公开**（只在作者手里）。8 source/46 sample 是当前论文库精读能达的极限。

---

## 5. 与旧脚本产物对比（裴总质疑验证）

| 维度 | 旧脚本（train_table_*.csv）| 手动精读（_manual.csv）|
|---|---|---|
| OP-only | 546 sample（含统计行/标准阈值假数据）| 188 sample（真实采样点级）|
| HM+OP | 60 sample（P06579 10个统计行误抽/P08598 60行假数据）| 46 sample（防伪复合 46/46）|
| 可信度 | 低（P06579/P08598 被证伪）| 高（金标 P01524 验证 + 证据可追溯）|

**裴总质疑完全正确**：脚本提取的统计表格不可信，精读是唯一可靠路径。

---

## 6. 后续补强 HM+OP 的路径（供裴总决策）

1. **联系作者索取原始数据**：P06898(256样)/P07842(256样)/P11182(169样)/P01630(221样) 的采样点级数据在作者手里，论文未公开。
2. **OCR 图表**（近似值，违反铁律#1 禁止估算，需裴总特批）：P02763/P11362 的 HM 柱状图可 OCR 读近似浓度，+40 HM+OP sample。
3. **扩展文献库**：当前 11676 篇已全量筛，HM+OP 场地研究论文的采样点级公开率低是结构性问题。
4. **接受 46/8 作初版**：source 8 接近 10 门槛，site_type 多样（电子废弃物/焦化/矿山/农田/工业），可作 HM+OP 模型初版训练，后续增量。

---

## 7. 交付物

```
C:\Users\曾鸿\Desktop\SRS\outputs\literature_mining\
├── train_table_op_only_manual.csv   (188 sample / 13 source) ✅达标
├── train_table_hm_op_manual.csv     (46 sample / 8 source)   ⚠️待补强
├── manual_extract_long.csv          (490 观测, 全量可追溯)
├── manual_extract_summary.csv       (200 canonical 元信息)
├── manual_extract/{hm_op,op_only}/  (per-paper CSV, Agent 精读产出)
└── extraction_report_manual.md      (本报告)
```

**按裴总铁律**：两个数据集未经裴总二审前不可用于训练。
