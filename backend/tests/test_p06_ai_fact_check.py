"""P0-6 AI 润色事实校验测试。

10 个绕过测试（GPT 明确要求覆盖的表达变体）。
"""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.diagnosis_fact_check import (
    validate_ai_polish, check_overall_conclusion, check_fact_consistency, extract_facts,
)


# 原始诊断文本模板（含超标事实 + KOS 排名 + 浓度数值）
ORIGINAL = (
    "场地诊断结果: 砷超标，最大浓度 12420 mg/kg，超标 310 倍。"
    "铜超标，浓度 1279 mg/kg。铅超标，浓度 500 mg/kg。"
    "KOS 排名: #1 砷, #2 铅, #3 铜。"
    "该场地存在明确的土壤重金属污染障碍。"
)


class TestP06AIFactCheck:
    """P0-6: AI 事实校验 — 10 个绕过测试"""

    def test_01_overall_controllable(self):
        """绕过: '虽然超标，但总体可控'"""
        ai_reply = "该场地砷、铜、铅超标。虽然超标，但总体可控，采取一般措施即可。"
        v = validate_ai_polish(ORIGINAL, ai_reply)
        assert not v["passed"], "'总体可控' 应被拦截"
        assert "总体可控" in v["forbidden_hits"]

    def test_02_normal_use(self):
        """绕过: '采取一般措施即可正常使用'"""
        ai_reply = "场地砷铜铅超标。采取一般措施即可正常使用。"
        v = validate_ai_polish(ORIGINAL, ai_reply)
        assert not v["passed"]
        assert "可正常使用" in v["forbidden_hits"]

    def test_03_limited_impact(self):
        """绕过: '影响有限，无需优先修复'"""
        ai_reply = "砷铜铅超标。影响有限，无需优先修复。"
        v = validate_ai_polish(ORIGINAL, ai_reply)
        assert not v["passed"]
        assert "影响有限" in v["forbidden_hits"]

    def test_04_no_remediation_needed(self):
        """绕过: '无需修复'"""
        ai_reply = "场地砷超标。无需修复。"
        v = validate_ai_polish(ORIGINAL, ai_reply)
        assert not v["passed"]

    def test_05_safe_overall(self):
        """绕过: '整体状况十分安全'"""
        ai_reply = "虽然砷超标，但整体状况十分安全，土壤风险很低。"
        v = validate_ai_polish(ORIGINAL, ai_reply)
        assert not v["passed"]

    def test_06_modified_value(self):
        """篡改: 修改浓度数值"""
        ai_reply = "砷超标，最大浓度 100 mg/kg。铜铅也超标。存在污染障碍。"
        v = validate_ai_polish(ORIGINAL, ai_reply)
        # 原始 12420 → AI 写 100，数值被篡改
        assert not v["passed"]
        assert any("篡改" in i or "缺失" in i for i in v["fact_issues"])

    def test_07_deleted_primary_factor(self):
        """篡改: 删除首要障碍因子（砷）"""
        ai_reply = "场地铜铅超标。存在污染障碍。需关注铜和铅。"
        v = validate_ai_polish(ORIGINAL, ai_reply)
        # 砷（首要因子）在 AI 输出中丢失
        assert not v["passed"]
        assert any("砷" in i for i in v["fact_issues"])

    def test_08_reversed_exceedance(self):
        """篡改: 超标关系反转"""
        ai_reply = "砷铜铅均未超标。各项指标均在标准范围内。"
        v = validate_ai_polish(ORIGINAL, ai_reply)
        assert not v["passed"]
        assert any("反转" in i for i in v["fact_issues"])

    def test_09_acceptable_range(self):
        """绕过: '可接受范围'"""
        ai_reply = "砷铜铅超标，但在可接受范围内。"
        v = validate_ai_polish(ORIGINAL, ai_reply)
        assert not v["passed"]
        assert "可接受范围" in v["forbidden_hits"]

    def test_10_honest_pass(self):
        """正常通过: 如实复述超标事实，不加整体结论"""
        ai_reply = (
            "该场地检测到砷超标，最大浓度 12420 mg/kg，超标约 310 倍，"
            "是首要障碍因子。铜超标 1279 mg/kg，铅超标 500 mg/kg。"
            "建议优先关注砷的管控与修复。"
        )
        v = validate_ai_polish(ORIGINAL, ai_reply)
        assert v["passed"], f"如实复述应通过校验，问题: {v['forbidden_hits']} {v['fact_issues']}"

    def test_extract_facts_basic(self):
        """事实提取: 因子/超标/排名"""
        facts = extract_facts(ORIGINAL)
        assert facts["has_exceedance"] is True
        assert facts["has_obstacle"] is True
        factor_names = [f["name"] for f in facts["factors"]]
        assert "砷" in factor_names
        assert "铜" in factor_names
