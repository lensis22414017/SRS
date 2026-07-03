# Round7 报告图片嵌入校验

> 生成时间: 2026-07-03 | 校验脚本: `backend/scripts/validate_report_images.py`
> 校验标准: 每份 PDF/DOCX 图片数 > 0 (`--min-images 1`)

## 一、校验方法

| 格式 | 方法 | 依赖 |
|---|---|---|
| DOCX | 解压 zip 计 `word/media/` 下文件数 | 标准库 zipfile |
| PDF | 字节扫描 `/Subtype /Image` + `/Image` 标记 | 标准库(轻量法, 可选 pypdf 增强) |

低于 `--min-images`(默认1) 退出码 2。

## 二、Alpha 版报告校验结果(现状)

> Alpha 版 6 DOCX + 6 PDF 走 scripts 链路(generate_kos_reports.py / generate_kos_pdfs.py),
> 该链路纯表格/文字输出, **从不嵌入图片**。

| 文件 | 格式 | 图片数 | 通过 |
|---|---|---|---|
| 1_HM生产用途诊断报告 | DOCX | 0 | ❌ |
| 2_HM生态用途诊断报告 | DOCX | 0 | ❌ |
| 3_OP生产用途诊断报告 | DOCX | 0 | ❌ |
| 4_OP生态用途诊断报告 | DOCX | 0 | ❌ |
| 5_HM+OP复合污染诊断报告 | DOCX | 0 | ❌ |
| 6_追溯档案样例_Alpha | DOCX | 0 | ❌ |
| 1_HM生产用途诊断报告 | PDF | 0 | ❌ |
| 2_HM生态用途诊断报告 | PDF | 0 | ❌ |
| (其余 4 PDF 同理) | PDF | 0 | ❌ |

**结论**: Alpha 版 12 份报告图片数全部为 0, 校验 `passed: false`。

## 三、v2 版报告(待 generate_reports_with_maps.py 运行)

> Round6 已建 `scripts/generate_reports_with_maps.py`, 接入 `report_service.generate()` 全流程报告链路,
> 该链路自动嵌入 matplotlib 采样点散点图 + SHAP 排名图 + EDA 图。

**运行后预期**: v2 版 6 PDF + 6 DOCX 图片数 ≥ 1(地图散点图), 校验 `passed: true`。

运行命令(需后端启动 + DB 已导入场地):
```bash
cd backend && python ../scripts/generate_reports_with_maps.py
# 生成后校验:
python backend/scripts/validate_report_images.py artifacts/demo_reports_v2_20260703/*.pdf artifacts/demo_reports_v2_20260703/*.docx --min-images 1
```

> ⚠ v2 实际数字待运行后填入本表。

## 四、诚实说明

1. **Alpha 版 0 图片是已知问题**, 由 scripts 链路纯表格输出导致, Round6 已规划修复方案(接入 report_service)。
2. **v2 版报告需后端运行**才能产出, 当前脚本就绪但未运行(依赖运行时环境)。
3. **校验脚本本身正确**: 已确认能检测出 Alpha 版 0 图片(passed:false), 不会误报。
4. **报告地图限制**: matplotlib 离线散点, 无真实瓦片底图, 水印诚实标注。
