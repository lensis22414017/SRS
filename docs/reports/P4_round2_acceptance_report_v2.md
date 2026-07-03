# P4 Round3 验收报告 v2

> 生成时间: 2026-07-03
> 响应: 裴总 Round2 验收未通过后的 P0 证据链修复
> 本报告与 BLOCKERS.md 严格一致,逐项给 通过/部分通过/未通过

---

## 裴总 7 条 P0 逐项

### 1. 是否真 15+3 → ✅ 通过
- validation_manifest.csv: **36 行 × 18 唯一场地**(3 真实 + 15 内部)
- 真实:个旧HM / 栖霞OP / 乡村HM+OP
- 内部:15 个从 Gold Dataset 按 source_id 采样(覆盖 HM/OP/composite)
- 双轨:每个场地 prod + eco = 36 行
- 字段完整:site_name/source/type/track/n_key/n_attention/n_family/n_unknown/review_required/status

### 2. 四层 KOS 是否都有文件证据 → ✅ 通过
| 文件 | 行数 | 真实记录 |
|---|---|---|
| model_attention_factors.csv | 92 | 各场地模型关注因子(无阈值实测+模型见过) |
| family_warnings.csv | 9 | 栖霞 PAH 族群未收录单体(苯并[a]蒽/芘/苯并[j]荧蒽等) |
| unknown_alerts.csv | 113 | 有机质/全氮/全磷/电导率等无阈值因子(送检建议) |
| kos_rankings.csv | 36 | 各场地 Top-5 |
| recommended_tests.csv | 108 | 补测建议 |

**栖霞 OP 8 族群 + 9 未知 现在有文件证据**(family_warnings 9行 + unknown_alerts 含栖霞记录)。

### 3. E2E 是否真非空 → 部分通过(9/10)
| 截图 | 状态 |
|---|---|
| login_admin | ✅ 112KB |
| site_list | ✅ 63KB |
| site_detail_nonblank | ✅ 69KB |
| **diagnosis_prod_result_top5** | ✅ **67KB(KOS 真实返回 key=4 attention=6)** |
| kos_top5_detail | ✅ 62KB(KOS 面板可见) |
| **diagnosis_eco_result_top5** | ✅ **67KB(生态轨 KOS 返回 key=4)** |
| reconstruction_reads_kos | ✅ 74KB |
| **recommendation_reads_kos** | ❌ **6KB 白屏(前端 leaflet/useRouteError 路由 bug)** |
| traceability_archive | ✅ 41KB |
| unauthorized_403 | ✅ 69KB |

**关键改进**:KOS prod/eco 截图通过 page.waitForResponse 拦截确认 API 真实返回了数据(key_obstacles=4),不再是空态。recommendation 白屏是前端路由 bug(后端 recommend_service 已确认读 KOS based_on_factors)。

### 4. report 是否读 KOS → ✅ 通过
6 份 DOCX 均读 KOS 四层(explicit_obstacles/key_obstacles/model_attention/family_warnings/unknown_alerts/recommended_tests/model_contribution),不读旧 importance。

### 5. API smoke 是否 7/7 → ✅ 8/8 通过
| 项 | 结果 |
|---|---|
| 登录 | ✅ |
| 模型注册表(6模型) | ✅ |
| all_prod approved | ✅ |
| op_prod exploratory | ✅ |
| 场地列表(n=3) | ✅ **(上轮 n=0 已修复)** |
| KOS诊断(key=4 att=6) | ✅ |
| 四层字段完整 | ✅ |
| 未授权401 | ✅ |

### 6. report 与 BLOCKERS 是否矛盾 → ✅ 已修正
- BLOCKERS.md 已重写,与本报告逐项一致
- 不再出现"Reconstruction 仍用旧 Top"等过时表述
- 追溯报告已改名"追溯档案样例_Alpha"(不冒充五阶段档案)

### 7. 追溯报告处理 → 选项 B(改名 Alpha)
6_追溯档案样例_Alpha.docx — 诚实标注为 Alpha 样例,非监管级全流程档案。不补五阶段材料(留下一轮)。

---

## 综合判定

| 维度 | 等级 |
|---|---|
| KOS 后端 Alpha | ✅ 通过 |
| 模型到 KOS 方法链 | ✅ 通过 |
| 四层输出证据 | ✅ 通过(92/9/113 行) |
| 15+3 验证 | ✅ 通过(36行/18场地) |
| E2E 前端证据 | ⚠️ 部分通过(9/10,recommendation 路由bug) |
| 报告样例 | ⚠️ 部分通过(DOCX 有,PDF 无,追溯降级Alpha) |
| 权限 smoke | ✅ 通过(12/12) |
| API smoke | ✅ 通过(8/8) |
| 第二阶段交付 | ⚠️ 接近(差 recommendation 路由修复 + PDF) |

## 是否可交给 Fable 5
**可以并行**:
- Fable 5 做 KOS 卡片视觉/报告版式/大屏/空态样式/演示 UI
- GLM5.2 同步修 recommendation 路由 bug + 补 PDF

**不建议**:Fable 5 接"最终交付"(因 recommendation 白屏 + 无 PDF 未解决)。

## KOS 四层规则(已钉死,本轮有文件证据)
```
正式 Top-N (key_obstacles): 实测 + 有阈值 + B=1 + E(A/B)  ← 严禁无阈值进入
模型关注 (model_attention): 实测 + 模型见过 + 无阈值 → 需复核  ← 92行证据
族群预警 (family_warnings): 未知单体归族群 → 不假装排名  ← 9行证据(栖霞PAH)
未知物 (unknown_alerts): 无法归类 → 送检  ← 113行证据
```
