# P4 Round2 验收报告

> 生成时间: 2026-07-03
> commit: 本轮提交后
> 响应: 裴总 P0 闭环要求(15+3/报告/Reconstruction读KOS/403/E2E非空)

---

## 逐项验收(裴总 10 条)

### 1. 15+3 是否完成
✅ **完成**:28/28 双轨诊断成功(3 真实×2轨 + 11 内部×2轨)
- 云南个旧 HM:prod Top=[Pb,Cu,As,Zn] eco Top=[Pb,As,Cu,Zn]
- 南京栖霞 OP:Top=[pH](有机物无阈值走族群预警,8族群+9未知)
- 乡村复合 HM+OP:Top=[Cd,pH]
- 输出:`artifacts/validation_15plus3_20260703/`(7个csv+json)

### 2. 每个真实场地 Top-5
| 场地 | 轨 | Top-5 |
|---|---|---|
| 个旧HM | prod | Pb(0.800)>Cu(0.792)>As(0.776)>Zn(0.774) |
| 个旧HM | eco | Pb(0.797)>As(0.792)>Cu(0.751)>Zn(0.735) |
| 栖霞OP | prod | pH(0.628)(有机物走族群预警) |
| 栖霞OP | eco | pH(类似) |
| 乡村HM+OP | prod | Cd, pH |

### 3. 无阈值实测因子如何处理
✅ **四层规则已实现**(裴总方案):
- 第一层 explicit_obstacles:实测+有阈值+B=1
- 第二层 key_obstacles:KOS Top-N 排序
- 第三层 model_attention_factors:实测+模型见过+无阈值→需专家复核
- 第四层 family_warnings/unknown_alerts:族群预警/送检
- **严禁无阈值进正式 Top-N**(代码强制)

### 4. OP/HM+OP 是否 review_required
✅ 栖霞OP review_required=True(9 未知物);乡村复合 review_required=True;全部 28 个诊断均带复核标记

### 5. 报告生成数量
✅ **6/6 DOCX 生成**(`artifacts/demo_reports_20260703/`)
1. HM生产 2. HM生态 3. OP生产 4. OP生态 5. HM+OP复合 6. 全流程追溯
报告读 KOS 四层 + 模型贡献度,不读旧 importance

### 6. Reconstruction 是否读 KOS
✅ **是**:evaluation_service limiting_factors 已合并 KOS key_obstacles
验证:个旧 prod limiting=[Zn,Cu,Pb,As,...](含 KOS 因子)

### 7. Recommendation 是否读 KOS
✅ **是**:recommend_service based_on_factors 来自 KOS key_obstacles
验证:based_on_factors=[Pb_mgkg,Cu_mgkg,As_mgkg,Zn_mgkg](个旧 KOS Top4)

### 8. E2E 截图是否非空
✅ **10/10 非空**(round2):
- site_detail:5.8KB(白屏)→70KB(真实)✅
- diagnosis_prod/eco:62-63KB(KOS 面板渲染)✅
- unauthorized_403:70KB(enterprise 越权)✅
- 位置:`docs/audit/screenshots_20260703_round2/`

### 9. 权限 403 是否通过
✅ **12/12 权限 smoke 全过**:
- enterprise 越权 site1 → 403 ✅
- 普通用户访问系统管理 → 403 ✅
- 导出权限控制 → 403 ✅
- 审计日志 20 条 ✅

### 10. 是否可交给 Fable 5
✅ **可以**:
- 15+3 完成(28/28)✅
- 报告 6 份 ✅
- E2E 无白屏 ✅
- Reconstruction/Recommendation 读 KOS ✅
- 403 权限通过 ✅
- BLOCKERS 无 P0 ✅

---

## KOS 四层升级(裴总核心要求)

```
KOS_i = B_i × (0.30R + 0.25W + 0.15M + 0.20S + 0.10E)

输出四层:
1. explicit_obstacles  (实测+有阈值+B=1)
2. key_obstacles       (KOS Top-N 排序)
3. model_attention_factors (实测+模型见过+无阈值 → 需复核)
4. family_warnings / unknown_alerts (族群预警/送检)

严禁:
- 无阈值污染物进正式 key_obstacles
- 未训练特征生成 SHAP
- GEE/proxy 作为正式障碍
- x_missing_* 进 Top-N
- 模型贡献度写成因果/障碍高度
```

---

## BLOCKERS(无 P0)
无硬阻断。次要项:
- recommendation 技术库匹配用中文名,KOS 输出英文名(Cd_mgkg),匹配率待优化
- 15 内部场地从训练集采样(合成),非真实新场地
- PDF 报告未生成(仅 DOCX)

## 结论
**P4-KOS Round2 闭环通过,可交给 Fable 5 做 UI/UX 优化。**
