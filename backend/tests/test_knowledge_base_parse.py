"""知识库 ETL 解析测试 (仅依赖 pandas, 不需 DB)。"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CSV = os.path.join(ROOT, "data", "knowledge_base", "统一障碍因子知识库_V1.0.csv")


def _parse():
    import sys
    sys.path.insert(0, os.path.join(ROOT, "ml", "etl"))
    from load_knowledge_base import parse_knowledge_base
    return parse_knowledge_base(CSV)


def test_factor_and_rule_counts():
    factors, rules = _parse()
    assert len(factors) == 122, f"因子数应为122, 实际{len(factors)}"
    assert len(rules) == 403, f"规则数应为403, 实际{len(rules)}"


def test_factor_type_mapping():
    factors, _ = _parse()
    types = {f["factor_type"] for f in factors}
    assert "pollutant" in types and "chemical" in types and "fertility" in types
