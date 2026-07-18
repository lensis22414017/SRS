/**
 * factorFormat — 因子名称标准化显示工具
 *
 * 后端 canonical code 用下划线连单位(如 Cd_mgkg), 前端展示时需转为规范化学写法:
 *   Cd_mgkg → Cd (mg/kg)
 *   As_mgkg → As (mg/kg)
 *   pH      → pH (保持, 后端已是大写)
 *   SoilpH  → pH
 *   镉       → 镉 (中文原名保持)
 *
 * 同步修复大小写: ph/Ph → pH
 */

/** canonical code → 规范化学写法 */
export function formatFactor(code: string | undefined | null): string {
  if (!code) return "—";

  let s = String(code).trim();

  // pH 特殊处理(各种变体统一为 pH)
  if (/^soil?p?h$/i.test(s) || /^p_?h$/i.test(s) || s.toLowerCase() === "ph") {
    return "pH";
  }

  // 中文原名直接返回(镉/砷/铅/有机质 等)
  if (/[\u4e00-\u9fff]/.test(s)) {
    return s;
  }

  // _mgkg / _uggkg 等下划线连单位 → 空格+括号规范写法
  // Cd_mgkg → Cd (mg/kg)
  // Cu_uggkg → Cu (μg/kg)
  s = s.replace(/_?mgkg$/i, " (mg/kg)")
       .replace(/_?uggkg$/i, " (μg/kg)")
       .replace(/_?ngg$/i, " (ng/g)")
       .replace(/_?mgkg_?dw$/i, " (mg/kg dw)");

  // 其他下划线分隔符 → 空格(如 Cation_Exchange → Cation Exchange)
  s = s.replace(/_/g, " ");

  return s.trim();
}

export default formatFactor;
