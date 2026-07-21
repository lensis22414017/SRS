/**
 * factorFormat — 因子名称标准化显示工具
 *
 * 后端 canonical code 用下划线连单位(如 Cd_mgkg), 前端展示时需转为规范化学写法:
 *   Cd_mgkg → 镉 (mg/kg)
 *   P_mgkg  → 有效磷 (mg/kg)
 *   OC_pct  → 有机碳 (%)
 */

/** canonical code → 规范中文显示名（含单位） */
const CANONICAL_DISPLAY: Record<string, string> = {
  // 重金属
  "Cd_mgkg": "镉 (mg/kg)", "Pb_mgkg": "铅 (mg/kg)", "As_mgkg": "砷 (mg/kg)",
  "Cr_mgkg": "铬 (mg/kg)", "Cr6_mgkg": "六价铬 (mg/kg)",
  "Hg_mgkg": "汞 (mg/kg)", "Cu_mgkg": "铜 (mg/kg)", "Zn_mgkg": "锌 (mg/kg)",
  "Ni_mgkg": "镍 (mg/kg)", "Co_mgkg": "钴 (mg/kg)", "V_mgkg": "钒 (mg/kg)",
  "Sb_mgkg": "锑 (mg/kg)", "Be_mgkg": "铍 (mg/kg)", "Ba_mgkg": "钡 (mg/kg)",
  "Mn_mgkg": "锰 (mg/kg)", "Fe_mgkg": "铁 (mg/kg)",
  "Mo_mgkg": "钼 (mg/kg)", "Tl_mgkg": "铊 (mg/kg)",
  // 理化
  "pH": "pH", "ph": "pH", "SoilpH": "pH",
  "OC_pct": "有机碳 (%)", "CEC_cmolkg": "阳离子交换量 (cmol/kg)",
  "SoilBD_gcm3": "容重 (g/cm³)", "EC_mScm": "电导率 (mS/cm)",
  "Sand_pct": "砂粒 (%)", "Silt_pct": "粉粒 (%)", "Clay_pct": "黏粒 (%)",
  "Elevation_m": "海拔 (m)", "MAP_mm": "年均降水 (mm)", "Slope_pct": "坡度 (°)",
  // 养分
  "TN_gkg": "全氮 (g/kg)", "Total_P_gkg": "全磷 (g/kg)", "Total_K_gkg": "全钾 (g/kg)",
  "P_mgkg": "有效磷 (mg/kg)", "K_mgkg": "速效钾 (mg/kg)",
  "Hydrolyzable_N_mgkg": "碱解氮 (mg/kg)",
  // 有机汇总
  "PAHs_total(族群)": "多环芳烃 (ng/g)", "BaP_ngg": "苯并[a]芘 (ng/g)",
  "SumOCP_ngg": "有机氯农药 (ng/g)", "SumDDTs_ngg": "滴滴涕 (ng/g)",
  "SumPCB_ngg": "多氯联苯 (ng/g)", "SumHCHs_ngg": "六六六 (ng/g)",
  "SumPAE_ugkg": "邻苯二甲酸酯 (μg/kg)", "SumPBDE_ngg": "多溴联苯醚 (ng/g)",
  "SumPFAS_ngg": "全氟化合物 (ng/g)", "TPH_ngg": "石油烃 (ng/g)",
  "HMWPAH_ngg": "高分子量PAHs (ng/g)", "LMWPAH_ngg": "低分子量PAHs (ng/g)",
};

export function formatFactor(code: string | undefined | null): string {
  if (!code) return "—";

  let s = String(code).trim();

  // 查映射表（优先）
  if (CANONICAL_DISPLAY[s]) return CANONICAL_DISPLAY[s];

  // pH 特殊处理
  if (/^soil?p?h$/i.test(s) || /^p_?h$/i.test(s) || s.toLowerCase() === "ph") {
    return "pH";
  }

  // 中文原名直接返回
  if (/[\u4e00-\u9fff]/.test(s)) {
    return s;
  }

  // _mgkg → (mg/kg) 兜底
  s = s.replace(/_?mgkg$/i, " (mg/kg)")
       .replace(/_?uggkg$/i, " (μg/kg)")
       .replace(/_?ngg$/i, " (ng/g)")
       .replace(/_?mgkg_?dw$/i, " (mg/kg dw)");

  s = s.replace(/_/g, " ");

  return s.trim();
}

export default formatFactor;
