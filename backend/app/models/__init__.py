"""核心数据模型 (对应 docs/architecture/database_schema.md)。

MVP 决策: 用 numeric 经纬度替代 PostGIS, 本地文件存储替代 MinIO。
检测数据采用长表 measurements。
"""
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


# ---------------- 权限与组织 ----------------
class Organization(Base, TimestampMixin):
    __tablename__ = "organizations"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    org_type: Mapped[str] = mapped_column(String(20))  # enterprise/agency/regulator/admin
    credit_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")


class User(Base, TimestampMixin):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(120))
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), nullable=True)
    email: Mapped[str | None] = mapped_column(String(120), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    roles = relationship("Role", secondary="user_roles", back_populates="users")


class Role(Base, TimestampMixin):
    __tablename__ = "roles"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    users = relationship("User", secondary="user_roles", back_populates="roles")
    permissions = relationship("Permission", secondary="role_permissions", back_populates="roles")


class Permission(Base, TimestampMixin):
    __tablename__ = "permissions"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(60), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    category: Mapped[str | None] = mapped_column(String(60), nullable=True)
    roles = relationship("Role", secondary="role_permissions", back_populates="permissions")


class UserRole(Base):
    __tablename__ = "user_roles"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), primary_key=True)


class RolePermission(Base):
    __tablename__ = "role_permissions"
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), primary_key=True)
    permission_id: Mapped[int] = mapped_column(ForeignKey("permissions.id"), primary_key=True)


# ---------------- 场地与检测 ----------------
class Site(Base, TimestampMixin):
    __tablename__ = "sites"
    id: Mapped[int] = mapped_column(primary_key=True)
    site_code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), nullable=True)
    pollution_type: Mapped[str | None] = mapped_column(String(20), nullable=True)  # heavy_metal/organic/composite
    land_use_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String(30), nullable=True)
    province: Mapped[str | None] = mapped_column(String(60), nullable=True)
    city: Mapped[str | None] = mapped_column(String(60), nullable=True)
    district: Mapped[str | None] = mapped_column(String(60), nullable=True)
    longitude: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)
    area: Mapped[float | None] = mapped_column(Float, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")


class SamplingPoint(Base, TimestampMixin):
    __tablename__ = "sampling_points"
    __table_args__ = (UniqueConstraint("site_id", "point_code", name="uq_site_point"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), index=True)
    point_code: Mapped[str] = mapped_column(String(50))
    longitude: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)
    depth_top_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    depth_bottom_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    soil_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    region: Mapped[str | None] = mapped_column(String(120), nullable=True)
    sampled_at: Mapped[date | None] = mapped_column(Date, nullable=True)


class FactorDictionary(Base, TimestampMixin):
    __tablename__ = "factor_dictionary"
    id: Mapped[int] = mapped_column(primary_key=True)
    factor_code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    factor_name: Mapped[str] = mapped_column(String(160))
    level1_category: Mapped[str | None] = mapped_column(String(40), nullable=True)
    factor_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    default_unit: Mapped[str | None] = mapped_column(String(30), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str | None] = mapped_column(String(120), nullable=True)


class ThresholdRule(Base, TimestampMixin):
    __tablename__ = "threshold_rules"
    id: Mapped[int] = mapped_column(primary_key=True)
    factor_id: Mapped[int] = mapped_column(ForeignKey("factor_dictionary.id"), index=True)
    application_scenario: Mapped[str | None] = mapped_column(String(120), nullable=True)
    applicable_scope: Mapped[str | None] = mapped_column(String(30), nullable=True)  # production/ecology
    land_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    threshold_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    threshold_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(30), nullable=True)
    threshold_original: Mapped[str | None] = mapped_column(Text, nullable=True)
    standard_source: Mapped[str | None] = mapped_column(String(200), nullable=True)
    version: Mapped[str] = mapped_column(String(20), default="V1.0")


class StandardThreshold(Base, TimestampMixin):
    __tablename__ = "standard_thresholds"
    __table_args__ = (
        UniqueConstraint("standard_code", "factor_name", "land_use_type",
                         "pH_condition", "exposure_scenario",
                         name="uq_standard_threshold_scope"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    factor_id: Mapped[int | None] = mapped_column(ForeignKey("factor_dictionary.id"), nullable=True, index=True)
    factor_name: Mapped[str] = mapped_column(String(160), index=True)
    land_use_type: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    standard_code: Mapped[str] = mapped_column(String(40), index=True)
    standard_name: Mapped[str] = mapped_column(String(220))
    screening_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    intervention_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    control_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(30), nullable=True)
    pH_condition: Mapped[str | None] = mapped_column(String(80), nullable=True)
    soil_condition: Mapped[str | None] = mapped_column(String(120), nullable=True)
    exposure_scenario: Mapped[str | None] = mapped_column(String(120), nullable=True)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    version: Mapped[str] = mapped_column(String(30), default="2018")
    source_reference: Mapped[str | None] = mapped_column(String(300), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class ImportBatch(Base, TimestampMixin):
    __tablename__ = "import_batches"
    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int | None] = mapped_column(ForeignKey("sites.id"), nullable=True, index=True)
    source_file: Mapped[str] = mapped_column(String(300))
    source_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)  # brief 4.2 内容指纹, 幂等判重键
    mapping_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)  # brief 4.2 映射指纹
    mapping_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    data_version: Mapped[str | None] = mapped_column(String(80), nullable=True)  # brief 4.2 本批次数据版本
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    valid_count: Mapped[int] = mapped_column(Integer, default=0)
    invalid_count: Mapped[int] = mapped_column(Integer, default=0)
    validation_report: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    script_version: Mapped[str | None] = mapped_column(String(30), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="success")
    imported_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class Measurement(Base, TimestampMixin):
    __tablename__ = "measurements"
    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), index=True)
    sampling_point_id: Mapped[int] = mapped_column(ForeignKey("sampling_points.id"), index=True)
    factor_id: Mapped[int] = mapped_column(ForeignKey("factor_dictionary.id"), index=True)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(30), nullable=True)
    method: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_below_detection: Mapped[bool] = mapped_column(Boolean, default=False)
    source_file: Mapped[str | None] = mapped_column(String(300), nullable=True)
    import_batch_id: Mapped[int | None] = mapped_column(ForeignKey("import_batches.id"), nullable=True, index=True)
    detected_at: Mapped[date | None] = mapped_column(Date, nullable=True)


# ---------------- 算法与评价 ----------------
class MLModel(Base, TimestampMixin):
    __tablename__ = "ml_models"
    id: Mapped[int] = mapped_column(primary_key=True)
    model_name: Mapped[str] = mapped_column(String(80))
    version: Mapped[str] = mapped_column(String(30))
    algorithm: Mapped[str | None] = mapped_column(String(40), nullable=True)
    feature_list: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    training_data_version: Mapped[str | None] = mapped_column(String(60), nullable=True)
    metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    artifact_path: Mapped[str | None] = mapped_column(String(300), nullable=True)
    trained_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DiagnosisResult(Base, TimestampMixin):
    __tablename__ = "diagnosis_results"
    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), index=True)
    model_id: Mapped[int | None] = mapped_column(ForeignKey("ml_models.id"), nullable=True)
    data_version: Mapped[str | None] = mapped_column(String(60), nullable=True)
    top_n: Mapped[int] = mapped_column(Integer, default=10)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    shap_global: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="done")


class DiagnosisFactorDetail(Base, TimestampMixin):
    __tablename__ = "diagnosis_factor_details"
    id: Mapped[int] = mapped_column(primary_key=True)
    diagnosis_id: Mapped[int] = mapped_column(ForeignKey("diagnosis_results.id"), index=True)
    factor_id: Mapped[int] = mapped_column(ForeignKey("factor_dictionary.id"))
    sampling_point_id: Mapped[int | None] = mapped_column(ForeignKey("sampling_points.id"), nullable=True)
    importance: Mapped[float | None] = mapped_column(Float, nullable=True)
    shap_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    direction: Mapped[str | None] = mapped_column(String(10), nullable=True)  # positive/negative
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)


class EvaluationResult(Base, TimestampMixin):
    __tablename__ = "evaluation_results"
    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), index=True)
    eval_type: Mapped[str] = mapped_column(String(30))  # reconstruction_prod/reconstruction_eco/ssui
    data_version: Mapped[str | None] = mapped_column(String(60), nullable=True)
    param_version: Mapped[str | None] = mapped_column(String(30), nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    grade: Mapped[str | None] = mapped_column(String(40), nullable=True)
    dimensions: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    weights: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    limiting_factors: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    risk_factors: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)


# ---------------- 推荐与技术库 ----------------
class TechnologyLibrary(Base, TimestampMixin):
    __tablename__ = "technology_library"
    id: Mapped[int] = mapped_column(primary_key=True)
    tech_name: Mapped[str] = mapped_column(String(150))
    applicable_pollutants: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    applicable_soil: Mapped[str | None] = mapped_column(Text, nullable=True)
    applicable_land_type: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    applicable_stage: Mapped[str | None] = mapped_column(String(60), nullable=True)
    advantages: Mapped[str | None] = mapped_column(Text, nullable=True)
    limitations: Mapped[str | None] = mapped_column(Text, nullable=True)
    cost_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    duration_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    secondary_risk: Mapped[str | None] = mapped_column(Text, nullable=True)
    forbidden_conditions: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str | None] = mapped_column(String(200), nullable=True)


class RemediationCase(Base, TimestampMixin):
    __tablename__ = "remediation_case_library"
    __table_args__ = (UniqueConstraint("case_id", name="uq_remediation_case_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[str] = mapped_column(String(80), index=True)
    site_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    region: Mapped[str | None] = mapped_column(String(120), nullable=True)
    land_use: Mapped[str | None] = mapped_column(String(80), nullable=True)
    pollution_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    pollutants: Mapped[str | None] = mapped_column(Text, nullable=True)
    concentration_range: Mapped[str | None] = mapped_column(Text, nullable=True)
    soil_conditions: Mapped[str | None] = mapped_column(Text, nullable=True)
    remediation_technology: Mapped[str] = mapped_column(String(180))
    technology_category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    duration: Mapped[str | None] = mapped_column(String(80), nullable=True)
    cost_level: Mapped[str | None] = mapped_column(String(30), nullable=True)
    effectiveness: Mapped[str | None] = mapped_column(Text, nullable=True)
    limitation: Mapped[str | None] = mapped_column(Text, nullable=True)
    secondary_risk: Mapped[str | None] = mapped_column(Text, nullable=True)
    post_remediation_function: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_source: Mapped[str | None] = mapped_column(String(240), nullable=True)
    doi: Mapped[str | None] = mapped_column(String(200), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class Recommendation(Base, TimestampMixin):
    __tablename__ = "recommendations"
    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), index=True)
    technology_id: Mapped[int] = mapped_column(ForeignKey("technology_library.id"))
    diagnosis_factor_id: Mapped[int | None] = mapped_column(ForeignKey("diagnosis_factor_details.id"), nullable=True)
    rule_version: Mapped[str | None] = mapped_column(String(30), nullable=True)
    match_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason_struct: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # brief 4.6 结构化推荐理由
    matched_factors: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # brief 4.6 命中障碍因子
    source: Mapped[str | None] = mapped_column(String(300), nullable=True)  # brief 4.6 法规/技术库来源
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)


# ---------------- 追溯与报告 ----------------
class WorkflowRecord(Base, TimestampMixin):
    __tablename__ = "workflow_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), index=True)
    stage: Mapped[str] = mapped_column(String(30))  # survey/approval/construction/effect/maintenance
    status: Mapped[str] = mapped_column(String(20), default="not_started")
    operator_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    operated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    data_source: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    is_returned: Mapped[bool] = mapped_column(Boolean, default=False)
    advanced_to_next: Mapped[bool] = mapped_column(Boolean, default=False)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class FileObject(Base, TimestampMixin):
    __tablename__ = "file_objects"
    id: Mapped[int] = mapped_column(primary_key=True)
    storage_key: Mapped[str] = mapped_column(String(400))
    original_name: Mapped[str] = mapped_column(String(300))
    content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), nullable=True)


class WorkflowAttachment(Base, TimestampMixin):
    __tablename__ = "workflow_attachments"
    id: Mapped[int] = mapped_column(primary_key=True)
    workflow_record_id: Mapped[int] = mapped_column(ForeignKey("workflow_records.id"), index=True)
    file_object_id: Mapped[int] = mapped_column(ForeignKey("file_objects.id"))
    file_role: Mapped[str | None] = mapped_column(String(60), nullable=True)


class ReportRecord(Base, TimestampMixin):
    __tablename__ = "report_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), index=True)
    report_type: Mapped[str] = mapped_column(String(40), default="traceability")
    version: Mapped[str] = mapped_column(String(20))
    data_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    template_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    file_object_id: Mapped[int | None] = mapped_column(ForeignKey("file_objects.id"), nullable=True)
    generated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# ---------------- 系统 ----------------
class AuditLog(Base, TimestampMixin):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(80))
    resource_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    resource_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result: Mapped[str] = mapped_column(String(20), default="success")
    ip: Mapped[str | None] = mapped_column(String(60), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(300), nullable=True)
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)


__all__ = [
    "Organization", "User", "Role", "Permission", "UserRole", "RolePermission",
    "Site", "SamplingPoint", "FactorDictionary", "ThresholdRule", "StandardThreshold",
    "ImportBatch", "Measurement",
    "MLModel", "DiagnosisResult", "DiagnosisFactorDetail", "EvaluationResult",
    "TechnologyLibrary", "RemediationCase", "Recommendation",
    "WorkflowRecord", "FileObject", "WorkflowAttachment", "ReportRecord", "AuditLog",
]
