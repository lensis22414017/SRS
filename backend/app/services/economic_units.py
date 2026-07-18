"""R3 审计第五类: 经济数据单位换算工具。

集中实现所有单位换算(1亩 = 1/15公顷), 供经济数据导入和校验使用。
"""
from __future__ import annotations

MU_PER_HECTARE = 15.0  # 1 公顷 = 15 亩


def mu_to_hectare(value: float) -> float:
    """亩 → 公顷。"""
    return value / MU_PER_HECTARE


def hectare_to_mu(value: float) -> float:
    """公顷 → 亩。"""
    return value * MU_PER_HECTARE


def yuan_per_mu_to_yuan_per_hectare(value: float) -> float:
    """元/亩 → 元/公顷。"""
    return value * MU_PER_HECTARE


def yuan_per_hectare_to_yuan_per_mu(value: float) -> float:
    """元/公顷 → 元/亩。"""
    return value / MU_PER_HECTARE


def kg_per_mu_to_kg_per_hectare(value: float) -> float:
    """kg/亩 → kg/公顷。"""
    return value * MU_PER_HECTARE


def kg_per_hectare_to_kg_per_mu(value: float) -> float:
    """kg/公顷 → kg/亩。"""
    return value / MU_PER_HECTARE


def standardize_unit(value: float, from_unit: str, to_unit: str) -> float:
    """通用单位标准化: 把 value 从 from_unit 换算到 to_unit。

    支持的组合:
      亩 ↔ 公顷 (面积)
      元/亩 ↔ 元/公顷 (单位面积成本)
      kg/亩 ↔ kg/公顷 (单位面积产量)
    """
    from_unit = (from_unit or "").strip().lower()
    to_unit = (to_unit or "").strip().lower()
    if from_unit == to_unit:
        return value

    # 面积: 亩 ↔ 公顷
    if from_unit in ("亩", "mu") and to_unit in ("公顷", "ha", "hectare"):
        return mu_to_hectare(value)
    if from_unit in ("公顷", "ha", "hectare") and to_unit in ("亩", "mu"):
        return hectare_to_mu(value)

    # 成本: 元/亩 ↔ 元/公顷
    if from_unit in ("元/亩", "元每亩") and to_unit in ("元/公顷", "元每公顷"):
        return yuan_per_mu_to_yuan_per_hectare(value)
    if from_unit in ("元/公顷", "元每公顷") and to_unit in ("元/亩", "元每亩"):
        return yuan_per_hectare_to_yuan_per_mu(value)

    # 产量: kg/亩 ↔ kg/公顷
    if from_unit in ("kg/亩", "公斤/亩") and to_unit in ("kg/公顷", "公斤/公顷"):
        return kg_per_mu_to_kg_per_hectare(value)
    if from_unit in ("kg/公顷", "公斤/公顷") and to_unit in ("kg/亩", "公斤/亩"):
        return kg_per_hectare_to_kg_per_mu(value)

    # 无法识别的换算
    raise ValueError(f"不支持的单位换算: {from_unit} → {to_unit}")


# D18-D25 标准单位定义(R3 审计口径)
INDICATOR_DEFINITIONS = {
    "D18": {"name": "劳动力成本", "unit": "元/亩", "direction": "negative",
            "description": "劳动力成本, 元/亩·年"},
    "D19": {"name": "机械化成本", "unit": "元/亩", "direction": "negative",
            "description": "机械作业及服务成本, 元/亩·年"},
    "D20": {"name": "土地成本", "unit": "元/亩", "direction": "negative",
            "description": "土地租金或折算土地成本, 元/亩·年"},
    "D21": {"name": "非机械化成本", "unit": "元/亩", "direction": "negative",
            "description": "种子、肥料、农药等非机械化物质投入, 元/亩·年"},
    "D22": {"name": "单位面积总产值", "unit": "元/公顷", "direction": "positive",
            "description": "单位面积总产值, 元/公顷·年"},
    "D23": {"name": "效益费用比", "unit": "无量纲", "direction": "positive",
            "description": "总产值÷总成本, 无量纲"},
    "D24": {"name": "人均可支配收入", "unit": "元/人", "direction": "positive",
            "description": "对应用途和地域的人均可支配收入, 元/人·年"},
    "D25": {"name": "单位面积实物产量", "unit": "kg/公顷", "direction": "positive",
            "description": "单位面积实物产量, kg/公顷·年"},
}
