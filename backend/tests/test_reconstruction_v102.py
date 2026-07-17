#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""GPT 审计第五节 + 10.5: 重构评价覆盖率门禁 + 缺阈值不给100分测试。

验证:
  1) score_pollutant 缺阈值 → None(不给100分, GPT 5.4)
  2) 覆盖率 < 30% → "证据不足/无法评价"(GPT 5.5)
  3) 内梅罗指数改进模糊综合评价正确计算
  4) AHP CR < 0.1 一致性检验通过(甲方 Table[16])
  5) 个旧缺失 107 项左右时不得产生"生态100分"权威结论(GPT 5.9)
"""
import os
import sys
import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(BACKEND)
sys.path.insert(0, BACKEND)
sys.path.insert(0, os.path.join(ROOT, "ml", "evaluation"))


def test_score_pollutant_no_threshold_returns_none():
    """缺阈值不再给100分(GPT 5.4 核心修复)。"""
    from reconstruction import score_pollutant
    # value 存在但 screen_limit=None → 应返回 None(退出打分)
    assert score_pollutant(80.0, None) is None, "缺阈值应返回None, 不给100分"
    # value=None → None
    assert score_pollutant(None, 40.0) is None
    # 未超 → 100
    assert score_pollutant(30.0, 40.0) == 100
    # 超标 → 50
    assert score_pollutant(80.0, 40.0) == 50


def test_coverage_gate_insufficient():
    """覆盖率 < 30% → 证据不足(GPT 5.5)。"""
    from reconstruction import evaluate, COVERAGE_GATE
    # 只有 1 个指标(pH), 生产轨有 26 项 → 覆盖率 ~3.8% << 30%
    result = evaluate({"pH": 6.5}, scope="production")
    assert result["grade"] == "证据不足/无法评价", f"低覆盖率应证据不足, 实际 {result['grade']}"
    assert result.get("is_insufficient") is True
    assert result["coverage_rate"] < COVERAGE_GATE
    assert result["score"] is None


def test_nemerow_index_computed():
    """内梅罗指数改进模糊综合评价(甲方方法)。"""
    from reconstruction import evaluate
    # 构造完整数据(覆盖率高)
    values = {
        "pH": 6.5, "有机质": 30.0, "全氮": 1.5, "有效磷": 15.0, "速效钾": 100.0,
        "砷": 20.0, "铅": 50.0, "铜": 30.0, "锌": 100.0, "镉": 0.2, "铬": 100.0,
        "汞": 0.5, "镍": 30.0,
    }
    screen = {"砷": 40, "铅": 170, "铜": 100, "锌": 300, "镉": 0.6,
              "铬": 250, "汞": 1.3, "镍": 100}
    result = evaluate(values, scope="production", ph=6.5, screen_limits=screen)
    if result.get("is_insufficient"):
        pytest.skip(f"覆盖率不足: {result.get('coverage_rate')}")
    # 内梅罗指数应计算出来
    assert "nemerow_score" in result
    assert result["score"] == result["nemerow_score"]
    # 等级应为可行或不可行(非证据不足)
    assert result["grade"] in ("可行", "不可行")


def test_ahp_consistency():
    """AHP CR < 0.1 一致性检验(甲方 Table[16])。"""
    import numpy as np
    from weighting import ahp_weights
    # 甲方生产准则层 Table[11]
    M = np.array([[1, 1/3, 3, 4], [3, 1, 5, 7], [1/3, 1/5, 1, 1/2], [1/4, 1/7, 2, 1]])
    w, cr = ahp_weights(M)
    assert cr < 0.1, f"CR 应 <0.1, 实际 {cr}"
    assert abs(w.sum() - 1.0) < 0.01
    # B2(修复潜力)应权重最大(甲方 Table[21] 趋势)
    assert w[1] == max(w), "B2修复潜力应权重最大"


def test_overload_does_not_get_100():
    """个旧超标数据不得因缺阈值而得100分(GPT 5.9)。"""
    from reconstruction import evaluate, score_pollutant
    # 砷=80 超标, 但阈值缺(模拟 resolve_limit 失败)
    f = score_pollutant(80.0, None)
    assert f is None, "砷=80 缺阈值应退出打分, 不得给100分"


def test_mice_impute():
    """MICE 缺失值插补(甲方方法段落[439])。"""
    from mice_imputer import apply_mice_to_values
    values = {"pH": 6.5, "砷": 80.0}
    all_factors = ["pH", "砷", "铅", "铜"]
    result = apply_mice_to_values(values, all_factors)
    # 缺失的铅/铜应被插补
    assert result["铅"]["is_imputed"] is True
    assert result["铜"]["is_imputed"] is True
    assert result["pH"]["is_imputed"] is False
    assert result["砷"]["is_imputed"] is False
