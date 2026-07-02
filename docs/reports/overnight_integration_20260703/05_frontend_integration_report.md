# 05 前端集成报告

## 结果: ✅ 通过

## 改动的页面

### 1. 障碍因子分析页 (ObstacleAnalysis.tsx)
- ✅ 新增"运行生产用途诊断(KOS)"按钮(紫色)
- ✅ 新增"运行生态用途诊断(KOS)"按钮(绿色)
- ✅ 新增 KOS 三层输出面板:
  - 第一层:关键障碍因子 Top-N(KOS 评分排序 + 进度条 + R/W/M/S/E Tooltip + 证据等级 Badge)
  - 第二层:模型贡献度横向条形图(不写"SHAP",写"贡献份额")
  - 第三层:建议补测因子表(未实测重要因子)
- ✅ 数据质量提示(Alert):OP 探索性 / 族群未收录 / 完全未知物质
- ✅ review_required 红色标记
- ✅ interpretation_note 页脚声明(模型贡献度,非因果)
- ✅ 双轨 Tag 切换(生产紫/生态绿)
- TypeScript 编译通过(npx tsc --noEmit 无错误)

### 2. 场地详情页 (SiteDetail.tsx)
- ✅ 新增"运行生产用途诊断(KOS)"按钮入口
- ✅ 新增"运行生态用途诊断(KOS)"按钮入口

### 3. client.ts API 层
- ✅ kosDiagnosis(id, track, subset) 方法
- ✅ modelRegistry() 方法

## API 联调验证(云南个旧真实数据)
```
生产轨: Pb(KOS=0.800) > Cu(0.792) > As(0.776) > Zn(0.774)
生态轨: Pb(0.797) > As(0.792) > Cu(0.751) > Zn(0.735)
补测: 7项  复核: True  数据质量: 9个完全未知物质
```
结果物理合理(个旧是铅砷矿区),双轨有差异(生态 As 权重更高)。

## 前端文案规范(已落实)
| ❌ 禁止 | ✅ 已改 |
|---|---|
| SHAP 值 | 模型贡献度 |
| 障碍高度 | KOS 综合评分 |
| x_missing_* | 不展示 |
| 因果 | 非因果声明 |

## 未完成(留给下一轮)
- ReconstructionAnalysis.tsx 读 KOS Top 作限制因子(当前仍用旧 Top)
- RecommendationPage.tsx 按 KOS 因子匹配技术库
- SSUI 页面数据不足提示
