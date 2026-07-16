"""P0-1 因子命名、化学形态和单位映射测试。

测试覆盖:
- 镉/Cd/cd/CD/镉_Cd(mg/kg) 都映射到 Cd_mgkg
- pH/pH值/酸碱度 都映射到 pH
- 总铬/Cr → Cr_mgkg，六价铬/Cr(VI)/Cr6+ → Cr6_mgkg（不混淆）
- 砷_As(μg/kg) 的单位转换 (÷1000)
- 同一因子重复列 → mapping_conflicts
- 普通英文单词含 as/cd/pb 字母不误配
"""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.factor_normalizer import normalize_factors_v2, normalize_factor_name


class TestP01FactorNormalization:
    """P0-1: 因子名精确匹配与规范化"""

    def test_cadmium_variants(self):
        """镉的各种写法都映射到 Cd_mgkg"""
        for name in ["镉", "Cd", "cd", "CD", "镉_Cd", "镉(mg/kg)", "镉_Cd(mg/kg)"]:
            canon, meta = normalize_factor_name(name)
            assert canon == "Cd_mgkg", f"'{name}' 应映射到 Cd_mgkg，实际: {canon}"

    def test_pH_variants(self):
        """pH 的各种写法"""
        for name in ["pH", "pH值", "酸碱度", "SoilpH", "pH_merged"]:
            canon, meta = normalize_factor_name(name)
            assert canon == "pH", f"'{name}' 应映射到 pH，实际: {canon}"

    def test_chromium_total_vs_hexavalent(self):
        """总铬 vs 六价铬必须区分"""
        # 总铬
        for name in ["铬", "Cr", "总铬", "铬(mg/kg)"]:
            canon, _ = normalize_factor_name(name)
            assert canon == "Cr_mgkg", f"'{name}' 应映射到 Cr_mgkg(总铬)，实际: {canon}"
        # 六价铬
        for name in ["六价铬", "铬(六价)", "Cr(VI)", "Cr6+"]:
            canon, _ = normalize_factor_name(name)
            assert canon == "Cr6_mgkg", f"'{name}' 应映射到 Cr6_mgkg(六价铬)，实际: {canon}"

    def test_no_substring_mismatch(self):
        """普通英文单词含 as/cd/pb 字母不误配"""
        for name in ["批次", "record", "sample", "period"]:
            canon, _ = normalize_factor_name(name)
            # 不应映射到任何因子（应为 None 或保留原名）
            assert canon not in ("Cd_mgkg", "As_mgkg", "Pb_mgkg"), \
                f"'{name}' 不应误配到重金属因子，实际: {canon}"

    def test_unit_conversion_ugkg_to_mgkg(self):
        """μg/kg → mg/kg 除以 1000"""
        result = normalize_factors_v2({"砷_As(μg/kg)": 12420.0})
        assert result["factors"]["As_mgkg"] == pytest.approx(12.42, rel=1e-3)
        # 记录转换信息
        d = result["mapping_details"][0]
        assert d["unit_raw"] in ("μg/kg", "ug/kg")
        assert d["unit_converted"] == "mg/kg"
        assert d["conversion_factor"] == 0.001

    def test_unit_conversion_ngg_to_mgkg(self):
        """ng/g → mg/kg 除以 1000（与 μg/kg 等值）"""
        result = normalize_factors_v2({"镉(ng/g)": 500.0})
        assert result["factors"]["Cd_mgkg"] == pytest.approx(0.5, rel=1e-3)

    def test_mgkg_no_conversion(self):
        """mg/kg 不转换"""
        result = normalize_factors_v2({"铜(mg/kg)": 100.0})
        assert result["factors"]["Cu_mgkg"] == 100.0

    def test_duplicate_column_conflict(self):
        """同一 canonical 多来源列 → mapping_conflicts"""
        result = normalize_factors_v2({
            "镉": 0.5,
            "Cd": 0.8,  # 与"镉"冲突
        })
        assert len(result["mapping_conflicts"]) >= 1
        assert result["mapping_conflicts"][0]["canonical"] == "Cd_mgkg"
        assert len(result["mapping_conflicts"][0]["sources"]) >= 2
        # data_quality_flags 应有冲突提示
        assert any("冲突" in f for f in result["data_quality_flags"])

    def test_unmapped_preserved(self):
        """未匹配的因子保留原名"""
        result = normalize_factors_v2({"某未知有机物X": 1.5})
        assert "某未知有机物X" in result["factors"]
        assert "某未知有机物X" in result["unmapped"]

    def test_none_and_nan_skipped(self):
        """None/NaN 值跳过"""
        result = normalize_factors_v2({"镉": None, "铅": float("nan"), "锌": 50.0})
        assert "Cd_mgkg" not in result["factors"]
        assert "Pb_mgkg" not in result["factors"]
        assert result["factors"]["Zn_mgkg"] == 50.0

    def test_full_heavy_metal_set(self):
        """完整重金属因子集映射"""
        raw = {"镉": 0.5, "铅": 30, "砷": 20, "铬": 100, "汞": 0.5,
               "铜": 50, "锌": 200, "镍": 40, "pH": 7.0}
        result = normalize_factors_v2(raw)
        f = result["factors"]
        assert f["Cd_mgkg"] == 0.5
        assert f["Pb_mgkg"] == 30
        assert f["As_mgkg"] == 20
        assert f["Cr_mgkg"] == 100
        assert f["Hg_mgkg"] == 0.5
        assert f["Cu_mgkg"] == 50
        assert f["Zn_mgkg"] == 200
        assert f["Ni_mgkg"] == 40
        assert f["pH"] == 7.0

    def test_NFKC_normalization(self):
        """全角字母/数字 NFKC 归一"""
        # 全角 C ｄ → 半角 cd
        canon, _ = normalize_factor_name("Ｃｄ")
        assert canon == "Cd_mgkg", f"NFKC 应将全角'Cd'映射到 Cd_mgkg，实际: {canon}"
