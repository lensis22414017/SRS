#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""清空所有业务数据, 保留参考数据 (GPT 审计 1.1 + 裴总决策: 全部清空用甲方数据)。

参考数据(保留): Organization, Role, Permission, RolePermission, User, UserRole,
                SystemConfig, TechnologyLibrary, FactorDictionary, StandardThreshold,
                ThresholdRule, MLModel
业务数据(清空): Site, SamplingPoint, Measurement, ImportBatch, DatasetVersion,
                SamplingEvent, ProjectAuthorization, DiagnosisResult, DiagnosisFactorDetail,
                EvaluationResult, Recommendation, WorkflowRecord, ReportRecord, AuditLog

用法:
    cd backend
    DATABASE_URL=sqlite:///./srs_dev.db python ../scripts/clear_all_sites.py
"""
import os
import sys

# 加入 backend 到 path
BACKEND = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend")
sys.path.insert(0, BACKEND)

from app.db.session import SessionLocal, engine
from app.db.init_db import create_all


def clear_business_data():
    """清空所有业务数据, 保留参考数据。"""
    from app.models import (
        Site, SamplingPoint, Measurement, ImportBatch, DatasetVersion,
        SamplingEvent, ProjectAuthorization, DiagnosisResult, DiagnosisFactorDetail,
        EvaluationResult, Recommendation, WorkflowRecord, ReportRecord, AuditLog,
    )
    # 按外键依赖顺序删除(子表先, 父表后)
    tables_to_clear = [
        ("AuditLog", AuditLog),
        ("ReportRecord", ReportRecord),
        ("WorkflowRecord", WorkflowRecord),
        ("Recommendation", Recommendation),
        ("EvaluationResult", EvaluationResult),
        ("DiagnosisFactorDetail", DiagnosisFactorDetail),
        ("DiagnosisResult", DiagnosisResult),
        ("ProjectAuthorization", ProjectAuthorization),
        ("SamplingEvent", SamplingEvent),
        ("DatasetVersion", DatasetVersion),
        ("ImportBatch", ImportBatch),
        ("Measurement", Measurement),
        ("SamplingPoint", SamplingPoint),
        ("Site", Site),
    ]
    db = SessionLocal()
    try:
        print("=" * 60)
        print("清空业务数据(保留参考数据)")
        print("=" * 60)
        for name, model in tables_to_clear:
            try:
                n = db.query(model).count()
                if n > 0:
                    db.query(model).delete()
                    print(f"  清空 {name}: {n} 条")
                else:
                    print(f"  {name}: 已空")
            except Exception as e:
                print(f"  跳过 {name}: {e}")
        db.commit()
        print("=" * 60)
        # 验证
        print("清空后业务表计数:")
        for name, model in tables_to_clear:
            try:
                print(f"  {name}: {db.query(model).count()}")
            except Exception:
                pass
    finally:
        db.close()


if __name__ == "__main__":
    # 确保表存在
    create_all()
    clear_business_data()
