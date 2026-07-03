# 第二阶段 15+3 场地批量验证报告 (Round 6)

> 生成时间: 2026-07-04 00:21 | 脚本: `scripts/run_round6_batch_validation.py`
> 真实场地: 3 个(DB id 1/2/3, 走 API 全 11 环节)
> 内部场地: 15 个(parquet 采样, 走 KOS service 直调, 诚实标注 N/A)

## 一、总体通过率

| 环节 | 通过/总数 | 通过率 |
|---|---|---|
| KOS 生产轨 | 18/18 | 100% |
| KOS 生态轨 | 18/18 | 100% |
| 功能重构 | 3/3 | 100% (仅真实场地) |
| SSUI | 3/3 | 100% (仅真实场地) |
| 方案推荐 | 0/3 | 0% (仅真实场地) |
| PDF 报告 | 0/3 | 0% |
| DOCX 报告 | 0/3 | 0% |
| 地图端点 | 0/3 | 0% |
| 权限隔离(403) | 0/3 | 0% |
| 需人工复核 | 18/18 | — |

## 二、逐场地明细(16 字段)

| site_id | site_name | type | region | n_points | prod | eco | recon | ssui | recommend | pdf | docx | map | screenshot | errors | review |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 云南个旧(HM) | heavy_metal | 云南 | 2 | pass | pass | pass | pass | fail(500) | fail(405) | fail(405) | fail(404) | 待节八 | 无 | 是 |
| 2 | 南京栖霞(OP) | organic | 江苏 | 200 | pass | pass | pass | pass | fail(500) | fail(405) | fail(405) | fail(404) | 待节八 | 无 | 是 |
| 3 | 乡村复合(HM+OP) | composite | 未知 | 24 | pass | pass | pass | pass | fail(500) | fail(405) | fail(405) | fail(404) | 待节八 | 无 | 是 |
| INT-1 | 内部#1(10.30955/g) | heavy_metal | Central Greece | 8 | pass | pass | N/A(内部) | N/A(内部) | N/A(内部) | N/A(内部) | N/A(内部) | N/A(内部) | 待节八 | 无 | 是 |
| INT-2 | 内部#2(10.1016/j.) | heavy_metal | Guizhou | 6 | pass | pass | N/A(内部) | N/A(内部) | N/A(内部) | N/A(内部) | N/A(内部) | N/A(内部) | 待节八 | 无 | 是 |
| INT-3 | 内部#3(10.1007/s1) | heavy_metal | unknown | 10 | pass | pass | N/A(内部) | N/A(内部) | N/A(内部) | N/A(内部) | N/A(内部) | N/A(内部) | 待节八 | 无 | 是 |
| INT-4 | 内部#4(10.1080/15) | heavy_metal | Asante | 7 | pass | pass | N/A(内部) | N/A(内部) | N/A(内部) | N/A(内部) | N/A(内部) | N/A(内部) | 待节八 | 无 | 是 |
| INT-5 | 内部#5(10.1007/s1) | heavy_metal | 湖南 | 7 | pass | pass | N/A(内部) | N/A(内部) | N/A(内部) | N/A(内部) | N/A(内部) | N/A(内部) | 待节八 | 无 | 是 |
| INT-6 | 内部#6(10.17221/4) | heavy_metal | Henan | 4 | pass | pass | N/A(内部) | N/A(内部) | N/A(内部) | N/A(内部) | N/A(内部) | N/A(内部) | 待节八 | 无 | 是 |
| INT-7 | 内部#7(10.1021/ac) | heavy_metal | Shandong | 2 | pass | pass | N/A(内部) | N/A(内部) | N/A(内部) | N/A(内部) | N/A(内部) | N/A(内部) | 待节八 | 无 | 是 |
| INT-8 | 内部#8(10.3184/09) | heavy_metal | Belgrade | 10 | pass | pass | N/A(内部) | N/A(内部) | N/A(内部) | N/A(内部) | N/A(内部) | N/A(内部) | 待节八 | 无 | 是 |
| INT-9 | 内部#9(10.1038/s4) | heavy_metal | 新疆 | 5 | pass | pass | N/A(内部) | N/A(内部) | N/A(内部) | N/A(内部) | N/A(内部) | N/A(内部) | 待节八 | 无 | 是 |
| INT-10 | 内部#10(10.1016/j.) | heavy_metal | Valparaíso | 7 | pass | pass | N/A(内部) | N/A(内部) | N/A(内部) | N/A(内部) | N/A(内部) | N/A(内部) | 待节八 | 无 | 是 |
| INT-11 | 内部#11(10.1016/j.) | heavy_metal | Buenos Aires | 5 | pass | pass | N/A(内部) | N/A(内部) | N/A(内部) | N/A(内部) | N/A(内部) | N/A(内部) | 待节八 | 无 | 是 |
| INT-12 | 内部#12(10.1007/s1) | heavy_metal | Zonguldak | 12 | pass | pass | N/A(内部) | N/A(内部) | N/A(内部) | N/A(内部) | N/A(内部) | N/A(内部) | 待节八 | 无 | 是 |
| INT-13 | 内部#13(10.21203/r) | heavy_metal | Maharashtra | 2 | pass | pass | N/A(内部) | N/A(内部) | N/A(内部) | N/A(内部) | N/A(内部) | N/A(内部) | 待节八 | 无 | 是 |
| INT-14 | 内部#14(10.1007/s1) | heavy_metal | Nakhon Pathom | 2 | pass | pass | N/A(内部) | N/A(内部) | N/A(内部) | N/A(内部) | N/A(内部) | N/A(内部) | 待节八 | 无 | 是 |
| INT-15 | 内部#15(10.1038/s4) | heavy_metal | Shanghai | 13 | pass | pass | N/A(内部) | N/A(内部) | N/A(内部) | N/A(内部) | N/A(内部) | N/A(内部) | 待节八 | 无 | 是 |

## 三、诚实说明

1. **内部场地仅验证 KOS 双轨链路**: 功能重构/SSUI/方案推荐/报告/地图环节标注 N/A。
   原因: 内部合成场地无完整阈值上下文与采样点地理坐标, 重构/SSUI/报告无意义。
2. **权限隔离**: 用 regulator 账号(只读, 无 data:input)尝试导入, 期望返回 401/403。
3. **截图**: 本表 screenshot_status 标'待节八', 实际由 Playwright round6 脚本产出。
4. **不写'全部完成'**: 任何 fail/N/A 如实标注。
