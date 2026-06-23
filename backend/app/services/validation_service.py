"""数据校验: 必填/类型/缺失/合理性/污染物阈值越界(pH 感知)。

校验层不依赖 DB。污染物阈值通过 threshold_resolver 解析知识库
threshold_original 文本(按 pH 分段)得到, 结合每个采样点的实测 pH 判定。
生成结构化校验报告。
"""
from __future__ import annotations

from app.services.import_service import ParsedSite
from app.services.threshold_resolver import resolve_limit

SEVERITY_ERROR = "error"
SEVERITY_WARN = "warning"

PH_RANGE = (0.0, 14.0)


def validate(parsed: ParsedSite, mapping: dict,
             pollutant_limits: dict | None = None,
             scope: str = "production", land_subtype: str = "其他用地") -> dict:
    issues: list[dict] = []
    req_point = mapping.get("required_point_fields", ["point_code"])
    req_factors = set(mapping.get("required_factors", []))

    n_points = len(parsed.points)
    n_measure = 0
    n_missing_value = 0
    seen_codes: set[str] = set()

    for p in parsed.points:
        for rf in req_point:
            if not getattr(p, rf, None):
                issues.append({"point_code": p.point_code, "factor": None,
                               "type": "missing_required_field", "field": rf,
                               "severity": SEVERITY_ERROR,
                               "message": f"采样点缺少必填字段 {rf}"})
        if p.point_code in seen_codes:
            issues.append({"point_code": p.point_code, "factor": None,
                           "type": "duplicate_point", "severity": SEVERITY_ERROR,
                           "message": f"采样点编号重复: {p.point_code}"})
        seen_codes.add(p.point_code)

        # 本点 pH(供污染物分段判定)
        ph_val = next((m.value for m in p.measurements
                       if m.factor_code == "pH" and m.value is not None), None)

        present = {m.factor_code for m in p.measurements if m.value is not None}
        for rf in req_factors - present:
            issues.append({"point_code": p.point_code, "factor": rf,
                           "type": "missing_required_factor", "severity": SEVERITY_ERROR,
                           "message": f"缺少必测因子 {rf} 的有效值"})

        for m in p.measurements:
            n_measure += 1
            if m.value is None:
                n_missing_value += 1
                issues.append({"point_code": p.point_code, "factor": m.factor_code,
                               "type": "missing_value", "severity": SEVERITY_WARN,
                               "message": f"{m.factor_code} 值缺失"})
                continue
            if m.value < 0:
                issues.append({"point_code": p.point_code, "factor": m.factor_code,
                               "type": "negative_value", "severity": SEVERITY_ERROR,
                               "value": m.value, "message": f"{m.factor_code} 出现负值 {m.value}"})
            if m.factor_code == "pH" and not (PH_RANGE[0] <= m.value <= PH_RANGE[1]):
                issues.append({"point_code": p.point_code, "factor": "pH",
                               "type": "out_of_physical_range", "severity": SEVERITY_ERROR,
                               "value": m.value, "message": f"pH={m.value} 超出物理范围"})
            # 污染物阈值越界(pH 感知, 仅提示)
            if pollutant_limits and m.factor_type == "pollutant":
                seg = resolve_limit(pollutant_limits, m.factor_code, ph_val,
                                    scope=scope, land_subtype=land_subtype)
                if seg and seg.get("limit") is not None and m.value > seg["limit"]:
                    issues.append({
                        "point_code": p.point_code, "factor": m.factor_code,
                        "type": "threshold_exceed", "severity": SEVERITY_WARN,
                        "value": m.value, "limit": seg["limit"], "ph": ph_val,
                        "source": seg.get("source"), "segment": seg.get("raw"),
                        "message": (f"{m.factor_code}={m.value}mg/kg 超过限值 "
                                    f"{seg['limit']}mg/kg (pH={ph_val}, {seg.get('source')})")})

    errors = [i for i in issues if i["severity"] == SEVERITY_ERROR]
    warnings = [i for i in issues if i["severity"] == SEVERITY_WARN]
    exceed = [i for i in issues if i["type"] == "threshold_exceed"]
    return {
        "source_file": parsed.source_file,
        "n_points": n_points,
        "n_measurements": n_measure,
        "n_missing_value": n_missing_value,
        "n_errors": len(errors),
        "n_warnings": len(warnings),
        "n_exceed": len(exceed),
        "passed": len(errors) == 0,
        "n_issues_total": len(issues),  # 全量计数(可追溯)
        # 仅存前 200 条样本, 避免大数据(如全国合并集 873万measurements) issues JSON 爆炸;
        # 完整统计在 summary.by_type(全量计数) + exceed_factors(去重因子集合)。
        "issues": issues[:200],
        "issues_truncated": len(issues) > 200,
        "summary": {
            "by_type": _count_by(issues, "type"),
            "exceed_factors": sorted({i["factor"] for i in exceed if i.get("factor")}),
        },
    }


def _count_by(issues: list[dict], key: str) -> dict:
    out: dict[str, int] = {}
    for i in issues:
        out[i[key]] = out.get(i[key], 0) + 1
    return out
