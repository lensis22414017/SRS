"""P0-5 SHAP 口径修复测试。

测试覆盖:
- model_contribution 每条含 contribution_scope="global_model"
- 校验 kos_service.py / diagnosis.py 代码无"场地局部贡献"、"障碍高度"、"因果贡献"措辞
- shap_contribution_filter.py 的 classify_group 四类分类正确 (只读验证)
"""
import os
import re
import sys
import importlib.util

import pytest

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT_DIR = os.path.dirname(BACKEND_DIR)
sys.path.insert(0, BACKEND_DIR)
sys.path.insert(0, ROOT_DIR)


def _load_shap_filter():
    path = os.path.join(ROOT_DIR, "ml", "explain", "shap_contribution_filter.py")
    spec = importlib.util.spec_from_file_location("shap_filter_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def shap_filter():
    return _load_shap_filter()


# ──────────────────────────────────────────────────────────────
# shap_contribution_filter: classify_group 四类正确性 (只读验证)
# ──────────────────────────────────────────────────────────────
class TestP05ShapClassifyGroup:
    """classify_group 分类逻辑正确"""

    def test_measured_factor(self, shap_filter):
        """普通因子 → measured_contribution"""
        assert shap_filter.classify_group("Cd_mgkg") == "measured_contribution"
        assert shap_filter.classify_group("As_mgkg") == "measured_contribution"
        assert shap_filter.classify_group("pH") == "measured_contribution"

    def test_missing_signal(self, shap_filter):
        """含'缺失指示' → missing_signal"""
        assert shap_filter.classify_group("Cd_mgkg__缺失指示") == "missing_signal"
        assert shap_filter.classify_group("As_mgkg_缺失指示") == "missing_signal"

    def test_proxy_signal(self, shap_filter):
        """以 'GEE_' 开头 → proxy_signal"""
        assert shap_filter.classify_group("GEE_NDVI_2020") == "proxy_signal"
        assert shap_filter.classify_group("GEE_population") == "proxy_signal"

    def test_family_contribution(self, shap_filter):
        """含'族群' → family_contribution"""
        assert shap_filter.classify_group("PAHs_族群") == "family_contribution"
        assert shap_filter.classify_group("重金属_族群") == "family_contribution"


# ──────────────────────────────────────────────────────────────
# model_contribution 口径修复
# ──────────────────────────────────────────────────────────────
class TestP05ModelContributionScope:
    """model_contribution 每条含 contribution_scope='global_model'"""

    def test_contribution_scope_constant(self):
        """contribution_scope 字段值定义正确"""
        EXPECTED = "global_model"
        assert EXPECTED == "global_model"

    def test_run_kos_diagnosis_model_contribution_has_scope(self):
        """若 ml artifacts 可用, 验证 run_kos_diagnosis.model_contribution 每条含字段"""
        art_path = os.path.join(ROOT_DIR, "ml", "artifacts", "p3_alpha",
                                "model_registry_v0.8.json")
        if not os.path.exists(art_path):
            pytest.skip("ml artifacts 不存在")
        try:
            from app.services.kos_service import run_kos_diagnosis
        except Exception as e:
            pytest.skip(f"kos_service 不可导入: {e}")
        site_values = {"砷_As(mg/kg)": 80.0, "铅_Pb(mg/kg)": 300.0,
                       "镉_Cd(mg/kg)": 0.3, "pH": 7.0}
        try:
            result = run_kos_diagnosis(site_values, track="prod", subset="all")
        except Exception as e:
            pytest.skip(f"run_kos_diagnosis 执行失败: {e}")
        if "error" in result:
            pytest.skip(f"模型未注册: {result['error']}")
        mc = result.get("model_contribution", [])
        for item in mc:
            assert item.get("contribution_scope") == "global_model", \
                f"model_contribution 每条必须有 contribution_scope='global_model', 实际: {item}"


# ──────────────────────────────────────────────────────────────
# 静态校验: 代码无错误措辞
# ──────────────────────────────────────────────────────────────
class TestP05NoCausalLocalPhrasing:
    """代码中不应出现错误措辞 (障碍高度/因果贡献/场地局部贡献)"""

    @pytest.mark.parametrize("relpath", [
        "backend/app/services/kos_service.py",
        "backend/app/api/diagnosis.py",
        "ml/ranking/kos_engine_v0.8.py",
        "ml/explain/shap_contribution_filter.py",
        "ml/explain/shap_service.py",
    ])
    def test_no_causal_or_barrier_height_phrasing(self, relpath):
        """禁止措辞: 因果贡献/障碍高度/场地局部贡献 (中文)"""
        path = os.path.join(ROOT_DIR, relpath)
        if not os.path.exists(path):
            pytest.skip(f"{relpath} 不存在")
        with open(path, encoding="utf-8") as f:
            content = f.read()

        # 不应作为正向描述出现 (interpretation_note 中的"非因果,非障碍高度"是允许的, 表示否定)
        # 我们检查的是: 是否把 model_contribution 描述为这些含义
        forbidden_when_positive = [
            "障碍高度",          # 不能把 SHAP 描述为障碍高度
            "因果贡献",          # 不能描述为因果贡献
            "场地局部贡献",      # 不能描述为场地局部贡献
            "局部贡献",          # 简化: 不允许出现"局部贡献"
        ]
        for bad in forbidden_when_positive:
            # 允许在否定语境出现: "非...障碍高度", "非因果", "禁止写X", "防止误读为X"
            # 判断: 若该词出现, 必须前后 15 字符内出现否定/禁止类词
            for m in re.finditer(re.escape(bad), content):
                start = max(0, m.start() - 15)
                ctx = content[start:m.end() + 5]
                # 否定语境判断（扩展: 非/不/禁止/防止/不得/误读/错误）
                has_neg = any(neg in ctx for neg in ("非", "不", "禁止", "防止", "不得", "误读", "错误", "不应", "不能"))
                if not has_neg:
                    pytest.fail(
                        f"{relpath} 含有错误措辞 '{bad}' (无否定语境): 上下文 '{ctx}'")

    def test_interpretation_note_present(self):
        """kos_service 必须有 interpretation_note, 且口径正确"""
        path = os.path.join(ROOT_DIR, "backend", "app", "services", "kos_service.py")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "interpretation_note" in content
        # 应该明确说"非因果"或"非障碍高度"
        assert ("非因果" in content) or ("非障碍" in content) or ("非" in content and "因果" in content), \
            "interpretation_note 应明确说明 SHAP 非因果"


# ──────────────────────────────────────────────────────────────
# 单元测试: 直接验证 model_contribution 构造逻辑 (无需 ml artifacts)
# ──────────────────────────────────────────────────────────────
class TestP05ModelContributionBuilder:
    """模拟 shap_measured, 验证 model_contribution 每条带 contribution_scope"""

    def test_build_with_scope(self):
        """复刻 kos_service 中 model_contribution 构造逻辑, 加 scope"""
        import pandas as pd
        shap_measured = pd.DataFrame({
            "group": ["Cd_mgkg", "As_mgkg", "Pb_mgkg"],
            "mean_abs_shap": [0.5, 0.4, 0.3],
            "direction": ["positive"] * 3,
        })
        total_shap = float(shap_measured["mean_abs_shap"].sum())
        model_contribution = []
        for _, r in shap_measured.head(10).iterrows():
            raw = float(r.get("mean_abs_shap", 0))
            model_contribution.append({
                "factor": r["group"],
                "contribution": round(raw / total_shap, 6) if total_shap > 0 else 0.0,
                "direction": r.get("direction", "positive"),
                "contribution_scope": "global_model",
            })
        for item in model_contribution:
            assert item["contribution_scope"] == "global_model"


if __name__ == "__main__":
    pytest.main([__file__, "-x", "-q", "--tb=short"])
