"""P0-6 AI 润色事实校验测试 + M0-7 强化(因子-数值-单位-排名绑定)。

10 个原有绕过/篡改测试 + 5 个 M0-7 新增的因子级绑定测试。
"""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.diagnosis_fact_check import (
    validate_ai_polish, check_overall_conclusion, check_fact_consistency, extract_facts,
)


# 原始诊断文本模板（含超标事实 + KOS 排名 + 浓度数值 + 单位 + 阈值）
ORIGINAL = (
    "场地诊断结果: 砷超标，最大浓度 12420 mg/kg，超标 310 倍。"
    "铜超标，浓度 1279 mg/kg。铅超标，浓度 500 mg/kg。"
    "KOS 排名: #1 砷, #2 铅, #3 铜。"
    "该场地存在明确的土壤重金属污染障碍。"
)


class TestP06AIFactCheck:
    """P0-6: AI 事实校验 — 10 个绕过/篡改测试"""

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
        """事实提取: 因子/超标/排名(M0-7 新结构 factor/value/unit/threshold/exceeded/rank)"""
        facts = extract_facts(ORIGINAL)
        assert facts["has_exceedance"] is True
        assert facts["has_obstacle"] is True
        factor_names = [f["factor"] for f in facts["factors"]]
        assert "砷" in factor_names
        assert "铜" in factor_names
        assert "铅" in factor_names
        # 每因子结构应包含 M0-7 字段
        as_factor = next(f for f in facts["factors"] if f["factor"] == "砷")
        assert as_factor["value"] == 12420
        assert as_factor["unit"] == "mg/kg"
        assert as_factor["exceeded"] is True
        assert as_factor["rank"] == 1


class TestM07FactorLevelBinding:
    """M0-7 强化: 因子-数值-单位-排名-阈值绑定 5 个测试"""

    def test_m07_01_value_swap_between_factors(self):
        """M0-7 测试1: As/Pb 数值互换(把砷的 12420 套到铅上)"""
        ai_reply = (
            "该场地砷超标，浓度 500 mg/kg（原为铅的值），"
            "铅超标，浓度 12420 mg/kg（原为砷的值，数值交换）。"
            "铜超标，浓度 1279 mg/kg。"
            "KOS 排名: #1 砷, #2 铅, #3 铜。"
        )
        v = validate_ai_polish(ORIGINAL, ai_reply)
        assert not v["passed"], "因子间数值互换必须被拦截"
        assert any("数值交换" in i for i in v["fact_issues"]), \
            f"应检出'数值交换'告警, 实际: {v['fact_issues']}"

    def test_m07_02_unit_change(self):
        """M0-7 测试2: 单位 mg/kg 改成 μg/kg"""
        ai_reply = (
            "该场地砷超标，最大浓度 12420 μg/kg（单位被篡改为 μg/kg）。"
            "铜超标，浓度 1279 mg/kg。铅超标，浓度 500 mg/kg。"
            "KOS 排名: #1 砷, #2 铅, #3 铜。"
        )
        v = validate_ai_polish(ORIGINAL, ai_reply)
        assert not v["passed"], "单位变更必须被拦截"
        assert any("单位篡改" in i for i in v["fact_issues"]), \
            f"应检出'单位篡改'告警, 实际: {v['fact_issues']}"

    def test_m07_03_rank_swap(self):
        """M0-7 测试3: 第一名(砷)与第二名(铅)互换"""
        ai_reply = (
            "该场地砷超标，最大浓度 12420 mg/kg。"
            "铜超标，浓度 1279 mg/kg。铅超标，浓度 500 mg/kg。"
            "KOS 排名: #1 铅, #2 砷, #3 铜。"
        )
        v = validate_ai_polish(ORIGINAL, ai_reply)
        assert not v["passed"], "排名顺序变更必须被拦截"
        assert any("排名篡改" in i for i in v["fact_issues"]), \
            f"应检出'排名篡改'告警, 实际: {v['fact_issues']}"

    def test_m07_04_threshold_as_measurement(self):
        """M0-7 测试4: 阈值冒充实测值（如把筛选值 60 当作砷的实测浓度）"""
        original_with_threshold = (
            "场地诊断结果: 砷超标，最大浓度 12420 mg/kg，阈值 60 mg/kg，超标 310 倍。"
            "铜超标，浓度 1279 mg/kg。铅超标，浓度 500 mg/kg。"
            "KOS 排名: #1 砷, #2 铅, #3 铜。"
        )
        # AI 把阈值 60 当成砷的实测值
        ai_reply = (
            "砷实测浓度 60 mg/kg（阈值冒充实测值）。"
            "铜超标，浓度 1279 mg/kg。铅超标，浓度 500 mg/kg。"
            "KOS 排名: #1 砷, #2 铅, #3 铜。"
        )
        v = validate_ai_polish(original_with_threshold, ai_reply)
        assert not v["passed"], "阈值/实测值互换必须被拦截"
        # 应能检出: 原始 12420 缺失/被改 或 阈值被标为实测值
        assert any(
            "篡改" in i or "缺失" in i or "互换" in i for i in v["fact_issues"]
        ), f"应检出阈值/实测值互换, 实际: {v['fact_issues']}"

    def test_m07_05_deleted_formal_obstacle(self):
        """M0-7 测试5: 删除某个正式障碍因子（如删除铜）"""
        ai_reply = (
            "该场地砷超标，最大浓度 12420 mg/kg。"
            "铅超标，浓度 500 mg/kg。"
            "KOS 排名: #1 砷, #2 铅。"
        )
        v = validate_ai_polish(ORIGINAL, ai_reply)
        assert not v["passed"], "删除正式障碍因子必须被拦截"
        # 铜是原始的正式障碍(超标且参与排名), 必须保留
        assert any("铜" in i for i in v["fact_issues"]), \
            f"应检出'铜'因子丢失, 实际: {v['fact_issues']}"
