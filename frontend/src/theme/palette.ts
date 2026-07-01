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

// ── 主色系(蓝灰科技风, 与 main.tsx ConfigProvider token colorPrimary 一致) ──
// 裴总: 更现代的蓝灰科技风(类 Linear/Vercel 但政务克制) — 降饱和、加中性灰、冷调
export const PRIMARY = "#2c5282";          // 蓝灰科技主色(冷调克制, 原 #0f3d6e 政务深蓝)
export const PRIMARY_DEEP = "#1e3a5f";     // 深蓝灰(悬停/强调)
export const PRIMARY_MID = "#3b82f6";      // 科技亮蓝(交互高亮/accent)
export const PRIMARY_LIGHT = "#93c5fd";    // 浅科技蓝
export const PRIMARY_MORANDI = "#515a85";  // 莫兰迪灰蓝紫(图表保留, 不作主色)

// ── 语义色(保留: 状态/等级判定用, 非装饰; 饱和度较高以确保警示性) ──
export const SUCCESS = "#16a34a";  // 达标/可行/低风险
export const WARNING = "#f59e0b";  // 警告/中度
export const DANGER = "#dc2626";   // 超标/危险/不可行
export const INFO = "#3b82f6";     // 信息/中高

// ── 发散色板(相关矩阵热力图: 负相关红 → 0 白 → 正相关蓝, 蓝端对齐 PRIMARY) ──
export const DIVERGING = ["#b91c1c", "#fee2e2", "#f8fafc", "#dbeafe", "#2c5282"];

// ── 连续色板(超标倍数/浓度渐变: 浅 → 深蓝) ──
export const SEQUENTIAL = ["#dee5ef", "#c6d3e2", "#81b7d9", "#3680ae", "#214e81"];

// ── 中性色(文本/边框/背景 — 蓝灰科技风加大中性灰比例) ──
export const NEUTRAL_TEXT = "#475569";       // 靛灰文字(原 #64748b, 提对比度)
export const NEUTRAL_TEXT_LIGHT = "#94a3b8";  // 浅靛灰(次要文字)
export const NEUTRAL_BORDER = "#e2e8f0";      // 冷调浅灰边(原 #d9e2ec)
export const NEUTRAL_BG = "#f1f5f9";          // 冷调中性灰底(原 #f8fafc, 科技感更深)

// ── 仪表盘等级色(从低到高, 用于 SSUI/重构可行性仪表盘 axisLine) ──
// 格式: [累计占比阈值, 颜色]
export const GAUGE_STOPS: [number, string][] = [
  [0.4, DANGER],   // <40 低/不可行
  [0.6, WARNING],  // 40~60 中
  [0.8, INFO],     // 60~80 中高
  [1, SUCCESS],    // >80 高/可行
];

// ── 污染类型语义色(裴总 P1-5a: 全系统统一; 三色拉开区分度, 不挤在暖色区) ──
// 首页饼图/地图点位、场地详情 Tag、场地列表标签全部引用本常量。
// Nature/Science 期刊级配色: 红(重金属) / 绿(有机) / 橙(复合) — 三色相隔大, 易区分。
export const POLLUTION_TYPE: Record<string, string> = {
  heavy_metal: "#D73027",  // Nature 深红
  organic: "#1B7837",      // Nature 深绿
  composite: "#E08214",    // Nature 琥珀橙
};

// 浅色变体 — Tag 背景、地图淡色标记、进度条浅底色
export const POLLUTION_TYPE_LIGHT: Record<string, string> = {
  heavy_metal: "#FCBBA1",  // 浅红
  organic: "#A6DBA0",      // 浅绿
  composite: "#FDB863",    // 浅橙
};

// 极浅底色 — 卡片背景、大面积区域
export const POLLUTION_TYPE_BG: Record<string, string> = {
  heavy_metal: "#FFF5F0",
  organic: "#F0F7F0",
  composite: "#FFF8F0",
};

export const POLLUTION_LABEL: Record<string, string> = {
  heavy_metal: "重金属", organic: "有机污染", composite: "复合污染",
};
