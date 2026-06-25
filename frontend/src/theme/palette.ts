// 全局配色系统 — 对齐裴总精品案例审美(低饱和灰蓝紫莫兰迪, 政府稳重 + 顶刊高级感)
//
// 配色源(实证): /Users/lensis/Desktop/Python可视化代码精品案例合集 高频 hex 统计
//   #515a85(74次最高频) #414f76 #214e81 #3680ae #81b7d9 #8e93af #e98184 #e8cda5
// 设计原则:
//   1. 低饱和度(chroma 低) + 中明度 → 莫兰迪/高级灰, 区别于 SaaS 高饱和活力色
//   2. 色盲友好: 避免纯红绿并列, 用蓝/粉/黄区分(顶刊 Nature/Science 要求)
//   3. 单一数据源: 全站引用本常量, 配色调整只改这一个文件
//   4. 语义色与装饰色分离: 状态判定用 SEMANTIC, 图表分类用 CATEGORICAL

// ── 分类色板(定性, pie/bar 多系列) ─ 裴总精品案例高频色降饱和排列 ──
export const CATEGORICAL = [
  "#515a85",  // 灰蓝紫(主色, 裴总案例 74 次最高频)
  "#3680ae",  // 中蓝
  "#81b7d9",  // 浅蓝
  "#8e93af",  // 灰紫
  "#e98184",  // 粉红(暖对比)
  "#e8cda5",  // 米黄
  "#c2768b",  // 玫粉
  "#9dc1c5",  // 灰青
];

// ── 主色系(政务深蓝, 与 main.tsx ConfigProvider token colorPrimary 一致) ──
export const PRIMARY = "#0f3d6e";          // 政务深蓝(token 主色)
export const PRIMARY_DEEP = "#214e81";     // 裴总深蓝
export const PRIMARY_MID = "#3680ae";      // 中蓝
export const PRIMARY_LIGHT = "#81b7d9";    // 浅蓝
export const PRIMARY_MORANDI = "#515a85";  // 莫兰迪灰蓝紫(裴总主色)

// ── 语义色(保留: 状态/等级判定用, 非装饰; 饱和度较高以确保警示性) ──
export const SUCCESS = "#16a34a";  // 达标/可行/低风险
export const WARNING = "#f59e0b";  // 警告/中度
export const DANGER = "#dc2626";   // 超标/危险/不可行
export const INFO = "#3b82f6";     // 信息/中高

// ── 发散色板(相关矩阵热力图: 负相关红 → 0 白 → 正相关蓝) ──
export const DIVERGING = ["#b91c1c", "#fee2e2", "#f8fafc", "#dbeafe", "#0f3d6e"];

// ── 连续色板(超标倍数/浓度渐变: 浅 → 深蓝) ──
export const SEQUENTIAL = ["#dee5ef", "#c6d3e2", "#81b7d9", "#3680ae", "#214e81"];

// ── 中性色(文本/边框/背景) ──
export const NEUTRAL_TEXT = "#64748b";
export const NEUTRAL_BORDER = "#d9e2ec";
export const NEUTRAL_BG = "#f8fafc";

// ── 仪表盘等级色(从低到高, 用于 SSUI/重构可行性仪表盘 axisLine) ──
// 格式: [累计占比阈值, 颜色]
export const GAUGE_STOPS: [number, string][] = [
  [0.4, DANGER],   // <40 低/不可行
  [0.6, WARNING],  // 40~60 中
  [0.8, INFO],     // 60~80 中高
  [1, SUCCESS],    // >80 高/可行
];
