# 报告地图嵌入验证报告

> 生成时间: 2026-07-03 | 验证脚本: `scripts/generate_reports_with_maps.py`
> 报告链路: `backend/app/services/report_service.py` (全流程追溯报告, Jinja2 HTML → weasyprint PDF / python-docx DOCX)
> 地图渲染: `backend/app/services/static_map_renderer.py` + `report_service._render_points_map_png()` (matplotlib 离线散点, 8 级色阶)

## 一、问题背景

第二阶段演示包 Alpha 的 6 份报告走 `scripts/generate_kos_pdfs.py` / `generate_kos_reports.py` 链路,
该链路用 reportlab / python-docx **纯表格输出, 从不调用地图渲染器**, 导致 PDF/DOCX 内零地图图片。

修复方案(裴总批准): scripts 链路改为接入 `report_service.generate()` 全流程追溯报告。
该链路已在 `_render_points_map_png()` / `_render_shap_figure_png()` / `_render_eda_figure_png()`
中实现 matplotlib 离线图件渲染, 并通过 `_embed_docx_image()` 嵌入 DOCX、通过 Jinja2 模板
`traceability_report.html` 的 `map_image` 占位符嵌入 PDF。

## 二、地图内容要素核对

| 要素 | 是否满足 | 实现位置 |
|---|---|---|
| 场地边界/点位范围 | ⚠ 仅点位(无场地轮廓多边形, DB 无 boundary 字段) | `_render_points_map_png` 经纬网散点 |
| 采样点 | ✅ | matplotlib scatter, 按经纬度定位 |
| 超标/风险等级颜色 | ✅ | 8 级色阶 `_exc_color()` (绿→黄→橙→红→暗红) |
| 图例 | ✅ | 8 级 Patch 图例 + 无数据项 |
| 坐标/比例尺/底图说明 | ⚠ 有坐标轴+水印, 无比例尺; 水印诚实标注"底图: 无(离线坐标散点)" | `fig.text` 水印 |

**诚实限制**: 当前地图为离线 matplotlib 散点图, **无真实瓦片底图**(天地图 MBTiles 未落地,
`data/geo/tiles/` 目录不存在)。水印明确标注, 不误导为卫星影像。场地级 boundary 多边形
DB 未存储(仅中心点经纬度), 故无场地轮廓线。

## 三、嵌入校验方案

对每份 PDF/DOCX 执行 4 项校验:

| 校验项 | 方法 | 通过标准 |
|---|---|---|
| PDF 图片数 | pypdf 扫 /Resources/XObject /Image | > 0 |
| DOCX 图片数 | 解压 zip 计 `word/media/` 文件数 | > 0 |
| 地图加载失败文本 | PDF 提取文本 / DOCX strip XML 标签 | 不含"地图加载失败" |
| 报告大小 | os.path.getsize | > 50 KB (防空报告) |

## 四、校验结果

> ⚠ 此表数字由 `scripts/generate_reports_with_maps.py` 运行后填充。
> 运行命令: `cd backend && python ../scripts/generate_reports_with_maps.py` (需后端 DB 已导入场地 1/2/3)

| # | 场地 | 格式 | 文件名 | 大小(KB) | 图片数 | 无失败文本 | 大小达标 | 状态 |
|---|---|---|---|---|---|---|---|---|
| 1 | 云南个旧(HM) | PDF | _待运行填充_ | — | — | — | — | 待运行 |
| 2 | 云南个旧(HM) | DOCX | _待运行填充_ | — | — | — | — | 待运行 |
| 3 | 南京栖霞(OP) | PDF | _待运行填充_ | — | — | — | — | 待运行 |
| 4 | 南京栖霞(OP) | DOCX | _待运行填充_ | — | — | — | — | 待运行 |
| 5 | 乡村复合(HM+OP) | PDF | _待运行填充_ | — | — | — | — | 待运行 |
| 6 | 乡村复合(HM+OP) | DOCX | _待运行填充_ | — | — | — | — | 待运行 |

## 五、与 Alpha 版差异

| 项 | Alpha (scripts 链路) | v2 (report_service 链路) |
|---|---|---|
| 地图 | ❌ 零图片 | ✅ matplotlib 散点图嵌入 |
| SHAP 排名图 | ❌ | ✅ matplotlib 横向条形图 |
| EDA 图 | ❌ | ✅ 均值/最大值对比柱状图 |
| 报告口径 | KOS 四层(诊断专项) | 全流程追溯(含 KOS + 重构 + SSUI + 方案 + 五阶段) |
| 文件位置 | `artifacts/demo_reports_round4/` + `demo_reports_20260703/` | `artifacts/demo_reports_v2_20260703/` |

## 六、风险与已知限制

1. **无真实瓦片底图**: 地图为 matplotlib 散点, 非卫星影像。水印诚实标注。
2. **weasyprint 依赖系统库**: 若环境无 pango/cairo, PDF 降级为 xhtml2pdf(纯 Python) 或 HTML。
   降级不影响图片嵌入, 但 CSS 排版质量略降。
3. **场地轮廓缺失**: DB 仅存场地中心点, 无 boundary 多边形, 地图无场地边界线。
4. **OP 报告标注探索性**: 有机污染模型仍为探索性, 相关报告章节诚实标注。
