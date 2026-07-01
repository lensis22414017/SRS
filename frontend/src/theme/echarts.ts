/** ECharts 全局主题 — SVG 渲染 + Nature 三色 + 统一 tooltip 样式 */
import * as echarts from "echarts";
import { POLLUTION_TYPE, CATEGORICAL } from "./palette";

echarts.registerTheme("srs-light", {
  color: [
    POLLUTION_TYPE.heavy_metal,
    POLLUTION_TYPE.organic,
    POLLUTION_TYPE.composite,
    ...CATEGORICAL,
  ],
  backgroundColor: "transparent",
  textStyle: {
    fontFamily: "PingFang SC, Microsoft YaHei, Helvetica Neue, sans-serif",
  },
  tooltip: {
    backgroundColor: "rgba(255,255,255,0.96)",
    borderColor: "#e2e8f0",
    borderWidth: 1,
    textStyle: { color: "#1e293b", fontSize: 13 },
  },
});

// 统一 opts: 全局 SVG 渲染
export const SVG_OPTS = { renderer: "svg" as const };
