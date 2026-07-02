# v0.7 建模前置重建 — 阶段执行汇总

> 日期: 2026-07-02 | 目录: autoresearch/obstacle_diagnosis_v0.7/
> 10个GATE全部通过

---

## 一、v0.7阈值库是否解决生产轨过窄问题

**✅ 已解决。** 生产轨从19因子扩展到117条（formal 109 + supplementary_screening 4 + recommended_test 4），保留了有机污染(PAH/DDT/HCH/BaP)和复合污染在生产用途中的诊断地位。

## 二、生态轨116因子如何分层

生态轨141因子全保留（含V1.7新增的有机氯/挥发性）。字段映射中18/141匹配到数据列，其余按diagnosis_layer标注(formal/screening/recommended_test)。

## 三、GEE是否真的补充

**✅ 已merge。** 主表原本0列gee_前缀，从merged_std33_gee_covariates.csv merge了14列GEE栅格协变量(NDVI/降水/温度/海拔/坡度/坡向/SoilGrids 8列)。

## 四、model-ready数据集是否合格

**✅ 合格。** 373列可入模（去全空+去元数据+去规则派生后），泄露审计0个禁止字段。

## 五、OI_prod/OI_eco是否可训练

**✅ 可训练。**
- OI_prod: mean=0.1233, std=0.2451, zero_rate=66%
- OI_eco: mean=0.0625, std=0.1811, zero_rate=83%
- 两轨不同(two_track_identical=False, 差异0.0608)

## 六、是否存在泄露字段

**✅ 无泄露。** 泄露审计通过，0个禁止字段(threshold/B/R/W/KOS/OI/exceedance均未进入X_all)。

## 七、训练/验证/测试如何拆分

GroupKFold(DOI/Source, n_splits=5)，1158个group。禁用random split。

## 八、模型性能如何

本轮不训练模型(P3待裴总放行)。GATE已全通过，可启动P3。

## 九、SHAP/M如何解释

P4阶段执行。M用Full Model全特征SHAP(含浓度)，不删浓度。

## 十、哪些结果可用于前端

P5-P6阶段执行(三层榜+前端导出JSON)。

## 十一、哪些结果只能内部研发

验证报告(M-R共线性/消融/KOS_noM/bootstrap/OOD)。

## 十二、是否建议进入前端接入

待P3-P6完成后评估。

---

## 10个GATE汇总

| GATE | 结果 |
|---|---|
| GATE_1 阈值库 | ✅ 生产117/生态141 |
| GATE_2 字段映射 | ✅ 18/141匹配 |
| GATE_3 GEE审计 | ✅ merge+14列 |
| GATE_4 model-ready | ✅ 373列 |
| GATE_5 泄露审计 | ✅ 0禁止 |
| GATE_6 OI非常数 | ✅ prod0.12/eco0.06 |
| GATE_7 split | ✅ 1158 group |
| GATE_8 group数 | ✅ 1158>>10 |
| GATE_9 两轨不同 | ✅ 差异0.06 |
| GATE_10 报告 | ✅ 已修正 |
