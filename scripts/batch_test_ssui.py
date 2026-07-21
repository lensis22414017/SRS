"""批量测试所有场地的 SSUI 评价能力，输出门禁命中矩阵。"""
from __future__ import annotations

import csv
import os
import sys

# 确保项目根在路径中
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(ROOT, "backend")
ML_EVAL = os.path.join(ROOT, "ml", "evaluation")

# 确保导入路径
for p in [BACKEND, ROOT, ML_EVAL]:
    if p not in sys.path:
        sys.path.insert(0, p)

# 切换到 backend 目录（SQLAlchemy models 需要）
os.chdir(BACKEND)

from datetime import datetime


def run_batch():
    # 延迟导入，避免循环依赖
    from ml.evaluation.ssui import evaluate, D_TO_FACTORS
    from ml.evaluation.safety_reference_loader import load_safety_reference
    from ml.evaluation.reference_loader import load_economic_reference

    # 加载参照数据
    safety_refs = load_safety_reference()
    safety_ranges = safety_refs["ranges"]
    econ_ref = load_economic_reference()

    # 用 SQLAlchemy 直接查数据库
    from app.db.session import SessionLocal
    from app.models import Site, Measurement, FactorDictionary

    db = SessionLocal()

    try:
        sites = db.query(Site).all()
        print(f"共 {len(sites)} 个场地")
        print()

        results = []
        header = [
            "site_name", "site_code", "scope",
            "C1_measured", "C1_coverage_pct",
            "C2_measured", "C2_has_D16", "C2_has_D17",
            "econ_measured",
            "full_25", "c1_partial_ok",
            "ssui", "grade", "is_blocked", "is_reference",
            "c1_available_d_codes", "c1_missing_d_codes",
            "c2_factors_found", "explanation_short",
        ]
        results.append(header)

        for site in sites:
            # 获取场地实测因子
            measurements = (
                db.query(Measurement, FactorDictionary)
                .join(FactorDictionary, Measurement.factor_id == FactorDictionary.id)
                .filter(Measurement.site_id == site.id)
                .all()
            )

            # 构建 series dict
            series: dict[str, list] = {}
            factor_names = set()
            for meas, fd in measurements:
                name = fd.factor_name or fd.factor_code
                factor_names.add(name)
                if name not in series:
                    series[name] = []
                if meas.value is not None:
                    try:
                        series[name].append(float(meas.value))
                    except (ValueError, TypeError):
                        pass

            # 构建安全阈值（从 series 中找重金属和有机物）
            from app.services.threshold_resolver import resolve_threshold_from_db

            _HM_CANON_MAP = {
                "砷": "As_mgkg", "铅": "Pb_mgkg", "镉": "Cd_mgkg", "铬": "Cr_mgkg",
                "汞": "Hg_mgkg", "铜": "Cu_mgkg", "锌": "Zn_mgkg", "镍": "Ni_mgkg",
            }
            heavy_factors = []
            organic_factors = []
            for fn in factor_names:
                if fn in _HM_CANON_MAP:
                    heavy_factors.append(fn)
                elif fn not in {"pH", "有机质", "全氮", "全磷", "全钾", "速效钾", "速效磷",
                                "碱解氮", "电导率", "阳离子交换量", "CEC", "砂粒", "粉粒",
                                "黏粒", "容重", "含水率", "海拔", "采样深度"}:
                    organic_factors.append(fn)

            safety_thresholds = {}
            threshold_resolution_status = {}
            for fc in heavy_factors:
                canon = _HM_CANON_MAP.get(fc)
                if canon:
                    resolved = resolve_threshold_from_db(db, canon, track="prod")
                    if resolved.get("threshold_value") is not None:
                        safety_thresholds[fc] = {
                            "limit": float(resolved["threshold_value"]),
                            "type": "upper",
                            "standard": resolved.get("threshold_standard", ""),
                            "version": resolved.get("threshold_version", ""),
                            "resolution_status": resolved.get("threshold_resolution_status", "resolved"),
                        }
                    threshold_resolution_status[fc] = resolved.get(
                        "threshold_resolution_status", "not_found")
            for fc in organic_factors:
                resolved = resolve_threshold_from_db(db, fc, track="prod")
                if resolved.get("threshold_value") is not None:
                    safety_thresholds[fc] = {
                        "limit": float(resolved["threshold_value"]),
                        "type": "upper",
                        "standard": resolved.get("threshold_standard", ""),
                        "version": resolved.get("threshold_version", ""),
                        "resolution_status": resolved.get("threshold_resolution_status", "resolved"),
                    }
                threshold_resolution_status[fc] = resolved.get(
                    "threshold_resolution_status", "not_found")

            # 注：demo_sites 默认无经济数据，此处用空（测试 blocked 行为）
            # 如需测试完整 SSUI，可手动填充 economic_data
            economic_data = {}

            # 运行 SSUI
            for scope in ("production", "ecology"):
                try:
                    result = evaluate(
                        series, scope=scope, t=2.0, intensity="medium",
                        economic_data=economic_data, allow_proxy=False,
                        safety_thresholds=safety_thresholds,
                        threshold_resolution_status=threshold_resolution_status,
                        safety_reference_ranges=safety_ranges,
                        economic_reference_data=econ_ref,
                        pollutant_groups={
                            "heavy_metals": heavy_factors,
                            "organics": organic_factors,
                        },
                    )
                except Exception as e:
                    result = {
                        "is_blocked": True, "ssui": None,
                        "grade": f"error:{str(e)[:40]}",
                        "explanation": str(e)[:100],
                        "c1_coverage_ratio": 0, "c1_normalization_missing": [],
                        "coverage": {}, "is_reference": False,
                    }

                cov = result.get("coverage") or {}
                c1_measured = cov.get("C1", 0)
                c2_measured = cov.get("C2", 0)
                c1_ratio = result.get("c1_coverage_ratio", 0)
                full_25 = cov.get("complete_25", False)

                # 收集 C1 可用的 D 码
                from ml.evaluation.ssui import D_TO_FACTORS
                c1_available = []
                c1_missing = []
                for d_code in sorted(D_TO_FACTORS):
                    if d_code.startswith(("D16_", "D17_", "D18_", "D19_", "D20_",
                                          "D21_", "D22_", "D23_", "D24_", "D25_")):
                        continue
                    aliases = D_TO_FACTORS[d_code]
                    has_any = any(a in series and series[a] for a in aliases)
                    if has_any:
                        c1_available.append(d_code)
                    else:
                        c1_missing.append(d_code)

                c2_factors = heavy_factors + organic_factors

                row = [
                    site.name or site.site_code,
                    site.site_code or "",
                    scope,
                    c1_measured,
                    f"{c1_ratio * 100:.0f}%",
                    c2_measured,
                    "Y" if heavy_factors else "N",
                    "Y" if organic_factors else "N",
                    cov.get("economic_measured", 0),
                    "Y" if full_25 else "N",
                    "Y" if (c1_measured >= 10 and c2_measured >= 2
                             and cov.get("economic_complete", False)) else "N",
                    result.get("ssui"),
                    result.get("grade", "N/A"),
                    "Y" if result.get("is_blocked") else "N",
                    "Y" if result.get("is_reference") else "N",
                    ", ".join(c1_available[:5]) + ("..." if len(c1_available) > 5 else ""),
                    ", ".join(c1_missing[:5]) + ("..." if len(c1_missing) > 5 else ""),
                    ", ".join(c2_factors[:5]) + ("..." if len(c2_factors) > 5 else ""),
                    (result.get("explanation") or "")[:80],
                ]
                results.append(row)
                print(f"  [{scope:>10}] {site.name or site.site_code}: "
                      f"C1={c1_measured}/15 C2={c2_measured}/2 Econ={cov.get('economic_measured', 0)}/8 "
                      f"→ {'FULL' if full_25 else 'PARTIAL' if c1_measured >= 10 else 'BLOCKED'} "
                      f"| 可用D码: {c1_available}")

        # 写出 CSV
        out_path = os.path.join(ROOT, "data", "standards", "ssui_batch_test_results.csv")
        with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            for row in results:
                writer.writerow(row)
        print(f"\n结果已写入: {out_path}")

    finally:
        db.close()


if __name__ == "__main__":
    run_batch()
