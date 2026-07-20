#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""GPT 审计第六节: SSUI 25 项完整重写测试。

验证:
  1) 25 项指标结构(D1-D25)已落地
  2) 风险/经济数据缺失 → SSUI=N/A(GPT 6.4)
  3) 不再用 C1 MVP 单维度虚假正式等级(GPT 6.1)
  4) 等级边界(甲方 Table[76])
"""
import os
import sys
import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(BACKEND)
sys.path.insert(0, BACKEND)
sys.path.insert(0, os.path.join(ROOT, "ml", "evaluation"))


def test_ssui_25_metrics_structure():
    """25 项元指标结构已落地(GPT 6.2)。"""
    import json
    import re
    params_path = os.path.join(ROOT, "ml", "params", "evaluation_params.json")
    with open(params_path, encoding="utf-8") as f:
        data = json.load(f)
    for scope in ("production", "ecology"):
        mw25 = data["ssui"][scope].get("meta_weights_25", {})
        assert len(mw25) == 25, f"{scope} 应有 25 项元指标, 实际 {len(mw25)}"
        # 检查 D1-D25 编号(自然排序)
        def _d_num(k):
            m = re.match(r"D(\d+)_", k)
            return int(m.group(1)) if m else 999
        d_codes = sorted(mw25.keys(), key=_d_num)
        for i, dc in enumerate(d_codes, 1):
            assert dc.startswith(f"D{i}_"), f"第{i}项应以 D{i}_ 开头, 实际 {dc}"


def test_ssui_na_when_missing_economic():
    """缺经济数据 → SSUI=blocked(R3 审计第五类, 不再叫 N/A)。"""
    from ssui import evaluate
    # 只有土壤数据(C1+C2), 无经济数据
    series = {
        "pH": [6.0, 6.5, 7.0],
        "有机质": [30, 40, 50],
        "砷": [10, 30, 50],
    }
    result = evaluate(
        series, scope="production", t=2.0, intensity="medium",
        safety_thresholds={"砷": {"limit": 30.0, "resolution_status": "resolved"}},
        threshold_resolution_status={"砷": "resolved"},
    )
    assert result.get("is_na") is True, "缺经济数据应 SSUI=blocked"
    assert result.get("is_blocked") is True, "缺经济数据应 blocked"
    assert result["ssui"] is None
    assert "经济" in str(result.get("missing_dimensions", []))


def test_ssui_no_c1_mvp_fake_grade():
    """不再用 C1 MVP 单维度虚假正式等级(GPT 6.1)。"""
    from ssui import evaluate
    series = {"pH": [6.0, 6.5, 7.0], "有机质": [30, 40, 50]}
    result = evaluate(series, scope="production")
    # 不应输出"中度可持续"等正式等级(那需要完整 25 项)
    assert result["grade"] != "中度可持续", "缺数据不应给正式等级"
    assert result["grade"] != "高度可持续"
    assert result.get("is_na") is True


def test_ssui_grade_boundaries():
    """等级边界(甲方 Table[76])。"""
    from ssui import _grade, _load
    params = _load()
    # 测试等级边界
    assert _grade(0.9, params) in ("高度可持续", "0.8-1.0")
    assert _grade(0.7, params) in ("中度可持续", "0.6-0.8")
    assert _grade(0.5, params) in ("低度可持续", "0.4-0.6")
    assert _grade(0.2, params) in ("不可持续", "<0.4")
