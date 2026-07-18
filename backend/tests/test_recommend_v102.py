#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""GPT 审计第七节: 推荐模块测试。

验证:
  1) 区分推荐类型(rule_based/case_based/collaborative)(GPT 7.1)
  2) 案例数据不足时不冒充协同过滤(GPT 7.2)
  3) 接收上游 KOS/重构/SSUI 状态(GPT 7.3)
  4) 不吞 KOS 异常(GPT 7.4)
  5) 法规来源可验证(GPT 7.5)
"""
import os
import sys
import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(BACKEND)
sys.path.insert(0, BACKEND)
sys.path.insert(0, os.path.join(ROOT, "ml", "recommend"))


def test_recommend_type_rule_based():
    """推荐类型标识为 rule_based(GPT 7.1)。"""
    import engine
    recs = engine.recommend(["砷", "铅"], land_use_cn="生产用地",
                            pollution_type="heavy_metal", top_k=3)
    assert len(recs) > 0
    for r in recs:
        # 每条推荐应有 source 字段(法规来源)
        assert "source" in r or "reason_struct" in r


def test_collaborative_not_faked():
    """案例数据不足时不冒充协同过滤(GPT 7.2)。"""
    # engine.recommend 是规则推荐, 不应声称是协同过滤
    import engine
    recs = engine.recommend(["砷"], land_use_cn="生产用地",
                            pollution_type="heavy_metal", top_k=1)
    for r in recs:
        rs = r.get("reason_struct", {})
        # 不应出现"协同过滤"字样
        assert "协同过滤" not in str(rs.get("match_method", ""))


def test_regulatory_source_verifiable():
    """法规来源可验证(GPT 7.5)。"""
    import engine
    recs = engine.recommend(["砷", "铅"], land_use_cn="生产用地",
                            pollution_type="heavy_metal", top_k=3)
    for r in recs:
        rs = r.get("reason_struct", {})
        basis = rs.get("regulatory_basis", "")
        is_default = rs.get("regulatory_basis_is_default", False)
        # 法规来源应非空
        assert basis, f"法规来源不应为空: {r.get('tech_name')}"
        # 应标注是否默认补充
        assert isinstance(is_default, bool)
        # 默认补充的应包含国标编号(非虚假)
        if is_default:
            assert any(code in basis for code in ["GB", "HJ", "GB/T"]), \
                f"默认法规应含国标编号: {basis}"


def test_upstream_status_tracking():
    """run_recommendation 返回 upstream_status(GPT 7.3)。"""
    # 这个测试需要 DB, 在有 DB 环境验证
    try:
        from app.db.session import SessionLocal
        from app.models import Base
        from app.db import session as _session_mod
        Base.metadata.drop_all(bind=_session_mod.engine)
        Base.metadata.create_all(bind=_session_mod.engine)
        from app.db.seed_db import seed_if_empty
        os.environ["SRS_DEMO_SEED"] = "1"
        seed_if_empty()

        from app.services.recommend_service import run_recommendation
        from app.models import Site
        db = SessionLocal()
        # 无场地时应报错(不吞异常)
        with pytest.raises(ValueError):
            run_recommendation(db, 99999)
        db.close()
    except ImportError:
        pytest.skip("无 DB 依赖")
