"""SRS 全链路修复回归测试(brief 4.1/4.2/4.3/4.5/4.8)。

沉淀同行评审发现的新功能测试缺口(M1): 这些功能此前仅靠临时 e2e 脚本验证,
无持久单测保护, 重构易回归。
"""
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GEJIU = os.path.join(ROOT, "data", "raw",
                     "3.20250731_重金属污染场地数据表(云南个旧)_最终版.xlsx")


def _has(*mods):
    try:
        for m in mods:
            __import__(m)
        return True
    except ImportError:
        return False


needs_db = pytest.mark.skipif(not _has("sqlalchemy", "fastapi", "pandas"), reason="需 venv")
needs_data = pytest.mark.skipif(not os.path.exists(GEJIU), reason="需个旧数据")


# ============ 4.1 重金属 token 边界匹配 + 统一映射 ============
def test_heavy_metal_token_rejects_false_positives():
    """brief 4.1: baseline/case/sample/class 含 as/cd/pb 字母片段但不得判重金属。"""
    from app.services.import_service import _matches_heavy_metal_token
    for col in ["baseline", "case", "sample", "class", "discourse", "ph", "有机质"]:
        assert not _matches_heavy_metal_token(col), f"{col!r} 不应被判重金属"


def test_heavy_metal_token_accepts_real_symbols():
    from app.services.import_service import _matches_heavy_metal_token
    for col in ["as", "as(mg/kg)", "cd", "pb ", "砷", "镉", "cr"]:
        assert _matches_heavy_metal_token(col), f"{col!r} 应判重金属"


def test_resolve_mapping_plain_file_not_heavy_metal(tmp_path):
    """brief 4.1: 普通文件(含 baseline/case 列) auto 不误判 heavy_metal。"""
    import pandas as pd
    from app.services.import_service import resolve_mapping_for_file
    df = pd.DataFrame({"采样点编号": ["S1", "S2"], "baseline": [1, 2],
                       "case_id": [3, 4], "pH": [6.5, 7.0], "有机质": [15, 18]})
    f = tmp_path / "plain.xlsx"
    df.to_excel(f, index=False)
    used_id, mapping, report = resolve_mapping_for_file("auto", str(f))
    assert mapping["site"]["pollution_type"] != "heavy_metal", "普通文件被误判 heavy_metal"
    assert "confidence" in report and "factor_columns" in report


# ============ 4.2 内容指纹幂等 + 数据版本 ============
@needs_db
@needs_data
def test_idempotent_reimport_no_dup():
    """brief 4.2: 同文件重导 reimported, measurements 不翻倍, data_version 含 sha256。"""
    from app.db.session import SessionLocal
    from app.db.bootstrap import main as bootstrap
    from app.db.load_kb import main as load_kb
    from app.services.pipeline import run_import
    from app.models import Measurement
    bootstrap(); load_kb()
    db = SessionLocal()
    try:
        r1 = run_import(db, GEJIU, "yunnan_gejiu")
        n1 = r1["n_measurements"]
        assert r1.get("source_sha256"), "source_sha256 应计算"
        assert r1["source_sha256"][:12] in r1["data_version"], "data_version 应含 sha256"
        r2 = run_import(db, GEJIU, "yunnan_gejiu")
        assert r2.get("reimported") is True, "重导应 reimported"
        assert db.query(Measurement).count() == n1, "重导不应翻倍"
    finally:
        db.close()


@needs_db
def test_current_site_data_version_empty_fallback():
    """brief 4.2: 无导入批次场地回退 site{id}_n{count} 格式。"""
    from app.db.session import SessionLocal
    from app.db.bootstrap import main as bootstrap
    from app.services.versioning import current_site_data_version
    bootstrap()
    db = SessionLocal()
    try:
        dv = current_site_data_version(db, 999999)
        assert dv.startswith("site999999_n"), f"空场地版本格式错: {dv}"
    finally:
        db.close()


# ============ 4.3 导出(行数+字段+audit) ============
@needs_db
@needs_data
def test_export_measurements_rows_fields_audit():
    """brief 4.3 / AC-16: 导出行数=measurements, 含16字段, 写 audit。"""
    from app.db.session import SessionLocal
    from app.db.bootstrap import main as bootstrap
    from app.db.load_kb import main as load_kb
    from app.services.pipeline import run_import
    from app.api.data import export_site_measurements
    from app.models import AuditLog
    from types import SimpleNamespace
    bootstrap(); load_kb()
    db = SessionLocal()
    try:
        r = run_import(db, GEJIU, "yunnan_gejiu")
        sid, n = r["site_id"], r["n_measurements"]
        resp = export_site_measurements(site_id=sid, format="csv",
                                        user=SimpleNamespace(id=1), db=db)
        lines = [l for l in resp.body.decode("utf-8-sig").split("\n") if l.strip()]
        assert len(lines) - 1 == n, f"导出行数 {len(lines)-1} != measurements {n}"
        header = lines[0]
        for f in ("site_code", "point_code", "factor_code", "import_batch_id", "value"):
            assert f in header, f"导出缺字段 {f}"
        assert db.query(AuditLog).filter_by(action="export_measurements").count() >= 1, "未写 audit"
    finally:
        db.close()


# ============ 4.5 评价 stale 判定 ============
@needs_db
@needs_data
def test_evaluation_stale_detection():
    """brief 4.5: 数据变更(measurement count 变)后旧评价 is_stale。"""
    from app.db.session import SessionLocal
    from app.db.bootstrap import main as bootstrap
    from app.db.load_kb import main as load_kb
    from app.services.pipeline import run_import
    from app.services.evaluation_service import run_evaluation
    from app.services.versioning import current_site_data_version
    from app.models import EvaluationResult, Measurement
    bootstrap(); load_kb()
    db = SessionLocal()
    try:
        run_import(db, GEJIU, "yunnan_gejiu")
        ev = run_evaluation(db, 1)
        ev_dv = ev["data_version"]
        cur = current_site_data_version(db, 1)
        assert ev_dv == cur, "刚评价应与 current 一致(is_stale=false)"
        # 模拟数据变更: 删部分 measurements → count 变 → current version 变 → 旧评价 stale
        db.query(Measurement).filter_by(site_id=1).delete()
        db.commit()
        cur2 = current_site_data_version(db, 1)
        assert cur2 != cur, "数据变更后 current_data_version 应变"
        latest = (db.query(EvaluationResult).filter_by(site_id=1, eval_type="ssui")
                  .order_by(EvaluationResult.id.desc()).first())
        assert latest.data_version != cur2, "旧评价 data_version 应与新 current 不同(stale)"
    finally:
        db.close()


# ============ 4.8 地图 8 级风险 + 阈值 generic 兜底 ============
def test_risk_level_8_tiers():
    """brief 4.8: _risk 8 级枚举, 边界值正确。"""
    from app.api.map import _risk
    assert _risk(None) == "unknown"
    assert _risk(0.5) == "none"
    assert _risk(1) == "low"
    assert _risk(2.9) == "low"
    assert _risk(3) == "med1"
    assert _risk(10) == "med2"
    assert _risk(30) == "high"
    assert _risk(80) == "severe"
    assert _risk(200) == "extreme"


def test_select_threshold_generic_fallback():
    """brief 4.8: 非 pH 档规则进 generic, _select_threshold 无 pH 时取 min。"""
    from app.api.map import _select_threshold
    bands = [None, None, None, None]
    generic = [50.0, 30.0]  # 两条通用阈值
    assert _select_threshold(bands, None, generic) == 30.0  # min(最严苛)
    # 有 pH 档时优先 pH 档
    bands[2] = 60.0
    assert _select_threshold(bands, 2, generic) == 60.0
    # pH 档缺失时回退 generic
    assert _select_threshold(bands, 0, generic) == 30.0
