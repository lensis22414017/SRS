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

echarts.registerTheme("srs-dark", {
  color: [
    "#1e90ff",
    "#00d4ff",
    "#7b68ee",
    "#00b894",
    "#f0b429",
    "#ff6b6b",
    "#fd79a8",
    "#a29bfe",
  ],
  backgroundColor: "transparent",
  textStyle: {
    color: "#8899bb",
    fontFamily: "PingFang SC, Microsoft YaHei, Helvetica Neue, sans-serif",
  },
  title: {
    textStyle: { color: "#a0b8d8" },
  },
  tooltip: {
    backgroundColor: "rgba(12, 24, 48, 0.95)",
    borderColor: "rgba(30,144,255,0.2)",
    borderWidth: 1,
    textStyle: { color: "#c8d6e5", fontSize: 13 },
  },
  legend: {
    textStyle: { color: "#8899bb" },
  },
  xAxis: {
    axisLine: { lineStyle: { color: "rgba(255,255,255,0.06)" } },
    axisTick: { lineStyle: { color: "rgba(255,255,255,0.06)" } },
    splitLine: { lineStyle: { color: "rgba(255,255,255,0.06)" } },
  },
  yAxis: {
    axisLine: { lineStyle: { color: "rgba(255,255,255,0.06)" } },
    axisTick: { lineStyle: { color: "rgba(255,255,255,0.06)" } },
    splitLine: { lineStyle: { color: "rgba(255,255,255,0.06)" } },
  },
});

// 统一 opts: 全局 SVG 渲染
export const SVG_OPTS = { renderer: "svg" as const };
