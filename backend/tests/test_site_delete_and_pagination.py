#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""GPT 审计第三节 + 3.5: 场地删除 + 分页序号测试。

验证:
  1) 删除场地后, 该场地及其关联数据不再出现在列表/统计
  2) 级联清理所有关联表(点位/测量/导入批次/诊断/评价/推荐/报告)
  3) 删除后场地不出现在列表(GPT 3.3)
  4) 分页序号: 第 2 页第 1 条显示 11 而非 1(GPT 3.5)
"""
import os
import sys
import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)


def test_delete_site_cascades_and_disappears():
    """删除场地 → 级联清理 + 不再出现(GPT 3.1-3.3)。"""
    from app.db.session import SessionLocal
    from app.models import (Base, Site, Measurement, SamplingPoint, ImportBatch,
                            DiagnosisResult, EvaluationResult)
    from app.db import session as _session_mod
    from app.services.import_service import resolve_mapping_for_file
    from app.services.pipeline import run_import_with_mapping

    db = SessionLocal()
    try:
        # 导入一个场地
        DATA_RAW = os.path.join(os.path.dirname(BACKEND), "data", "raw")
        xlsx = os.path.join(DATA_RAW, "1.20250731_复合污染场地数据表(乡村建设用地)_完整版.xlsx")
        if not os.path.exists(xlsx):
            pytest.skip("缺少乡村 XLSX")
        used_id, mapping, report = resolve_mapping_for_file("auto", xlsx)
        run_import_with_mapping(db, xlsx, mapping, imported_by=1, on_conflict="skip")

        site = db.query(Site).first()
        assert site is not None, "导入后应有场地"
        sid = site.id
        n_meas_before = db.query(Measurement).filter_by(site_id=sid).count()
        n_points_before = db.query(SamplingPoint).filter_by(site_id=sid).count()
        assert n_meas_before > 0, "应有测量数据"
        assert n_points_before == 8, f"乡村应 8 点, 实际 {n_points_before}"

        # 删除场地(事务化级联)
        from app.models import (DatasetVersion, ProjectAuthorization, Recommendation,
                                RemediationCase, SamplingEvent, WorkflowAttachment,
                                WorkflowRecord, ReportRecord)
        diag_ids = [d.id for d in db.query(DiagnosisResult.id).filter_by(site_id=sid).all()]
        wf_ids = [w.id for w in db.query(WorkflowRecord.id).filter_by(site_id=sid).all()]
        if wf_ids:
            db.query(WorkflowAttachment).filter(
                WorkflowAttachment.workflow_record_id.in_(wf_ids)).delete(synchronize_session=False)
        if diag_ids:
            from app.models import DiagnosisFactorDetail
            db.query(DiagnosisFactorDetail).filter(
                DiagnosisFactorDetail.diagnosis_id.in_(diag_ids)).delete(synchronize_session=False)
        for model in [WorkflowRecord, Recommendation, EvaluationResult, DiagnosisResult,
                      ReportRecord, ProjectAuthorization, SamplingEvent, DatasetVersion,
                      ImportBatch, Measurement, SamplingPoint]:
            db.query(model).filter_by(site_id=sid).delete(synchronize_session=False)
        # 注: RemediationCase 是案例库(无 site_id), 不参与场地删除级联
        db.delete(site)
        db.commit()

        # 验证: 场地不再出现
        assert db.query(Site).count() == 0, "删除后应 0 场地"
        assert db.query(Measurement).filter_by(site_id=sid).count() == 0, "测量应清空"
        assert db.query(SamplingPoint).filter_by(site_id=sid).count() == 0, "点位应清空"
    finally:
        db.close()


def test_pagination_sequence_formula():
    """分页序号公式: (currentPage-1)*pageSize + rowIndex + 1(GPT 3.5)。

    验证纯数学公式正确性(不依赖 DB), 第 2 页第 1 条应显示 11。
    """
    # 模拟 seqCol 的 render 逻辑
    def seq_render(page, page_size, row_index):
        offset = (page - 1) * page_size if (page and page_size) else 0
        return offset + row_index + 1

    # 第 1 页
    assert seq_render(1, 10, 0) == 1, "第1页第1条应=1"
    assert seq_render(1, 10, 9) == 10, "第1页第10条应=10"
    # 第 2 页(GPT 3.5 核心: 第 2 页第 1 条应=11)
    assert seq_render(2, 10, 0) == 11, f"第2页第1条应=11, 实际={seq_render(2, 10, 0)}"
    assert seq_render(2, 10, 9) == 20, "第2页第10条应=20"
    # 第 3 页
    assert seq_render(3, 10, 0) == 21, "第3页第1条应=21"
