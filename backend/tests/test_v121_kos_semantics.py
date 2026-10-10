"""v1.2.1 审计 R01/R02 回归: 阈值方向、有机质/有机碳语义、单位等价与开放失败、证据准入。

夹具数值来自 2026-10-10 审计报告中的 A 场地异常(CEC 21.29 vs 10、有机质 19.1/53.63 g/kg vs 0.35 %、
全氮 3.089 vs 1.0), 仅作回归夹具, 不是经批准的科学限值。
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.db.session import SessionLocal  # noqa: E402
from app.models import StandardThreshold  # noqa: E402
from app.services import threshold_resolver as TR  # noqa: E402
from app.services.factor_normalizer import normalize_factors_v2, normalize_factor_name  # noqa: E402


@pytest.fixture()
def db():
    from app.db.init_db import create_all
    create_all()
    d = SessionLocal()
    if d.query(StandardThreshold).count() == 0:
        from app.db.load_standard_thresholds import load
        load(d)
        d.commit()
    yield d
    d.close()


def _kos():
    from app.services.kos_service import _kos_engine
    return _kos_engine


# ───────── R01: 阈值方向 ─────────
@pytest.mark.parametrize("factor,direction", [
    ("CEC_cmolkg", "lower"), ("TN_gkg", "lower"), ("OC_pct", "lower"), ("OM_gkg", "lower"),
    ("Total_P_gkg", "lower"), ("Total_K_gkg", "lower"), ("P_mgkg", "lower"), ("K_mgkg", "lower"),
    ("Hydrolyzable_N_mgkg", "lower"), ("SoilBD_gcm3", "upper"), ("EC_mScm", "upper"), ("Mn_mgkg", "upper"),
])
def test_fallback_thresholds_carry_direction(db, factor, direction):
    r = TR.resolve_threshold_from_db(db, factor, track="prod", site_pH=6.0)
    assert r["threshold"] is not None, factor
    assert r["threshold"]["type"] == direction, (factor, r["threshold"])
    assert r["threshold_resolution_status"] == "heuristic"
    assert r["evidence_grade"] == "C"


def test_official_gb15618_row_is_upper_and_grade_a(db):
    r = TR.resolve_threshold_from_db(db, "Cd_mgkg", track="prod", site_pH=6.0)
    assert r["threshold_resolution_status"] == "resolved"
    assert r["threshold"]["type"] == "upper" and r["evidence_grade"] == "A"


def test_cross_track_fallback_is_not_reported_as_resolved(db):
    # 六价铬只有 GB 36600 行; 生产轨(GB 15618)查不到时不得冒充本轨权威阈值
    r = TR.resolve_threshold_from_db(db, "Cr6_mgkg", track="prod", site_pH=6.0)
    assert r["threshold_resolution_status"] == "cross_track_fallback"
    assert r["review_required"] is True and r["evidence_grade"] == "C"


@pytest.mark.parametrize("value,expect_b", [(21.29, 0), (10.0, 0), (8.0, 1)])
def test_cec_lower_bound_semantics(db, value, expect_b):
    thr = TR.resolve_threshold_from_db(db, "CEC_cmolkg", track="prod")["threshold"]
    assert _kos().compute_severity(value, thr)[1] == expect_b


@pytest.mark.parametrize("value,expect_b", [(3.089, 0), (0.6, 1)])
def test_total_nitrogen_is_deficiency_not_upper(db, value, expect_b):
    thr = TR.resolve_threshold_from_db(db, "TN_gkg", track="prod")["threshold"]
    assert _kos().compute_severity(value, thr)[1] == expect_b


# ───────── R01: 有机质 ≠ 有机碳; 单位等价; 开放失败 ─────────
@pytest.mark.parametrize("col", ["有机质(g/kg)", "有机质", "SOM", "土壤有机质(%)"])
def test_organic_matter_never_maps_to_organic_carbon(col):
    canonical, _ = normalize_factor_name(col)
    assert canonical == "OM_gkg", (col, canonical)


@pytest.mark.parametrize("col", ["有机碳(%)", "SOC", "有机碳含量"])
def test_organic_carbon_maps_to_oc(col):
    assert normalize_factor_name(col)[0] == "OC_pct"


def test_equivalent_units_give_equal_values():
    a = normalize_factors_v2({"有机质(g/kg)": 19.1})["factors"]["OM_gkg"]
    b = normalize_factors_v2({"有机质(%)": 1.91})["factors"]["OM_gkg"]
    assert a == pytest.approx(b)
    c = normalize_factors_v2({"镉(mg/kg)": 0.6})["factors"]["Cd_mgkg"]
    d = normalize_factors_v2({"镉(μg/kg)": 600})["factors"]["Cd_mgkg"]
    assert c == pytest.approx(d)
    e = normalize_factors_v2({"有机碳(%)": 1.2})["factors"]["OC_pct"]
    f = normalize_factors_v2({"有机碳(g/kg)": 12.0})["factors"]["OC_pct"]
    assert e == pytest.approx(f)


def test_explicit_units_argument_used_and_unknown_unit_fails_closed():
    r = normalize_factors_v2({"有机质": 19.1}, units={"有机质": "g/kg"})
    assert r["factors"]["OM_gkg"] == pytest.approx(19.1)
    bad = normalize_factors_v2({"有机质": 19.1}, units={"有机质": "cmol/kg"})
    assert "OM_gkg" not in bad["factors"]
    assert any(u["canonical"] == "OM_gkg" for u in bad["unit_unresolved"])
    unknown = normalize_factors_v2({"镉": 1.0}, units={"镉": "ppbv"})
    assert "Cd_mgkg" not in unknown["factors"]


def test_speciation_qualifier_is_not_a_unit():
    r = normalize_factors_v2({"六价铬": 0.8}, units={"六价铬": "VI"})
    assert "Cr_mgkg" not in r["factors"]
    assert r["factors"].get("Cr6_mgkg") == pytest.approx(0.8)
    assert normalize_factor_name("铬_Cr(mg/kg)")[0] == "Cr_mgkg"
    assert normalize_factor_name("六价铬_Cr(VI)(mg/kg)")[0] == "Cr6_mgkg"


def test_import_header_parser_skips_speciation_group():
    from app.services.import_service import split_header_unit
    assert split_header_unit("六价铬_Cr(VI)(mg/kg)") == ("六价铬", "mg/kg")
    assert split_header_unit("有机质(g/kg)") == ("有机质", "g/kg")
    assert split_header_unit("pH") == ("pH", None)


# ───────── R02: 证据准入 ─────────
A_POINT = {"pH": 6.9, "镉(mg/kg)": 1.5839, "铅(mg/kg)": 216.9963, "有机质(g/kg)": 19.1,
           "全氮(g/kg)": 3.089, "阳离子交换量(cmol/kg)": 21.29}


def _run(db, points, **kw):
    from app.services.kos_service import run_kos_diagnosis
    site = {}
    for p in points.values():
        for k, v in p.items():
            site[k] = max(v, site.get(k, v))
    return run_kos_diagnosis(site, track="prod", subset="hm", top_n=10, site_pH=6.9, db_session=db,
                             per_point_data=points, **kw)


def test_official_topn_only_contains_grade_a_resolved(db):
    r = _run(db, {1: A_POINT, 2: {**A_POINT, "阳离子交换量(cmol/kg)": 7.5, "全氮(g/kg)": 0.6}})
    formal = r["key_obstacles"]
    assert formal, "Cd/Pb 超 GB 15618 应进入正式 Top-N"
    for k in formal:
        assert k["evidence"] == "A" and k["threshold_resolution_status"] == "resolved", k
        assert k["threshold_standard"].startswith("GB 15618"), k
    names = {k["factor"] for k in formal}
    assert {"Cd_mgkg", "Pb_mgkg"} <= names
    assert not names & {"CEC_cmolkg", "TN_gkg", "OC_pct", "OM_gkg"}
    explo = {k["factor"]: k for k in r["exploratory_obstacles"]}
    # 点 2 的 CEC 7.5 < 10、全氮 0.6 < 1.0 构成探索性(文献兜底)不足, 点 1 的 21.29/3.089 不构成
    assert explo["CEC_cmolkg"]["decision_point_id"] == 2 and explo["CEC_cmolkg"]["evidence"] == "C"
    assert explo["TN_gkg"]["value"] == pytest.approx(0.6)
    assert "OC_pct" not in explo  # 有机质不得冒充有机碳


def test_no_official_threshold_gives_insufficient_evidence(db):
    r = _run(db, {1: {"pH": 6.5, "阳离子交换量(cmol/kg)": 5.0, "全氮(g/kg)": 0.4}})
    assert r["key_obstacles"] == []
    assert r["official_ranking_status"] == "insufficient_evidence"
    assert len(r["exploratory_obstacles"]) == 2


def test_partial_official_ranking_is_labelled(db):
    r = _run(db, {1: {"pH": 6.5, "镉(mg/kg)": 0.9}})
    assert [k["factor"] for k in r["key_obstacles"]] == ["Cd_mgkg"]
    assert r["official_ranking_status"] == "partial"


def test_unit_unresolved_factor_excluded_from_formal(db):
    from app.services.kos_service import run_kos_diagnosis
    r = run_kos_diagnosis({"镉": 1.5}, track="prod", subset="hm", site_pH=6.5, db_session=db,
                          per_point_data={1: {"镉": 1.5}}, units={"镉": "ppbv"})
    assert r["key_obstacles"] == []
    assert any(u["canonical"] == "Cd_mgkg" for u in r["unit_unresolved"])


# ───────── R02 补充: 暂定 / 行业标准 / 缺失阈值 夹具 与 证据链 ─────────
def _tmp_row(db, **kw):
    row = StandardThreshold(standard_name=kw.pop("standard_name", "夹具"), version="fixture", **kw)
    db.add(row)
    db.flush()
    return row


def test_provisional_threshold_is_exploratory_only(db):
    try:
        _tmp_row(db, factor_name="Co", standard_code="GB 15618-2018", screening_value=20.0, unit="mg/kg",
                 notes="暂定值, 待审定 (测试夹具)")
        r = TR.resolve_threshold_from_db(db, "Co_mgkg", track="prod", site_pH=6.5)
        assert r["threshold_resolution_status"] == "provisional" and r["evidence_grade"] == "C"
        k = _run(db, {1: {"pH": 6.5, "镉(mg/kg)": 0.9, "钴(mg/kg)": 45.0}})
        assert "Co_mgkg" not in {x["factor"] for x in k["key_obstacles"]}
        ex = {x["factor"]: x for x in k["exploratory_obstacles"]}
        assert ex["Co_mgkg"]["evidence_chain"]["admission"] == "exploratory"
        assert ex["Co_mgkg"]["threshold_resolution_status"] == "provisional"
    finally:
        db.rollback()


def test_secondary_standard_uses_known_direction_or_is_not_judged(db):
    try:
        _tmp_row(db, factor_name="氰化物", standard_code="EPA RSL 2024", screening_value=2.3, unit="mg/kg")
        r = TR.resolve_threshold_from_db(db, "Cyanide", track="prod", site_pH=6.5)
        assert r["threshold_resolution_status"] == "secondary_standard"
        assert r["threshold_type"] == "unknown" and r["threshold"] is None  # 方向未知 → 不判定
    finally:
        db.rollback()


def test_missing_threshold_never_enters_any_ranking(db):
    r = TR.resolve_threshold_from_db(db, "Unknown_factor_xyz", track="prod", site_pH=6.5)
    assert r["threshold_resolution_status"] in ("not_found", "ambiguous")
    assert r["threshold"] is None


def test_official_items_carry_full_evidence_chain(db):
    r = _run(db, {1: {"pH": 6.9, "镉(mg/kg)": 1.5839}}, units={"镉(mg/kg)": "mg/kg"})
    ch = r["key_obstacles"][0]["evidence_chain"]
    assert ch["admission"] == "official" and ch["evidence_grade"] == "A"
    assert ch["threshold_standard"].startswith("GB 15618") and ch["threshold_type"] == "upper"
    assert ch["raw_factor"] == "镉(mg/kg)" and ch["conversion_status"] in ("identity", "converted")
    assert ch["decision_point_id"] == 1 and ch["threshold_source_id"]


# ───────── R01 补充: 有机物数值单位(ng/g)与 GB 36600 阈值单位(mg/kg)对齐 ─────────
def test_organic_threshold_unit_aligned_with_value_unit(db):
    from app.services.kos_service import run_kos_diagnosis
    pt = {"pH": 6.8, "苯并[a]芘(mg/kg)": 2.5, "石油烃(C10-C40)(mg/kg)": 600.0, "镉(mg/kg)": 25.0}
    r = run_kos_diagnosis(dict(pt), track="eco", subset="all", top_n=10, site_pH=6.8, land_use_type="第一类用地",
                          db_session=db, per_point_data={1: dict(pt)}, units={k: "mg/kg" for k in pt if k != "pH"})
    off = {k["factor"]: k for k in r["key_obstacles"]}
    # 2.5 mg/kg = 2500 ng/g, 第一类筛选值 0.55 mg/kg = 550 ng/g → 超标 4.5 倍; 不能出现 2500 vs 0.55
    assert off["BaP_ngg"]["threshold_value"] == pytest.approx(550.0) and off["BaP_ngg"]["threshold_unit"] == "ng/g"
    assert off["BaP_ngg"]["exceedance_ratio"] == pytest.approx(2500 / 550, rel=1e-3)
    # 石油烃 600 mg/kg < 826 mg/kg 第一类筛选值 → 不得进入正式 Top-N(此前单位错配会误判为超标)
    assert "TPH_ngg" not in off
    assert off["Cd_mgkg"]["threshold_value"] == pytest.approx(20.0)


def test_unit_factor_matrix():
    from app.services.factor_normalizer import unit_factor
    assert unit_factor("mg/kg", "ng/g") == 1000.0 and unit_factor("μg/kg", "mg/kg") == 0.001
    assert unit_factor("%", "g/kg") == 10.0 and unit_factor("mg/kg", "cmol(+)/kg") is None


def test_paddy_tier_used_when_farmland_is_paddy(db):
    # GB 15618 表1: 镉 6.5<pH≤7.5 水田 0.6 / 其他 0.3
    r_p = TR.resolve_threshold_from_db(db, "Cd_mgkg", track="prod", site_pH=6.9, land_use_type="水田")
    r_o = TR.resolve_threshold_from_db(db, "Cd_mgkg", track="prod", site_pH=6.9, land_use_type=None)
    assert r_p["threshold_value"] == 0.6 and r_p["land_use_type"] == "水田"
    assert r_o["threshold_value"] == 0.3 and r_o["threshold_resolution_status"] == "resolved"
    # 铜/镍/锌 无水田专列 → 水田时仍唯一解析
    assert TR.resolve_threshold_from_db(db, "Zn_mgkg", track="prod", site_pH=6.9, land_use_type="水田")["threshold_resolution_status"] == "resolved"
