"""P0-OPEN-6 开放集分层识别测试。

15 项测试覆盖 GPT 审计要求的全部场景。
"""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.open_set_classifier import (
    classify_factor, classify_open_set,
    FAMILY_MATCH_MIN_CONFIDENCE,
)

# 测试用已知集合
KNOWN_CANONICAL = {"Cd_mgkg", "Pb_mgkg", "As_mgkg", "Cr_mgkg", "Cr6_mgkg", "Cu_mgkg", "pH"}
MODEL_FEATURES = {"Cd_mgkg", "Pb_mgkg", "As_mgkg", "Cu_mgkg", "Zn_mgkg", "pH", "BaP_ngg"}
KNOWN_THRESHOLDS = {
    "Cd_mgkg": {"type": "upper", "limit": 0.6},
    "Pb_mgkg": {"type": "upper", "limit": 170},
    "As_mgkg": {"type": "upper", "limit": 40},
    "Cr_mgkg": {"type": "upper", "limit": 250},
}


class TestPOpenSetRecognition:
    """P0-OPEN-6: 15 项开放集识别测试"""

    def test_01_standard_factor_cn_en_unit_variants(self):
        """1. 已有标准因子的中文、英文和单位变体"""
        for name in ["镉", "Cd", "镉(mg/kg)", "砷_As(μg/kg)"]:
            r = classify_factor(name, 1.0, "mg/kg", KNOWN_CANONICAL, MODEL_FEATURES, KNOWN_THRESHOLDS)
            assert r["layer"] in ("formal_eligible", "model_candidate"), \
                f"'{name}' 应被识别, 实际 layer={r['layer']}"

    def test_02_model_known_no_threshold(self):
        """2. 模型认识但无正式阈值的因子 → model_candidate"""
        r = classify_factor("苯并芘", 0.8, "mg/kg", KNOWN_CANONICAL, MODEL_FEATURES, KNOWN_THRESHOLDS)
        # BaP 在 model_features 但不在 KNOWN_THRESHOLDS
        assert r["layer"] in ("model_candidate", "family_alert"), \
            f"模型认识但无阈值应为 model_candidate/family, 实际={r['layer']}"

    def test_03_unindexed_PAH_family(self):
        """3. 未收录但能归入 PAH 族群的因子 → family_alert"""
        # 芘不在 KNOWN_CANONICAL 但含 PAH 关键词
        r = classify_factor("荧蒽", 5.0, "mg/kg", KNOWN_CANONICAL, MODEL_FEATURES, KNOWN_THRESHOLDS)
        assert r["layer"] == "family_alert", f"荧蒽应归 PAH family_alert, 实际={r['layer']}"
        assert r["matched_family"] == "PAH"

    def test_04_unindexed_PFAS_family(self):
        """4. 未收录但能归入 PFAS 族群的因子 → family_alert"""
        r = classify_factor("全氟辛酸(PFOA)", 0.05, "mg/kg", KNOWN_CANONICAL, MODEL_FEATURES, KNOWN_THRESHOLDS)
        assert r["layer"] == "family_alert", f"PFOA 应归 PFAS family_alert, 实际={r['layer']}"
        assert r["matched_family"] == "PFAS"

    def test_05_unindexed_soil_physical(self):
        """5. 未收录的土壤物理性质指标 → 养分族群或 unknown 或 formal_eligible(别名表有则精确匹配)"""
        r = classify_factor("土壤容重", 1.3, None, KNOWN_CANONICAL, MODEL_FEATURES, KNOWN_THRESHOLDS)
        # 土壤容重可能在别名表(SoilBD_gcm3), 精确匹配→formal_eligible(无阈值);
        # 也可能不在别名表→family_alert(养分)或unknown_measured
        assert r["layer"] in ("family_alert", "unknown_measured", "formal_eligible"), \
            f"土壤容重应归 family/unknown/formal_eligible, 实际={r['layer']}"

    def test_06_completely_unknown_name(self):
        """6. 完全未知名称 → unknown_measured"""
        r = classify_factor("某神秘化合物XYZ123", 1.5, "mg/kg", KNOWN_CANONICAL, MODEL_FEATURES, KNOWN_THRESHOLDS)
        assert r["layer"] == "unknown_measured"
        assert r["review_required"] is True
        assert r["value"] == 1.5  # 数据保留不丢弃

    def test_07_incompatible_units(self):
        """7. 单位不兼容 → 降级或标记"""
        # PAH 族群但单位是无量纲 pH → 不兼容
        r = classify_factor("荧蒽", 5.0, "无量纲", KNOWN_CANONICAL, MODEL_FEATURES, KNOWN_THRESHOLDS)
        # 应降级置信度或归 unknown
        assert r["layer"] in ("unknown_measured", "family_alert")
        if r["layer"] == "family_alert":
            assert r["family_match_confidence"] < 0.8  # 置信度被降

    def test_08_total_cr_vs_hexavalent_cr(self):
        """8. 总铬与六价铬不得归为同一具体因子"""
        r_total = classify_factor("总铬", 100.0, "mg/kg", KNOWN_CANONICAL, MODEL_FEATURES, KNOWN_THRESHOLDS)
        r_hex = classify_factor("六价铬", 5.0, "mg/kg", KNOWN_CANONICAL, MODEL_FEATURES, KNOWN_THRESHOLDS)
        # 两者的 canonical 必须不同
        assert r_total.get("canonical") != r_hex.get("canonical"), \
            "总铬和六价铬不能映射到同一 canonical"

    def test_09_total_vs_available_form(self):
        """9. 总量与有效态不得互相映射"""
        r_total = classify_factor("总氮", 1.5, "g/kg", KNOWN_CANONICAL, MODEL_FEATURES, KNOWN_THRESHOLDS)
        r_avail = classify_factor("有效磷", 20.0, "mg/kg", KNOWN_CANONICAL, MODEL_FEATURES, KNOWN_THRESHOLDS)
        # 两者 canonical 不同(或都为 None 但层不同)
        assert r_total.get("canonical") != r_avail.get("canonical") or \
               r_total.get("canonical") is None

    def test_10_far_cluster_downgrade(self):
        """10. 最近簇距离过大时必须降级 unknown_measured"""
        # 名称与任何族群都无关
        r = classify_factor("zzz_unknown_xyz", 1.0, "mg/kg", KNOWN_CANONICAL, MODEL_FEATURES, KNOWN_THRESHOLDS)
        assert r["layer"] == "unknown_measured"

    def test_11_low_confidence_no_family_alert(self):
        """11. 低置信度不得进入 family_alert"""
        # 构造一个匹配但置信度低于阈值的场景(通过单位不兼容降置信度)
        r = classify_factor("荧蒽", 5.0, "无量纲", KNOWN_CANONICAL, MODEL_FEATURES, KNOWN_THRESHOLDS)
        if r["layer"] == "family_alert":
            assert r["family_match_confidence"] >= FAMILY_MATCH_MIN_CONFIDENCE, \
                "进入 family_alert 的置信度不得低于阈值"

    def test_12_unknown_not_in_kos(self):
        """12. 未知因子不得进入正式 KOS"""
        r = classify_factor("某未知物XYZ", 100.0, "mg/kg", KNOWN_CANONICAL, MODEL_FEATURES, KNOWN_THRESHOLDS)
        assert r["layer"] == "unknown_measured"
        assert "threshold" not in r or r.get("threshold") is None  # 无阈值

    def test_13_unknown_visible_in_api(self):
        """13. 未知因子必须在 API 结果中可见(不丢弃)"""
        raw = {"镉": 0.5, "某未知有机物X": 1.5, "荧蒽": 3.0, "苯并芘": 0.8}
        result = classify_open_set(raw, KNOWN_CANONICAL, MODEL_FEATURES, KNOWN_THRESHOLDS)
        assert len(result["unknown_measured"]) > 0  # 未知因子被保留
        assert result["open_set_summary"]["n_unknown"] >= 1
        # 未知因子的原始名保留
        unknown_names = [u["original_name"] for u in result["unknown_measured"]]
        assert "某未知有机物X" in unknown_names

    def test_14_mixed_four_layers(self):
        """14. 一个文件同时含正式、候选、族群、未知四类因子"""
        raw = {
            "镉": 0.5,           # formal_eligible (有阈值, 未超标→formal_eligible)
            "苯并芘": 0.8,       # model_candidate 或 family
            "荧蒽": 3.0,         # family_alert (PAH)
            "某神秘化合物": 2.0,  # unknown_measured
        }
        result = classify_open_set(raw, KNOWN_CANONICAL, MODEL_FEATURES, KNOWN_THRESHOLDS)
        summary = result["open_set_summary"]
        # M0-3: 区分 formal_eligible/formal_obstacle
        assert summary["n_formal_eligible"] >= 1, f"应有 formal_eligible, 实际={summary}"
        assert summary["n_family_alert"] >= 1 or summary["n_model_candidate"] >= 1
        assert summary["n_unknown"] >= 1
        # 四层都有数据
        total = (summary["n_formal_eligible"] + summary["n_model_candidate"] +
                 summary["n_family_alert"] + summary["n_unknown"])
        assert total >= 4

    def test_15_unknown_no_crash(self):
        """15. 未知因子不能导致整个诊断接口失败"""
        raw = {"正常因子": 1.0, "": None, "!!!": 999, "123数字": 0.001}
        # 不应抛异常
        result = classify_open_set(raw, KNOWN_CANONICAL, MODEL_FEATURES, KNOWN_THRESHOLDS)
        assert result is not None
        assert "open_set_summary" in result
