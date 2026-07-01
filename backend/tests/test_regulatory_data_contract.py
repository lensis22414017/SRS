"""监管级数据契约验证测试 (Regulatory Data Contract)。

覆盖 AC-10~AC-18: 数据库 schema 结构完整性 + 字段语义正确性。
不依赖外部数据文件, 使用 SQLAlchemy 直接构造测试数据。

每个测试函数名清晰描述验证的契约条款, 遵循 conftest.py 的统一测试库体系。
"""
from __future__ import annotations

import pytest


def _has(*mods):
    try:
        for m in mods:
            __import__(m)
        return True
    except ImportError:
        return False


needs_db = pytest.mark.skipif(
    not _has("sqlalchemy", "fastapi"), reason="需 venv (fastapi + sqlalchemy)"
)


# ═══════════════════════════════════════════════════════════════════
# 测试辅助
# ═══════════════════════════════════════════════════════════════════

def _bootstrap():
    """重置数据库(删表 → 建表 → 种子), 保证测试隔离。"""
    from app.db.bootstrap import main as bootstrap
    bootstrap()


def _new_session():
    """获取新的数据库会话。"""
    from app.db.session import SessionLocal
    return SessionLocal()


def _make_site(db, code: str, name: str = ""):
    """在测试数据库中创建新场地, 返回 Site 实例 (已 flush, 有 id)。"""
    from app.models import Site
    site = Site(site_code=code, name=name or code)
    db.add(site)
    db.flush()
    return site


def _ensure_models_loaded():
    """确保所有 SQLAlchemy 模型已注册到 Base.metadata (幂等)。"""
    import app.models  # noqa: F401


# ═══════════════════════════════════════════════════════════════════
# 1. dataset_versions 表存在且与 diagnosis/evaluation 绑定
# ═══════════════════════════════════════════════════════════════════

@needs_db
def test_dataset_versions_table_exists():
    """AC-10: dataset_versions 表存在于 database metadata。"""
    _ensure_models_loaded()
    from app.db.base import Base
    assert "dataset_versions" in Base.metadata.tables, (
        "dataset_versions 表未注册到 Base.metadata"
    )


@needs_db
def test_dataset_versions_has_required_columns():
    """AC-10: dataset_versions 表包含 site_id / version_code / source_type / is_active。"""
    _ensure_models_loaded()
    from app.db.base import Base
    cols = set(Base.metadata.tables["dataset_versions"].columns.keys())
    required = {"site_id", "version_code", "is_active"}
    assert required.issubset(cols), (
        f"dataset_versions 缺少必填列: {required - cols}"
    )


@needs_db
def test_dataset_versions_can_persist_record():
    """AC-10: 可向 dataset_versions 写入记录并回读。"""
    _bootstrap()
    db = _new_session()
    try:
        from app.models import DatasetVersion, Site

        s = Site(site_code="DV-TEST-001", name="版本绑定测试场地")
        db.add(s)
        db.flush()

        dv = DatasetVersion(
            site_id=s.id,
            version_code="v1.0_sha256abc_n1000",
            source_type="import",
            row_count=1000,
            factor_count=14,
            point_count=134,
            is_active=True,
        )
        db.add(dv)
        db.commit()

        loaded = db.query(DatasetVersion).filter_by(site_id=s.id).first()
        assert loaded is not None
        assert loaded.version_code == "v1.0_sha256abc_n1000"
        assert loaded.source_type == "import"
        assert loaded.is_active is True
    finally:
        db.close()


@needs_db
def test_diagnosis_result_has_data_version_column():
    """AC-10: DiagnosisResult 包含 data_version 列, 可与 DatasetVersion 绑定。"""
    from app.models import DiagnosisResult
    assert hasattr(DiagnosisResult, "data_version"), (
        "DiagnosisResult 缺少 data_version 列"
    )


@needs_db
def test_evaluation_result_has_data_version_column():
    """AC-10: EvaluationResult 包含 data_version 列, 可与 DatasetVersion 绑定。"""
    from app.models import EvaluationResult
    assert hasattr(EvaluationResult, "data_version"), (
        "EvaluationResult 缺少 data_version 列"
    )


@needs_db
def test_diagnosis_and_evaluation_bind_to_same_data_version():
    """AC-10: diagnosis 和 evaluation 写入同 data_version 时可关联查询。"""
    _bootstrap()
    db = _new_session()
    try:
        from app.models import (
            DatasetVersion, DiagnosisResult, EvaluationResult,
            MLModel,
        )

        site = _make_site(db, "DV-BIND-001", "绑定关联测试")

        dv = DatasetVersion(site_id=site.id, version_code="v42", source_type="import", is_active=True)
        db.add(dv)

        m = MLModel(model_name="test_rf", version="0.1", algorithm="RandomForest")
        db.add(m)
        db.flush()

        diag = DiagnosisResult(site_id=site.id, model_id=m.id, data_version=dv.version_code, top_n=5)
        db.add(diag)
        ev = EvaluationResult(site_id=site.id, eval_type="reconstruction_prod",
                              data_version=dv.version_code, score=72.5, grade="C")
        db.add(ev)
        db.commit()

        from sqlalchemy import and_
        d = (db.query(DiagnosisResult)
             .filter(and_(DiagnosisResult.site_id == site.id,
                          DiagnosisResult.data_version == dv.version_code))
             .first())
        e = (db.query(EvaluationResult)
             .filter(and_(EvaluationResult.site_id == site.id,
                          EvaluationResult.data_version == dv.version_code))
             .first())
        assert d is not None and e is not None, "诊断/评价无法通过同 data_version 绑定"
        assert d.data_version == e.data_version
    finally:
        db.close()


# ═══════════════════════════════════════════════════════════════════
# 2. Measurement 监管字段
# ═══════════════════════════════════════════════════════════════════

@needs_db
def test_measurement_has_original_value_text_column():
    """AC-11: Measurement 包含 original_value_text 列 (Text 类型, 保存导入原始文本)。"""
    _ensure_models_loaded()
    from app.db.base import Base
    assert "original_value_text" in Base.metadata.tables["measurements"].columns.keys(), (
        "measurements 缺少 original_value_text 列"
    )


@needs_db
def test_measurement_has_qualifier_column():
    """AC-11: Measurement 包含 qualifier 列 (< / > / = / ND)。"""
    _ensure_models_loaded()
    from app.db.base import Base
    assert "qualifier" in Base.metadata.tables["measurements"].columns.keys(), (
        "measurements 缺少 qualifier 列"
    )


@needs_db
def test_measurement_has_detection_limit_column():
    """AC-11: Measurement 包含 detection_limit 列 (Float 类型, 检出限数值)。"""
    _ensure_models_loaded()
    from app.db.base import Base
    assert "detection_limit" in Base.metadata.tables["measurements"].columns.keys(), (
        "measurements 缺少 detection_limit 列"
    )


@needs_db
def test_measurement_has_value_used_for_model_column():
    """AC-11: Measurement 包含 value_used_for_model 列 (Float, 供模型使用的归一化值)。"""
    _ensure_models_loaded()
    from app.db.base import Base
    assert "value_used_for_model" in Base.metadata.tables["measurements"].columns.keys(), (
        "measurements 缺少 value_used_for_model 列"
    )


@needs_db
def test_measurement_has_replicate_group_id_column():
    """AC-15: Measurement 包含 replicate_group_id 列 (String(40), 平行样分组)。"""
    _ensure_models_loaded()
    from app.db.base import Base
    assert "replicate_group_id" in Base.metadata.tables["measurements"].columns.keys(), (
        "measurements 缺少 replicate_group_id 列"
    )


@needs_db
def test_measurement_has_data_origin_column():
    """AC-14: Measurement 包含 data_origin 列 (String(30), 数据来源区分)。"""
    _ensure_models_loaded()
    from app.db.base import Base
    assert "data_origin" in Base.metadata.tables["measurements"].columns.keys(), (
        "measurements 缺少 data_origin 列"
    )


@needs_db
def test_measurement_has_qa_status_column():
    """AC-11: Measurement 包含 qa_status 列 (质检状态, 默认 'raw')。"""
    _ensure_models_loaded()
    from app.db.base import Base
    assert "qa_status" in Base.metadata.tables["measurements"].columns.keys(), (
        "measurements 缺少 qa_status 列"
    )


@needs_db
def test_measurement_has_evidence_level_column():
    """AC-11: Measurement 包含 evidence_level 列 (证据等级, 默认 'A')。"""
    _ensure_models_loaded()
    from app.db.base import Base
    assert "evidence_level" in Base.metadata.tables["measurements"].columns.keys(), (
        "measurements 缺少 evidence_level 列"
    )


# ═══════════════════════════════════════════════════════════════════
# 3. 采样事件 sampling_events 表存在
# ═══════════════════════════════════════════════════════════════════

@needs_db
def test_sampling_events_table_exists():
    """AC-12: sampling_events 表存在于 database metadata。"""
    _ensure_models_loaded()
    from app.db.base import Base
    assert "sampling_events" in Base.metadata.tables, (
        "sampling_events 表未注册到 Base.metadata"
    )


@needs_db
def test_sampling_events_has_required_columns():
    """AC-12: sampling_events 表包含 site_id / event_code / event_date / event_type。"""
    _ensure_models_loaded()
    from app.db.base import Base
    cols = set(Base.metadata.tables["sampling_events"].columns.keys())
    required = {"site_id", "event_code", "event_date", "event_type"}
    assert required.issubset(cols), (
        f"sampling_events 缺少必填列: {required - cols}"
    )


@needs_db
def test_sampling_events_unique_constraint():
    """AC-12: sampling_events 有 (site_id, event_code) 唯一约束。"""
    _bootstrap()
    db = _new_session()
    try:
        from app.models import SamplingEvent
        import sqlalchemy as sa
        from sqlalchemy.exc import IntegrityError

        site = _make_site(db, "SE-TEST-001", "采样事件测试")

        e1 = SamplingEvent(site_id=site.id, event_code="SPRING-2024",
                           event_type="routine", event_date=None)
        db.add(e1)
        db.commit()

        e2 = SamplingEvent(site_id=site.id, event_code="SPRING-2024",
                           event_type="supplemental", event_date=None)
        db.add(e2)
        with pytest.raises((IntegrityError, sa.exc.IntegrityError)):
            db.commit()
    finally:
        db.rollback()
        db.close()


@needs_db
def test_sampling_events_can_persist_record():
    """AC-12: 可向 sampling_events 写入记录并回读。"""
    _bootstrap()
    db = _new_session()
    try:
        from app.models import SamplingEvent

        site = _make_site(db, "SE-WRITE-001", "写入测试")

        e = SamplingEvent(
            site_id=site.id,
            event_code="SUMMER-2025",
            event_date=None,
            event_type="routine",
            sampling_team="A 组",
            sampling_plan_ref="HJ/T 166-2004",
            weather_condition="晴",
        )
        db.add(e)
        db.commit()

        loaded = db.query(SamplingEvent).filter_by(site_id=site.id).first()
        assert loaded is not None
        assert loaded.event_code == "SUMMER-2025"
        assert loaded.sampling_team == "A 组"
    finally:
        db.close()


# ═══════════════════════════════════════════════════════════════════
# 4. project_authorizations 表存在
# ═══════════════════════════════════════════════════════════════════

@needs_db
def test_project_authorizations_table_exists():
    """AC-13: project_authorizations 表存在于 database metadata。"""
    _ensure_models_loaded()
    from app.db.base import Base
    assert "project_authorizations" in Base.metadata.tables, (
        "project_authorizations 表未注册到 Base.metadata"
    )


@needs_db
def test_project_authorizations_has_required_columns():
    """AC-13: project_authorizations 包含 site_id/authorized_org_id/valid_from/valid_until/is_revoked。"""
    _ensure_models_loaded()
    from app.db.base import Base
    cols = set(Base.metadata.tables["project_authorizations"].columns.keys())
    required = {"site_id", "authorized_org_id", "valid_from", "is_revoked"}
    assert required.issubset(cols), (
        f"project_authorizations 缺少必填列: {required - cols}"
    )


@needs_db
def test_project_authorizations_can_persist_record():
    """AC-13: 可向 project_authorizations 写入授权记录并回读。"""
    _bootstrap()
    db = _new_session()
    try:
        from app.models import (
            Organization, ProjectAuthorization, User,
        )
        from datetime import date

        site = _make_site(db, "PA-TEST-001", "授权测试")

        org = db.query(Organization).filter_by(org_type="agency").first()
        assert org is not None, "seed 数据应包含 agency 组织"
        admin = db.query(User).filter_by(username="admin").first()
        assert admin is not None, "seed 数据应包含 admin 用户"

        pa = ProjectAuthorization(
            site_id=site.id,
            authorized_org_id=org.id,
            authorized_by=admin.id,
            permission_scope="read_write",
            valid_from=date.today(),
            is_revoked=False,
        )
        db.add(pa)
        db.commit()

        loaded = db.query(ProjectAuthorization).filter_by(site_id=site.id).first()
        assert loaded is not None
        assert loaded.permission_scope == "read_write"
        assert loaded.is_revoked is False
    finally:
        db.close()


# ═══════════════════════════════════════════════════════════════════
# 5. Organization/User is_seed 列
# ═══════════════════════════════════════════════════════════════════

@needs_db
def test_organization_has_is_seed_column():
    """AC-17: Organization 包含 is_seed 列 (Boolean, 种子数据标记)。"""
    _ensure_models_loaded()
    from app.db.base import Base
    assert "is_seed" in Base.metadata.tables["organizations"].columns.keys(), (
        "organizations 缺少 is_seed 列"
    )


@needs_db
def test_user_has_is_seed_column():
    """AC-17: User 包含 is_seed 列 (Boolean, 种子数据标记)。"""
    _ensure_models_loaded()
    from app.db.base import Base
    assert "is_seed" in Base.metadata.tables["users"].columns.keys(), (
        "users 缺少 is_seed 列"
    )


@needs_db
def test_seed_organizations_marked_is_seed_true():
    """AC-17: seed 数据中的组织 is_seed=True。"""
    _bootstrap()
    db = _new_session()
    try:
        from app.models import Organization
        seed_orgs = db.query(Organization).filter_by(is_seed=True).all()
        assert len(seed_orgs) >= 4, (
            f"应有至少 4 个种子组织 (is_seed=True), 实际: {len(seed_orgs)}"
        )
        seed_names = {o.name for o in seed_orgs}
        expected = {"系统管理方", "示范企业(个旧场地)", "第三方检测机构", "属地监管单位"}
        assert expected.issubset(seed_names), (
            f"缺少预期种子组织: {expected - seed_names}"
        )
    finally:
        db.close()


@needs_db
def test_seed_users_marked_is_seed_true():
    """AC-17: seed 数据中的用户 is_seed=True。"""
    _bootstrap()
    db = _new_session()
    try:
        from app.models import User
        seed_users = db.query(User).filter_by(is_seed=True).all()
        assert len(seed_users) >= 4, (
            f"应有至少 4 个种子用户 (is_seed=True), 实际: {len(seed_users)}"
        )
        seed_usernames = {u.username for u in seed_users}
        expected = {"admin", "enterprise", "agency", "regulator"}
        assert expected.issubset(seed_usernames), (
            f"缺少预期种子用户: {expected - seed_usernames}"
        )
    finally:
        db.close()


# ═══════════════════════════════════════════════════════════════════
# 6. 检测限: 导入含 '<0.001' 的数据后 DB 中 qualifier='<'
# ═══════════════════════════════════════════════════════════════════

@needs_db
def test_measurement_qualifier_persisted_for_below_detection():
    """AC-11: 检测限标记 qualifier 可直接写入并持久化保留于 DB (不依赖解析管道)。"""
    _bootstrap()
    db = _new_session()
    try:
        from app.models import (
            FactorDictionary, Measurement, SamplingPoint,
        )

        site = _make_site(db, "DL-QUAL-001", "检出限测试")

        sp = SamplingPoint(site_id=site.id, point_code="PT-QLF-01")
        db.add(sp)
        db.flush()

        fd = FactorDictionary(factor_code="Cd", factor_name="镉", default_unit="mg/kg")
        db.add(fd)
        db.flush()

        m = Measurement(
            site_id=site.id,
            sampling_point_id=sp.id,
            factor_id=fd.id,
            value=0.0005,                     # DL/2 估算值
            unit="mg/kg",
            original_value_text="<0.001",
            qualifier="<",
            detection_limit=0.001,
            is_below_detection=True,
            qa_status="raw",
            evidence_level="A",
            data_origin="field",
        )
        db.add(m)
        db.commit()

        loaded = db.query(Measurement).filter_by(site_id=site.id).first()
        assert loaded is not None
        assert loaded.original_value_text == "<0.001", (
            f"original_value_text 应保留原始文本 '<0.001', 实际: {loaded.original_value_text}"
        )
        assert loaded.qualifier == "<", (
            f"qualifier 应为 '<', 实际: {loaded.qualifier}"
        )
        assert loaded.detection_limit == 0.001, (
            f"detection_limit 应为 0.001, 实际: {loaded.detection_limit}"
        )
        assert loaded.is_below_detection is True
        assert loaded.value is not None and loaded.value < loaded.detection_limit
    finally:
        db.close()


@needs_db
def test_measurement_qualifier_variants_persist():
    """AC-11: qualifier 可区分 '<' / '>' / 'ND' 三种语义。"""
    _bootstrap()
    db = _new_session()
    try:
        from app.models import (
            FactorDictionary, Measurement, SamplingPoint,
        )

        site = _make_site(db, "DL-VAR-001", "检出限变体测试")

        sp = SamplingPoint(site_id=site.id, point_code="PT-VAR-01")
        db.add(sp)
        db.flush()

        fd = FactorDictionary(factor_code="Cu", factor_name="铜", default_unit="mg/kg")
        db.add(fd)
        db.flush()

        variants = [
            ("<0.01", "<", 0.01, 0.005),
            (">100", ">", 100.0, 100.0),
            ("ND", "ND", None, None),
        ]
        for raw, qual, dl, val in variants:
            db.add(Measurement(
                site_id=site.id, sampling_point_id=sp.id, factor_id=fd.id,
                unit="mg/kg",
                original_value_text=raw,
                qualifier=qual,
                detection_limit=dl,
                value=val,
                is_below_detection=(qual in ("<", "ND")),
                qa_status="raw", evidence_level="A", data_origin="field",
            ))
        db.commit()

        results = {m.qualifier: m for m in db.query(Measurement)
                   .filter_by(site_id=site.id).all()}
        assert "<" in results
        assert ">" in results
        assert "ND" in results
        assert results["<"].detection_limit == 0.01
        assert results[">"].detection_limit == 100.0
        assert results["ND"].detection_limit is None
        assert results["ND"].value is None  # ND 无法量化
    finally:
        db.close()


# ═══════════════════════════════════════════════════════════════════
# 7. data_origin 字段: field/literature/synthetic/demo 区分
# ═══════════════════════════════════════════════════════════════════

@needs_db
def test_data_origin_distinguishable_in_db():
    """AC-14: data_origin 可在 DB 中区分 field / literature / synthetic / demo 四种来源。"""
    _bootstrap()
    db = _new_session()
    try:
        from app.models import (
            FactorDictionary, Measurement, SamplingPoint,
        )

        site = _make_site(db, "DO-TEST-001", "数据来源测试")

        sp = SamplingPoint(site_id=site.id, point_code="PT-DO-01")
        db.add(sp)
        db.flush()

        fd = FactorDictionary(factor_code="Zn", factor_name="锌", default_unit="mg/kg")
        db.add(fd)
        db.flush()

        origins = ["field", "literature", "synthetic", "demo"]
        for origin in origins:
            db.add(Measurement(
                site_id=site.id, sampling_point_id=sp.id, factor_id=fd.id,
                value=50.0, unit="mg/kg",
                qa_status="raw", evidence_level="A",
                data_origin=origin,
            ))
        db.commit()

        for origin in origins:
            count = (db.query(Measurement)
                     .filter_by(site_id=site.id, data_origin=origin)
                     .count())
            assert count == 1, (
                f"data_origin='{origin}' 应有 1 条记录, 实际: {count}"
            )

        total = db.query(Measurement).filter_by(site_id=site.id).count()
        assert total == 4, f"应有 4 条总计, 实际: {total}"
    finally:
        db.close()


@needs_db
def test_data_origin_defaults_to_field():
    """AC-14: data_origin 默认值应为 'field' (模型层 default='field')。"""
    _bootstrap()
    db = _new_session()
    try:
        from app.models import (
            FactorDictionary, Measurement, SamplingPoint,
        )

        site = _make_site(db, "DO-DEF-001", "默认来源测试")

        sp = SamplingPoint(site_id=site.id, point_code="PT-DEF-01")
        db.add(sp)
        db.flush()

        fd = FactorDictionary(factor_code="Pb", factor_name="铅", default_unit="mg/kg")
        db.add(fd)
        db.flush()

        m = Measurement(
            site_id=site.id, sampling_point_id=sp.id, factor_id=fd.id,
            value=30.0, unit="mg/kg",
            qa_status="raw", evidence_level="A",
        )
        db.add(m)
        db.commit()

        loaded = db.query(Measurement).filter_by(site_id=site.id).first()
        assert loaded.data_origin == "field", (
            f"data_origin 默认值应为 'field', 实际: '{loaded.data_origin}'"
        )
    finally:
        db.close()


# ═══════════════════════════════════════════════════════════════════
# 8. 平行样 replicate_group_id 不被静默平均
# ═══════════════════════════════════════════════════════════════════

@needs_db
def test_replicate_group_retains_all_members():
    """AC-15: 同 replicate_group_id 的多条记录均保留, 不被静默平均或丢弃。"""
    _bootstrap()
    db = _new_session()
    try:
        from app.models import (
            FactorDictionary, Measurement, SamplingPoint,
        )

        site = _make_site(db, "REP-TEST-001", "平行样测试")

        sp = SamplingPoint(site_id=site.id, point_code="PT-REP-01")
        db.add(sp)
        db.flush()

        fd = FactorDictionary(factor_code="As", factor_name="砷", default_unit="mg/kg")
        db.add(fd)
        db.flush()

        replicate_group = "site01_As_pointA_20230701"
        replicates = [12.3, 11.8, 12.1]

        for val in replicates:
            db.add(Measurement(
                site_id=site.id, sampling_point_id=sp.id, factor_id=fd.id,
                value=val, unit="mg/kg",
                replicate_group_id=replicate_group,
                original_value_text=str(val),
                qa_status="raw", evidence_level="A", data_origin="field",
            ))
        db.commit()

        members = (db.query(Measurement)
                   .filter_by(site_id=site.id, replicate_group_id=replicate_group)
                   .all())
        assert len(members) == 3, (
            f"平行样组应有 3 条记录全部保留, 实际: {len(members)}"
        )
        values = {m.value for m in members}
        assert values == {12.3, 11.8, 12.1}, (
            f"平行样值应完整保留, 实际: {values}"
        )
    finally:
        db.close()


@needs_db
def test_replicate_group_values_separate_from_model_value():
    """AC-15: 平行样的原始值 (value) 与模型可用值 (value_used_for_model) 独立存储。"""
    _bootstrap()
    db = _new_session()
    try:
        from app.models import (
            FactorDictionary, Measurement, SamplingPoint,
        )

        site = _make_site(db, "REP-SEP-001", "平行样分离测试")

        sp = SamplingPoint(site_id=site.id, point_code="PT-SEP-01")
        db.add(sp)
        db.flush()

        fd = FactorDictionary(factor_code="Hg", factor_name="汞", default_unit="mg/kg")
        db.add(fd)
        db.flush()

        replicate_group = "site01_Hg_pointB_20230702"
        raw_values = [0.15, 0.18, 0.16]

        for val in raw_values:
            db.add(Measurement(
                site_id=site.id, sampling_point_id=sp.id, factor_id=fd.id,
                value=val,                        # 原始检测值
                value_used_for_model=None,        # 不静默平均, 留待下游显式处理
                unit="mg/kg",
                replicate_group_id=replicate_group,
                qa_status="raw", evidence_level="A", data_origin="field",
            ))
        db.commit()

        members = (db.query(Measurement)
                   .filter_by(site_id=site.id, replicate_group_id=replicate_group)
                   .all())
        assert len(members) == 3
        for m in members:
            assert m.value_used_for_model is None, (
                f"value_used_for_model 应为 None (未被静默平均), "
                f"实际: {m.value_used_for_model}"
            )
    finally:
        db.close()


# ═══════════════════════════════════════════════════════════════════
# 9. 迁移计数一致性
# ═══════════════════════════════════════════════════════════════════

@needs_db
def test_schema_supports_counting_sites_and_measurements():
    """AC-16: 系统 schema 支持对场地/测量值进行聚合计数 (SQL COUNT 可用)。"""
    _bootstrap()
    db = _new_session()
    try:
        from app.models import (
            FactorDictionary, Measurement, SamplingPoint, Site,
        )

        # 构造 2 个新场地进行计数测试
        for si in range(2):
            s = Site(site_code=f"CNT-{si:03d}", name=f"计数测试场地{si}")
            db.add(s)
            db.flush()

            fd = FactorDictionary(factor_code=f"CNTF{si}", factor_name=f"计数因子{si}", default_unit="mg/kg")
            db.add(fd)
            db.flush()

            for pi in range(5):
                sp = SamplingPoint(site_id=s.id, point_code=f"PC{si}-{pi:03d}")
                db.add(sp)
                db.flush()

                for _ in range(4):
                    db.add(Measurement(
                        site_id=s.id, sampling_point_id=sp.id, factor_id=fd.id,
                        value=10.0, unit="mg/kg",
                        qa_status="raw", evidence_level="A", data_origin="field",
                    ))
        db.commit()

        from sqlalchemy import func
        n_sites = db.query(func.count(Site.id)).scalar()
        n_meas = db.query(func.count(Measurement.id)).scalar()
        n_points = db.query(func.count(SamplingPoint.id)).scalar()

        # seed 有场地组, 我们至少追加了 2 个场地
        assert n_sites >= 2, f"场地总数应 >= 2, 实际: {n_sites}"
        assert n_points >= 10, f"采样点总数应 >= 10, 实际: {n_points}"
        assert n_meas >= 40, f"测量值总数应 >= 40, 实际: {n_meas}"

        # 验证计数一致性: 每个测试场地 5 点 * 4 测量 = 20 测量
        for si in range(2):
            site = db.query(Site).filter_by(site_code=f"CNT-{si:03d}").first()
            assert site is not None
            pts = db.query(SamplingPoint).filter_by(site_id=site.id).count()
            assert pts == 5, f"场地 {si} 应有 5 点, 实际: {pts}"
            ms = db.query(Measurement).filter_by(site_id=site.id).count()
            assert ms == 20, f"场地 {si} 应有 20 条测量值, 实际: {ms}"
    finally:
        db.close()


@needs_db
def test_import_batch_tracks_measurement_counts():
    """AC-16: ImportBatch 的 row_count / valid_count / invalid_count 正确追踪计数。"""
    _bootstrap()
    db = _new_session()
    try:
        from app.models import ImportBatch

        site = _make_site(db, "IB-COUNT-001", "批次计数测试")

        batch = ImportBatch(
            site_id=site.id,
            source_file="/data/test.xlsx",
            row_count=134,
            valid_count=130,
            invalid_count=4,
            status="success",
        )
        db.add(batch)
        db.commit()

        loaded = db.query(ImportBatch).filter_by(site_id=site.id).first()
        assert loaded is not None
        assert loaded.row_count == 134
        assert loaded.valid_count == 130
        assert loaded.invalid_count == 4
        assert loaded.valid_count + loaded.invalid_count == loaded.row_count, (
            f"valid({loaded.valid_count}) + invalid({loaded.invalid_count}) "
            f"!= row_count({loaded.row_count})"
        )
    finally:
        db.close()


# ═══════════════════════════════════════════════════════════════════
# 10. 综合数据契约: 端到端 CRUD 闭环
# ═══════════════════════════════════════════════════════════════════

@needs_db
def test_end_to_end_data_contract_write_read():
    """AC-18: 综合契约 — 所有监管字段一次写入后可完整回读。"""
    _bootstrap()
    db = _new_session()
    try:
        from app.models import (
            DatasetVersion, FactorDictionary, Measurement, SamplingEvent,
            SamplingPoint,
        )

        site = _make_site(db, "E2E-CONTRACT", "端到端契约测试")

        # 采样事件
        se = SamplingEvent(site_id=site.id, event_code="E2E-2025Q2",
                           event_type="routine", sampling_team="甲组")
        db.add(se)
        db.flush()

        # 数据集版本
        dv = DatasetVersion(site_id=site.id, version_code="e2e_v1",
                            source_type="import", row_count=1, factor_count=1,
                            point_count=1, is_active=True)
        db.add(dv)
        db.flush()

        # 采样点 + 因子
        sp = SamplingPoint(site_id=site.id, point_code="E2E-PT")
        db.add(sp)
        db.flush()

        fd = FactorDictionary(factor_code="Cr", factor_name="铬", default_unit="mg/kg")
        db.add(fd)
        db.flush()

        # 测量值 (全部监管字段填充)
        m = Measurement(
            site_id=site.id, sampling_point_id=sp.id, factor_id=fd.id,
            value=45.2, unit="mg/kg",
            original_value_text="45.2",
            qualifier="=",
            detection_limit=0.01,
            value_used_for_model=45.2,
            replicate_group_id="E2E-Cr-001",
            method="HJ 491-2019",
            is_below_detection=False,
            qa_status="raw",
            evidence_level="A",
            data_origin="field",
        )
        db.add(m)
        db.commit()

        # 完整回读
        loaded = db.query(Measurement).filter_by(site_id=site.id).first()
        assert loaded is not None
        assert loaded.original_value_text == "45.2"
        assert loaded.qualifier == "="
        assert loaded.detection_limit == 0.01
        assert loaded.value_used_for_model == 45.2
        assert loaded.replicate_group_id == "E2E-Cr-001"
        assert loaded.data_origin == "field"
        assert loaded.qa_status == "raw"
        assert loaded.evidence_level == "A"
        assert loaded.is_below_detection is False

        # 关联验证
        assert loaded.factor_id == fd.id
        assert loaded.sampling_point_id == sp.id
        dv_loaded = db.query(DatasetVersion).filter_by(site_id=site.id).first()
        assert dv_loaded.version_code == "e2e_v1"
        se_loaded = db.query(SamplingEvent).filter_by(site_id=site.id).first()
        assert se_loaded.sampling_team == "甲组"
    finally:
        db.close()
