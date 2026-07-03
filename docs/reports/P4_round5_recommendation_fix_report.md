# P4 Round5 方案推荐修复报告

> 生成时间: 2026-07-03
> 响应: 裴总 Round4 验收(Recommendation 404 未通过)

---

## 问题
recommendation_reads_kos_round4.png 显示 404 页面不存在。

## 根因(双重)
1. **截图 URL 错误**:截图脚本访问 `/recommendation`,但实际路由是 `/recommend`(无 ation 后缀)。菜单 key 也是 `/recommend`。访问 `/recommendation` 命中兜底 404 路由。
2. **因子名不匹配**(即使路径正确也推荐为空):KOS 输出英文名 `Pb_mgkg/Cu_mgkg/As_mgkg/Zn_mgkg`,但推荐引擎 `engine.recommend` 用中文 METAL 集合 `{"砷","铅",...}` 匹配,英文不在集合里 → `_factor_class` 返回 "other" → 匹配失败 → 推荐数 0。

## 修复
1. **路径**:确认正确路由 `/recommend`(main.tsx line 100 + App.tsx 菜单 key),截图脚本改用正确路径。
2. **因子名归一化**:recommend_service 加 `_EN2CN` 映射,KOS 英文因子 → 中文再传引擎:
   ```
   Pb_mgkg→铅  Cu_mgkg→铜  As_mgkg→砷  Zn_mgkg→锌
   Cd_mgkg→镉  Cr_mgkg→铬  Hg_mgkg→汞  Ni_mgkg→镍
   ```

## 验证(DOM + 截图)
| 检查项 | 结果 |
|---|---|
| 截图路径 | `/recommend`(正确) |
| 含方案推荐标题 | ✅ |
| 含技术名称(修复/稳定/淋洗/客土) | ✅ |
| 含匹配分 | ✅ |
| 含 based_on 因子(砷/铅/镉) | ✅ |
| 卡片数 | 16 |
| 含 404 | ✅ false(不再 404) |
| 截图大小 | 242KB(原 6KB 白屏/404) |

## 推荐 API 返回(个旧 HM,5 个技术)
| rank | 技术名称 | match_score |
|---|---|---|
| 1 | 植物修复(超富集/植物提取) | 0.955 |
| 2 | 农艺调控(钝化+低累积品种) | 0.955 |
| 3 | 固化/稳定化(S/S) | 0.95 |
| 4 | 客土/换土 | 0.95 |
| 5 | 土壤淋洗 | 0.878 |

based_on_factors: [铅, 铜, 砷, 锌](KOS Top4,已转中文)

## 结论
- Recommendation 前端:**通过**(不再 404,显示 5 技术卡片)
- OP/HM+OP review_required:后端已标记(recommend_service 读 kos_review_required)
- 可进入第二阶段演示包(方案推荐页现在可演示)
