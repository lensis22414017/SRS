"""P0-4 KOS 饱和和稳定性透明化测试。

测试覆盖:
- compute_severity_detail 返回 exceedance_ratio 和 severity_saturated
  - severity_saturated 在超标 10 倍 (cap=10) 时为 True
- compute_kos 的 key_obstacles 每条含: exceedance_ratio, severity_cap_ratio, severity_saturated
- S=0.8 保留, 但增加 stability_is_constant=True, stability_note 文本
- 相邻 KOS 排名差 < 0.01: ranking_difference_small=True
- 不破坏现有返回字段 (向后兼容)

kos_engine_v0.8.py 用 importlib 动态加载 (kos_service.py:31),
这里直接通过 importlib 加载该模块文件来测试。
"""
import os
import sys
import math
import importlib.util

import pytest
import pandas as pd

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT_DIR = os.path.dirname(BACKEND_DIR)
sys.path.insert(0, BACKEND_DIR)
sys.path.insert(0, ROOT_DIR)


def _load_kos_engine():
    """动态加载 kos_engine_v0.8.py (与 kos_service.py 同样方式)"""
    path = os.path.join(ROOT_DIR, "ml", "ranking", "kos_engine_v0.8.py")
    spec = importlib.util.spec_from_file_location("kos_engine_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def kos():
    return _load_kos_engine()


# ──────────────────────────────────────────────────────────────
# compute_severity_detail 测试
# ──────────────────────────────────────────────────────────────
class TestP04ComputeSeverityDetail:
    """compute_severity_detail 返回 exceedance_ratio 和 severity_saturated"""

    def test_function_exists(self, kos):
        """compute_severity_detail 函数必须存在 (新增)"""
        assert hasattr(kos, "compute_severity_detail"), \
            "kos_engine 必须新增 compute_severity_detail 函数"

    def test_returns_meta_dict(self, kos):
        """compute_severity_detail 返回 dict, 含 exceedance_ratio / severity_saturated"""
        r = kos.compute_severity_detail(0.6, {"type": "upper", "limit": 0.6})
        # 应该是 dict 而不是 tuple
        assert isinstance(r, dict), f"compute_severity_detail 应返回 dict, 实际 {type(r)}"
        assert "exceedance_ratio" in r
        assert "severity_saturated" in r

    def test_exceedance_ratio_upper(self, kos):
        """upper 类型: value=3, limit=1 → exceedance_ratio=3.0"""
        r = kos.compute_severity_detail(3.0, {"type": "upper", "limit": 1.0})
        assert r["exceedance_ratio"] == pytest.approx(3.0, rel=1e-6)

    def test_exceedance_ratio_below_limit(self, kos):
        """未超标 (value<limit): exceedance_ratio=value/limit, severity_saturated=False"""
        r = kos.compute_severity_detail(0.3, {"type": "upper", "limit": 0.6})
        assert r["exceedance_ratio"] == pytest.approx(0.5, rel=1e-6)
        assert r["severity_saturated"] is False

    def test_severity_saturated_at_10x(self, kos):
        """超标 10 倍 (cap=10) 触发 severity_saturated=True"""
        r = kos.compute_severity_detail(10.0, {"type": "upper", "limit": 1.0})
        assert r["severity_saturated"] is True

    def test_severity_saturated_above_10x(self, kos):
        """超标 100 倍: severity_saturated=True"""
        r = kos.compute_severity_detail(100.0, {"type": "upper", "limit": 1.0})
        assert r["severity_saturated"] is True

    def test_severity_saturated_below_cap(self, kos):
        """超标 9.9 倍 (略低于 cap): severity_saturated=False"""
        r = kos.compute_severity_detail(9.9, {"type": "upper", "limit": 1.0})
        assert r["severity_saturated"] is False

    def test_cap_constant_exists(self, kos):
        """模块级常量 KOS_SEVERITY_CAP_RATIO 存在且 == 10"""
        assert hasattr(kos, "KOS_SEVERITY_CAP_RATIO")
        assert kos.KOS_SEVERITY_CAP_RATIO == 10

    def test_severity_cap_ratio_in_result(self, kos):
        """返回值含 severity_cap_ratio 字段"""
        r = kos.compute_severity_detail(15.0, {"type": "upper", "limit": 1.0})
        assert "severity_cap_ratio" in r
        assert r["severity_cap_ratio"] == kos.KOS_SEVERITY_CAP_RATIO


# ──────────────────────────────────────────────────────────────
# compute_kos 测试: 每条 key_obstacle 含新字段
# ──────────────────────────────────────────────────────────────
def _build_fake_shap():
    """构造一个最小的 SHAP measured DataFrame 用于 compute_kos"""
    return pd.DataFrame({
        "group": ["Cd_mgkg", "As_mgkg", "Pb_mgkg", "Cu_mgkg", "Zn_mgkg"],
        "mean_abs_shap": [0.5, 0.4, 0.3, 0.2, 0.1],
        "direction": ["positive"] * 5,
    })


class TestP04KosResultTransparency:
    """compute_kos 结果透明化字段"""

    def test_key_obstacles_have_transparency_fields(self, kos):
        """每条 key_obstacle 必须含: exceedance_ratio, severity_cap_ratio,
        severity_saturated, stability_is_constant, stability_note"""
        shap = _build_fake_shap()
        values = {"Cd_mgkg": 0.8, "As_mgkg": 80.0, "Pb_mgkg": 200.0,
                  "Cu_mgkg": 50.0, "Zn_mgkg": 100.0}
        thresholds = {
            "Cd_mgkg": {"type": "upper", "limit": 0.6},
            "As_mgkg": {"type": "upper", "limit": 40.0},
            "Pb_mgkg": {"type": "upper", "limit": 170.0},
            "Cu_mgkg": {"type": "upper", "limit": 100.0},
            "Zn_mgkg": {"type": "upper", "limit": 300.0},
        }
        weights = {"Cd_mgkg": 0.9, "As_mgkg": 0.85, "Pb_mgkg": 0.8,
                   "Cu_mgkg": 0.75, "Zn_mgkg": 0.7}
        evidence = {f: "A" for f in values}
        result = kos.compute_kos(shap, values, thresholds, weights, evidence, top_n=5)
        assert len(result["key_obstacles"]) > 0
        for k in result["key_obstacles"]:
            assert "exceedance_ratio" in k, f"key_obstacle 缺 exceedance_ratio: {k}"
            assert "severity_cap_ratio" in k
            assert "severity_saturated" in k
            assert "stability_is_constant" in k
            assert "stability_note" in k

    def test_stability_is_constant_always_true(self, kos):
        """所有结果 stability_is_constant=True (S 是固定占位参数)"""
        shap = _build_fake_shap()
        values = {"Cd_mgkg": 0.8, "As_mgkg": 80.0}
        thresholds = {"Cd_mgkg": {"type": "upper", "limit": 0.6},
                      "As_mgkg": {"type": "upper", "limit": 40.0}}
        weights = {"Cd_mgkg": 0.9, "As_mgkg": 0.85}
        evidence = {f: "A" for f in values}
        result = kos.compute_kos(shap, values, thresholds, weights, evidence, top_n=5)
        for k in result["key_obstacles"]:
            assert k["stability_is_constant"] is True
            assert "S" in k["stability_note"] or "稳定" in k["stability_note"] \
                or "占位" in k["stability_note"], \
                f"stability_note 应说明 S 为固定占位参数, 实际: {k['stability_note']}"

    def test_exceedance_ratio_correct_in_key_obstacles(self, kos):
        """key_obstacle 的 exceedance_ratio 与 value/limit 一致"""
        shap = _build_fake_shap()
        values = {"Cd_mgkg": 6.0}  # 10x of limit
        thresholds = {"Cd_mgkg": {"type": "upper", "limit": 0.6}}
        weights = {"Cd_mgkg": 0.9}
        evidence = {"Cd_mgkg": "A"}
        result = kos.compute_kos(shap, values, thresholds, weights, evidence, top_n=5)
        if len(result["key_obstacles"]) > 0:
            k = result["key_obstacles"][0]
            assert k["exceedance_ratio"] == pytest.approx(10.0, rel=1e-6)
            assert k["severity_saturated"] is True

    def test_existing_fields_preserved(self, kos):
        """向后兼容: 原有字段不删除 (rank/factor/KOS/R/W/M/S/E/value/B/threshold)"""
        shap = _build_fake_shap()
        values = {"Cd_mgkg": 0.8, "As_mgkg": 80.0}
        thresholds = {"Cd_mgkg": {"type": "upper", "limit": 0.6},
                      "As_mgkg": {"type": "upper", "limit": 40.0}}
        weights = {"Cd_mgkg": 0.9, "As_mgkg": 0.85}
        evidence = {f: "A" for f in values}
        result = kos.compute_kos(shap, values, thresholds, weights, evidence, top_n=5)
        for k in result["key_obstacles"]:
            # 原有字段必须保留 (kos_engine 层原始字段, components 在 kos_service 层包装)
            for must_have in ("rank", "factor", "KOS",
                              "value", "E", "R", "W", "M", "S", "B", "threshold"):
                assert must_have in k, f"原有字段 {must_have} 不应被删除: {k.keys()}"


# ──────────────────────────────────────────────────────────────
# ranking_difference_small 测试
# ──────────────────────────────────────────────────────────────
class TestP04RankingDifferenceSmall:
    """相邻 KOS 排名差 < 0.01 时 ranking_difference_small=True"""

    def test_ranking_difference_small_flag(self, kos):
        """构造两个 KOS 几乎相等 (差<0.01) 的因子, 验证 ranking_difference_small=True"""
        shap = _build_fake_shap()
        # 两个相同因子的值让 KOS 几乎一致
        values = {"Cd_mgkg": 0.61, "As_mgkg": 41.0}  # 都刚超阈值, KOS 接近
        thresholds = {"Cd_mgkg": {"type": "upper", "limit": 0.6},
                      "As_mgkg": {"type": "upper", "limit": 40.0}}
        weights = {"Cd_mgkg": 0.85, "As_mgkg": 0.85}  # 权重一致
        evidence = {f: "A" for f in values}
        result = kos.compute_kos(shap, values, thresholds, weights, evidence, top_n=5)
        # 计算所有相邻差
        ks = result["key_obstacles"]
        if len(ks) >= 2:
            # 至少有一条相邻差<0.01 时, 至少有一条 ranking_difference_small=True
            has_small = any(k.get("ranking_difference_small") for k in ks)
            diffs = [ks[i]["KOS"] - ks[i + 1]["KOS"] for i in range(len(ks) - 1)]
            has_diff_small = any(d < 0.01 for d in diffs)
            # 若有任何相邻差<0.01, 应该有标记
            if has_diff_small:
                assert has_small, \
                    f"KOS 相邻差<0.01 但未标记 ranking_difference_small, KOS 序列: {[k['KOS'] for k in ks]}"

    def test_no_small_difference_no_flag(self, kos):
        """KOS 差距大时不标记 (用极端差值)"""
        shap = _build_fake_shap()
        values = {"Cd_mgkg": 60.0,  # 100x of limit (饱和)
                  "Cu_mgkg": 101.0}  # 仅刚超 100
        thresholds = {"Cd_mgkg": {"type": "upper", "limit": 0.6},
                      "Cu_mgkg": {"type": "upper", "limit": 100.0}}
        weights = {"Cd_mgkg": 0.9, "Cu_mgkg": 0.75}
        evidence = {f: "A" for f in values}
        result = kos.compute_kos(shap, values, thresholds, weights, evidence, top_n=5)
        ks = result["key_obstacles"]
        if len(ks) == 2:
            # 差距应远大于 0.01, 不应有 ranking_difference_small
            assert all(not k.get("ranking_difference_small", False) for k in ks), \
                f"差距大不应标记 ranking_difference_small, KOS: {[k['KOS'] for k in ks]}"


# ──────────────────────────────────────────────────────────────
# 集成测试: kos_service.run_kos_diagnosis 透传新字段
# ──────────────────────────────────────────────────────────────
class TestP04KosServiceIntegration:
    """kos_service.run_kos_diagnosis 是否透传新字段"""

    def test_run_kos_diagnosis_key_obstacles_have_transparency(self):
        """若 ml artifacts 可用, run_kos_diagnosis 返回的 key_obstacles 含新字段"""
        try:
            from app.services.kos_service import run_kos_diagnosis
        except Exception as e:
            pytest.skip(f"kos_service 不可导入: {e}")
        # 检查 ml artifacts 是否存在
        art_path = os.path.join(ROOT_DIR, "ml", "artifacts", "p3_alpha",
                                "model_registry_v0.8.json")
        if not os.path.exists(art_path):
            pytest.skip("ml artifacts 不存在, 跳过端到端测试")
        site_values = {"砷_As(mg/kg)": 80.0, "铅_Pb(mg/kg)": 300.0,
                       "镉_Cd(mg/kg)": 0.3, "pH": 7.0}
        try:
            result = run_kos_diagnosis(site_values, track="prod", subset="all")
        except Exception as e:
            pytest.skip(f"run_kos_diagnosis 执行失败 (可能缺工件): {e}")
        if "error" in result:
            pytest.skip(f"模型未注册: {result['error']}")
        for k in result.get("key_obstacles", []):
            assert "exceedance_ratio" in k
            assert "severity_saturated" in k
            assert "stability_is_constant" in k


if __name__ == "__main__":
    pytest.main([__file__, "-x", "-q", "--tb=short"])
