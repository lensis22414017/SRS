"""QA/QC 质量控制服务 — 平行样相对偏差 + 加标回收率(竞品完善 H1, 2026-06-24)。

环境监测数据可信度评估(竞品功能, 支撑监管决策"检测数据是否可信"):
- 平行样精密度: RPD(相对百分偏差) ≤20% 合格(无机) / ≤30% 合格(有机痕量)
- 加标回收准确度: 无机 80-120% / 有机 70-120% 合格

参考: HJ/T 91-2002 地表水和污水监测技术规范; HJ 166-2004 土壤环境监测技术规范。
"""
from __future__ import annotations


def relative_percent_difference(a: float, b: float) -> float:
    """相对百分偏差 RPD(%)。平行样精密度的核心指标, 越小越精密。"""
    s = a + b
    if s == 0:
        return 0.0
    return round(abs(a - b) / (s / 2.0) * 100.0, 2)


def spike_recovery(original: float, spiked_amount: float, total_measured: float) -> float:
    """加标回收率(%)。准确度指标。
    original=本底浓度, spiked_amount=加标量, total_measured=加标后实测总浓度。
    """
    if spiked_amount == 0:
        return 0.0
    return round((total_measured - original) / spiked_amount * 100.0, 2)


def qc_pass_rpd(rpd: float, matrix: str = "无机") -> bool:
    """RPD 合格判定。无机≤20%, 有机痕量≤30%。"""
    lim = 30.0 if matrix in ("有机", "organic") else 20.0
    return rpd <= lim


def qc_pass_recovery(rec: float, matrix: str = "无机") -> bool:
    """回收率合格判定。无机 80-120%, 有机 70-120%。"""
    if matrix in ("有机", "organic"):
        return 70.0 <= rec <= 120.0
    return 80.0 <= rec <= 120.0


def qc_assess(a: float, b: float, original: float, spiked_amount: float,
              total_measured: float, matrix: str = "无机") -> dict:
    """一站式 QC 评估: 平行样RPD + 加标回收率 + 合格判定。"""
    rpd = relative_percent_difference(a, b)
    rec = spike_recovery(original, spiked_amount, total_measured)
    return {
        "rpd": rpd, "rpd_pass": qc_pass_rpd(rpd, matrix),
        "recovery": rec, "recovery_pass": qc_pass_recovery(rec, matrix),
        "matrix": matrix,
        "overall_pass": qc_pass_rpd(rpd, matrix) and qc_pass_recovery(rec, matrix),
    }


if __name__ == "__main__":
    print("=== QA/QC 自测 ===")
    rpd = relative_percent_difference(10.2, 9.8)
    print(f"平行样RPD(10.2,9.8)={rpd}% 无机合格={qc_pass_rpd(rpd)} 有机合格={qc_pass_rpd(rpd,'有机')}")
    rec = spike_recovery(10, 10, 19.5)
    print(f"加标回收(本底10/加标10/实测19.5)={rec}% 合格={qc_pass_recovery(rec)}")
    print("一站式:", qc_assess(10.2, 9.8, 10, 10, 19.5, "无机"))
