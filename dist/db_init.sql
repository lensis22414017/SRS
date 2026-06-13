-- ============================================================
-- SRS 数据库初始化脚本 v0.1.0
-- 污染场地土壤生态-生产功能重构监管系统
-- 目标: PostgreSQL 15+
-- 用法: psql -U <user> -d <dbname> -f db_init.sql
-- ============================================================

-- 1. 组织
CREATE TABLE IF NOT EXISTS organizations (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(200) NOT NULL,
    org_type        VARCHAR(20)  NOT NULL DEFAULT 'enterprise',
    credit_code     VARCHAR(50),
    status          VARCHAR(20)  NOT NULL DEFAULT 'active',
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ
);

-- 2. 用户
CREATE TABLE IF NOT EXISTS users (
    id              SERIAL PRIMARY KEY,
    username        VARCHAR(80)  NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,
    display_name    VARCHAR(120) NOT NULL,
    organization_id INTEGER      REFERENCES organizations(id),
    email           VARCHAR(120),
    phone           VARCHAR(40),
    status          VARCHAR(20)  NOT NULL DEFAULT 'active',
    last_login_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_users_username ON users(username);

-- 3. 角色
CREATE TABLE IF NOT EXISTS roles (
    id              SERIAL PRIMARY KEY,
    code            VARCHAR(40)  NOT NULL UNIQUE,
    name            VARCHAR(80)  NOT NULL,
    description     VARCHAR(255),
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ
);

-- 4. 权限
CREATE TABLE IF NOT EXISTS permissions (
    id              SERIAL PRIMARY KEY,
    code            VARCHAR(60)  NOT NULL UNIQUE,
    name            VARCHAR(120) NOT NULL,
    category        VARCHAR(60),
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ
);

-- 5. 用户-角色关联
CREATE TABLE IF NOT EXISTS user_roles (
    user_id         INTEGER NOT NULL REFERENCES users(id),
    role_id         INTEGER NOT NULL REFERENCES roles(id),
    PRIMARY KEY (user_id, role_id)
);

-- 6. 角色-权限关联
CREATE TABLE IF NOT EXISTS role_permissions (
    role_id         INTEGER NOT NULL REFERENCES roles(id),
    permission_id   INTEGER NOT NULL REFERENCES permissions(id),
    PRIMARY KEY (role_id, permission_id)
);

-- 7. 场地
CREATE TABLE IF NOT EXISTS sites (
    id              SERIAL PRIMARY KEY,
    site_code       VARCHAR(50)  NOT NULL UNIQUE,
    name            VARCHAR(200) NOT NULL,
    organization_id INTEGER      REFERENCES organizations(id),
    pollution_type  VARCHAR(20),
    land_use_type   VARCHAR(50),
    risk_level      VARCHAR(30),
    province        VARCHAR(60),
    city            VARCHAR(60),
    district        VARCHAR(60),
    longitude       NUMERIC(10,6),
    latitude        NUMERIC(10,6),
    area            DOUBLE PRECISION,
    description     TEXT,
    status          VARCHAR(20)  NOT NULL DEFAULT 'active',
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_sites_site_code ON sites(site_code);

-- 8. 采样点
CREATE TABLE IF NOT EXISTS sampling_points (
    id              SERIAL PRIMARY KEY,
    site_id         INTEGER      NOT NULL REFERENCES sites(id),
    point_code      VARCHAR(50)  NOT NULL,
    longitude       NUMERIC(10,6),
    latitude        NUMERIC(10,6),
    depth_top_cm    DOUBLE PRECISION,
    depth_bottom_cm DOUBLE PRECISION,
    soil_type       VARCHAR(80),
    region          VARCHAR(120),
    sampled_at      DATE,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ,
    UNIQUE (site_id, point_code)
);
CREATE INDEX IF NOT EXISTS ix_sampling_points_site_id ON sampling_points(site_id);

-- 9. 障碍因子字典
CREATE TABLE IF NOT EXISTS factor_dictionary (
    id              SERIAL PRIMARY KEY,
    factor_code     VARCHAR(80)  NOT NULL UNIQUE,
    factor_name     VARCHAR(160) NOT NULL,
    level1_category VARCHAR(40),
    factor_type     VARCHAR(30),
    default_unit    VARCHAR(30),
    description     TEXT,
    source          VARCHAR(120),
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_factor_dictionary_factor_code ON factor_dictionary(factor_code);

-- 10. 阈值规则
CREATE TABLE IF NOT EXISTS threshold_rules (
    id                  SERIAL PRIMARY KEY,
    factor_id           INTEGER NOT NULL REFERENCES factor_dictionary(id),
    application_scenario VARCHAR(120),
    applicable_scope    VARCHAR(30),
    land_type           VARCHAR(60),
    threshold_min       DOUBLE PRECISION,
    threshold_max       DOUBLE PRECISION,
    unit                VARCHAR(30),
    threshold_original  TEXT,
    standard_source     VARCHAR(200),
    version             VARCHAR(20) NOT NULL DEFAULT 'V1.0',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_threshold_rules_factor_id ON threshold_rules(factor_id);

-- 11. 标准阈值
CREATE TABLE IF NOT EXISTS standard_thresholds (
    id                  SERIAL PRIMARY KEY,
    factor_id           INTEGER REFERENCES factor_dictionary(id),
    factor_name         VARCHAR(160) NOT NULL,
    land_use_type       VARCHAR(80),
    standard_code       VARCHAR(40)  NOT NULL,
    standard_name       VARCHAR(220) NOT NULL,
    screening_value     DOUBLE PRECISION,
    intervention_value  DOUBLE PRECISION,
    control_value       DOUBLE PRECISION,
    unit                VARCHAR(30),
    ph_condition        VARCHAR(80),
    soil_condition      VARCHAR(120),
    exposure_scenario   VARCHAR(120),
    effective_date      DATE,
    version             VARCHAR(30)  NOT NULL DEFAULT '2018',
    source_reference    VARCHAR(300),
    notes               TEXT,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ,
    UNIQUE (standard_code, factor_name, land_use_type, ph_condition, exposure_scenario)
);
CREATE INDEX IF NOT EXISTS ix_standard_thresholds_factor_id   ON standard_thresholds(factor_id);
CREATE INDEX IF NOT EXISTS ix_standard_thresholds_factor_name ON standard_thresholds(factor_name);
CREATE INDEX IF NOT EXISTS ix_standard_thresholds_land_use    ON standard_thresholds(land_use_type);
CREATE INDEX IF NOT EXISTS ix_standard_thresholds_code        ON standard_thresholds(standard_code);

-- 12. 导入批次
CREATE TABLE IF NOT EXISTS import_batches (
    id              SERIAL PRIMARY KEY,
    site_id         INTEGER REFERENCES sites(id),
    source_file     VARCHAR(300) NOT NULL,
    mapping_snapshot JSONB,
    row_count       INTEGER      NOT NULL DEFAULT 0,
    valid_count     INTEGER      NOT NULL DEFAULT 0,
    invalid_count   INTEGER      NOT NULL DEFAULT 0,
    validation_report JSONB,
    script_version  VARCHAR(30),
    status          VARCHAR(20)  NOT NULL DEFAULT 'success',
    imported_by     INTEGER REFERENCES users(id),
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_import_batches_site_id ON import_batches(site_id);

-- 13. 检测数据 (长表)
CREATE TABLE IF NOT EXISTS measurements (
    id                SERIAL PRIMARY KEY,
    site_id           INTEGER NOT NULL REFERENCES sites(id),
    sampling_point_id INTEGER NOT NULL REFERENCES sampling_points(id),
    factor_id         INTEGER NOT NULL REFERENCES factor_dictionary(id),
    value             DOUBLE PRECISION,
    unit              VARCHAR(30),
    method            VARCHAR(120),
    is_below_detection BOOLEAN  NOT NULL DEFAULT FALSE,
    source_file       VARCHAR(300),
    import_batch_id   INTEGER REFERENCES import_batches(id),
    detected_at       DATE,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_measurements_site_id            ON measurements(site_id);
CREATE INDEX IF NOT EXISTS ix_measurements_sampling_point_id  ON measurements(sampling_point_id);
CREATE INDEX IF NOT EXISTS ix_measurements_factor_id          ON measurements(factor_id);
CREATE INDEX IF NOT EXISTS ix_measurements_import_batch_id    ON measurements(import_batch_id);

-- 14. ML 模型
CREATE TABLE IF NOT EXISTS ml_models (
    id                  SERIAL PRIMARY KEY,
    model_name          VARCHAR(80) NOT NULL,
    version             VARCHAR(30) NOT NULL,
    algorithm           VARCHAR(40),
    feature_list        JSONB,
    training_data_version VARCHAR(60),
    metrics             JSONB,
    artifact_path       VARCHAR(300),
    trained_at          TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ
);

-- 15. 诊断结果
CREATE TABLE IF NOT EXISTS diagnosis_results (
    id              SERIAL PRIMARY KEY,
    site_id         INTEGER NOT NULL REFERENCES sites(id),
    model_id        INTEGER REFERENCES ml_models(id),
    data_version    VARCHAR(60),
    top_n           INTEGER NOT NULL DEFAULT 10,
    summary         TEXT,
    shap_global     JSONB,
    status          VARCHAR(20) NOT NULL DEFAULT 'done',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_diagnosis_results_site_id ON diagnosis_results(site_id);

-- 16. 诊断因子明细
CREATE TABLE IF NOT EXISTS diagnosis_factor_details (
    id                SERIAL PRIMARY KEY,
    diagnosis_id      INTEGER NOT NULL REFERENCES diagnosis_results(id),
    factor_id         INTEGER NOT NULL REFERENCES factor_dictionary(id),
    sampling_point_id INTEGER REFERENCES sampling_points(id),
    importance        DOUBLE PRECISION,
    shap_value        DOUBLE PRECISION,
    direction         VARCHAR(10),
    rank              INTEGER,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_diagnosis_factor_details_diagnosis_id ON diagnosis_factor_details(diagnosis_id);

-- 17. 评价结果
CREATE TABLE IF NOT EXISTS evaluation_results (
    id              SERIAL PRIMARY KEY,
    site_id         INTEGER NOT NULL REFERENCES sites(id),
    eval_type       VARCHAR(30) NOT NULL,
    data_version    VARCHAR(60),
    param_version   VARCHAR(30),
    score           DOUBLE PRECISION,
    grade           VARCHAR(40),
    dimensions      JSONB,
    weights         JSONB,
    limiting_factors JSONB,
    risk_factors    JSONB,
    explanation     TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_evaluation_results_site_id ON evaluation_results(site_id);

-- 18. 技术库
CREATE TABLE IF NOT EXISTS technology_library (
    id                    SERIAL PRIMARY KEY,
    tech_name             VARCHAR(150) NOT NULL,
    applicable_pollutants  JSONB,
    applicable_soil       TEXT,
    applicable_land_type   JSONB,
    applicable_stage      VARCHAR(60),
    advantages            TEXT,
    limitations           TEXT,
    cost_level            VARCHAR(20),
    duration_level        VARCHAR(20),
    secondary_risk        TEXT,
    forbidden_conditions  TEXT,
    source                VARCHAR(200),
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ
);

-- 19. 修复案例库
CREATE TABLE IF NOT EXISTS remediation_case_library (
    id                      SERIAL PRIMARY KEY,
    case_id                 VARCHAR(80)  NOT NULL UNIQUE,
    site_type               VARCHAR(120),
    region                  VARCHAR(120),
    land_use                VARCHAR(80),
    pollution_type          VARCHAR(40),
    pollutants              TEXT,
    concentration_range     TEXT,
    soil_conditions         TEXT,
    remediation_technology  VARCHAR(180) NOT NULL,
    technology_category     VARCHAR(80),
    duration                VARCHAR(80),
    cost_level              VARCHAR(30),
    effectiveness           TEXT,
    limitation              TEXT,
    secondary_risk          TEXT,
    post_remediation_function TEXT,
    evidence_source         VARCHAR(240),
    doi                     VARCHAR(200),
    notes                   TEXT,
    created_at              TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_remediation_case_id ON remediation_case_library(case_id);

-- 20. 方案推荐
CREATE TABLE IF NOT EXISTS recommendations (
    id                   SERIAL PRIMARY KEY,
    site_id              INTEGER NOT NULL REFERENCES sites(id),
    technology_id        INTEGER NOT NULL REFERENCES technology_library(id),
    diagnosis_factor_id  INTEGER REFERENCES diagnosis_factor_details(id),
    rule_version         VARCHAR(30),
    match_score          DOUBLE PRECISION,
    reason               TEXT,
    rank                 INTEGER,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_recommendations_site_id ON recommendations(site_id);

-- 21. 五阶段追溯记录
CREATE TABLE IF NOT EXISTS workflow_records (
    id                  SERIAL PRIMARY KEY,
    site_id             INTEGER NOT NULL REFERENCES sites(id),
    stage               VARCHAR(30) NOT NULL,
    status              VARCHAR(20) NOT NULL DEFAULT 'not_started',
    operator_id         INTEGER REFERENCES users(id),
    operated_at         TIMESTAMPTZ,
    review_comment      TEXT,
    version             VARCHAR(20),
    data_source         VARCHAR(200),
    is_completed        BOOLEAN NOT NULL DEFAULT FALSE,
    is_returned         BOOLEAN NOT NULL DEFAULT FALSE,
    advanced_to_next    BOOLEAN NOT NULL DEFAULT FALSE,
    payload             JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_workflow_records_site_id ON workflow_records(site_id);

-- 22. 文件对象
CREATE TABLE IF NOT EXISTS file_objects (
    id              SERIAL PRIMARY KEY,
    storage_key     VARCHAR(400) NOT NULL,
    original_name   VARCHAR(300) NOT NULL,
    content_type    VARCHAR(120),
    size_bytes      INTEGER,
    sha256          VARCHAR(64),
    organization_id INTEGER REFERENCES organizations(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ
);

-- 23. 追溯附件关联
CREATE TABLE IF NOT EXISTS workflow_attachments (
    id                  SERIAL PRIMARY KEY,
    workflow_record_id  INTEGER NOT NULL REFERENCES workflow_records(id),
    file_object_id      INTEGER NOT NULL REFERENCES file_objects(id),
    file_role           VARCHAR(60),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_workflow_attachments_wf_id ON workflow_attachments(workflow_record_id);

-- 24. 报告记录
CREATE TABLE IF NOT EXISTS report_records (
    id              SERIAL PRIMARY KEY,
    site_id         INTEGER NOT NULL REFERENCES sites(id),
    report_type     VARCHAR(40) NOT NULL DEFAULT 'traceability',
    version         VARCHAR(20) NOT NULL,
    data_snapshot   JSONB,
    template_version VARCHAR(20),
    file_object_id  INTEGER REFERENCES file_objects(id),
    generated_by    INTEGER REFERENCES users(id),
    generated_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_report_records_site_id ON report_records(site_id);

-- 25. 操作日志
CREATE TABLE IF NOT EXISTS audit_logs (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER REFERENCES users(id),
    action          VARCHAR(80)  NOT NULL,
    resource_type   VARCHAR(60),
    resource_id     INTEGER,
    result          VARCHAR(20)  NOT NULL DEFAULT 'success',
    ip              VARCHAR(60),
    user_agent      VARCHAR(300),
    detail          JSONB,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_audit_logs_user_id ON audit_logs(user_id);

-- ============================================================
-- 种子数据: 4 种角色 + 14 项权限 + 4 个组织 + 4 个演示账号
-- 演示账号密码: Demo@2026 (bcrypt hash, 请用后端 seed 脚本生成真实 hash)
-- ============================================================

-- 组织
INSERT INTO organizations (name, org_type) VALUES
    ('系统管理方',       'admin'),
    ('示范企业A(个旧场地)', 'enterprise'),
    ('第三方检测机构B',    'agency'),
    ('属地监管单位C',     'regulator')
ON CONFLICT DO NOTHING;

-- 权限
INSERT INTO permissions (code, name, category) VALUES
    ('data:input',      '数据录入',   '数据'),
    ('data:query',      '数据查询',   '数据'),
    ('data:export',     '数据导出',   '数据'),
    ('data:archive',    '数据归档',   '数据'),
    ('report:generate', '报告生成',   '报告'),
    ('map:view',        '地图查看',   '数据'),
    ('workflow:view',   '全流程查看', '追溯'),
    ('file:download',   '文档下载',   '文件'),
    ('user:manage',     '用户管理',   '系统'),
    ('role:manage',     '角色管理',   '系统'),
    ('audit:view',      '日志审计',   '系统'),
    ('param:config',    '参数设置',   '系统'),
    ('model:manage',    '模型管理',   '算法'),
    ('tech:manage',     '技术库管理', '决策')
ON CONFLICT (code) DO NOTHING;

-- 角色
INSERT INTO roles (code, name, description) VALUES
    ('admin',      '系统管理员', '全功能访问'),
    ('enterprise', '企业用户',   '本企业数据录入/方案/流程上传'),
    ('agency',     '第三方机构', '授权项目检测/评估上传'),
    ('regulator',  '监管人员',   '监管范围内查看与追溯')
ON CONFLICT (code) DO NOTHING;

-- 角色-权限关联 (用子查询获取 id)
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.code = 'admin'
  AND p.code IN ('data:input','data:query','data:export','data:archive',
                 'report:generate','map:view','workflow:view','file:download',
                 'user:manage','role:manage','audit:view','param:config',
                 'model:manage','tech:manage')
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.code = 'enterprise'
  AND p.code IN ('data:input','data:query','data:export','report:generate',
                 'map:view','workflow:view','file:download')
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.code = 'agency'
  AND p.code IN ('data:input','data:query','workflow:view','file:download')
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.code = 'regulator'
  AND p.code IN ('data:query','map:view','workflow:view','file:download',
                 'report:generate','audit:view')
ON CONFLICT DO NOTHING;

-- 用户-角色关联 (演示账号密码需通过后端 seed_db.py 生成真实 bcrypt hash 后插入)
-- 此处仅提供角色绑定模板。实际执行: python backend/app/db/seed_db.py
INSERT INTO user_roles (user_id, role_id)
SELECT u.id, r.id FROM users u, roles r
WHERE u.username = 'admin'      AND r.code = 'admin'
ON CONFLICT DO NOTHING;

INSERT INTO user_roles (user_id, role_id)
SELECT u.id, r.id FROM users u, roles r
WHERE u.username = 'enterprise' AND r.code = 'enterprise'
ON CONFLICT DO NOTHING;

INSERT INTO user_roles (user_id, role_id)
SELECT u.id, r.id FROM users u, roles r
WHERE u.username = 'agency'     AND r.code = 'agency'
ON CONFLICT DO NOTHING;

INSERT INTO user_roles (user_id, role_id)
SELECT u.id, r.id FROM users u, roles r
WHERE u.username = 'regulator'  AND r.code = 'regulator'
ON CONFLICT DO NOTHING;
