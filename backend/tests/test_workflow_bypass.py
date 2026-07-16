"""v1.0 P0-4: 工作流状态转移绕过测试。

验证:
1. not_started → completed 直接跳转被拒绝(即使 is_completed=True)
2. not_started → returned 直接跳转被拒绝(即使 is_returned=True)
3. returned → completed 直接跳转被拒绝
4. 合法路径 not_started→in_progress→completed 正常通过
"""
import pytest
from app.db.session import SessionLocal
from app.models import Site, WorkflowRecord
from app.services import workflow_service as W


@pytest.fixture
def db():
    db = SessionLocal()
    yield db
    db.rollback()
    db.close()


@pytest.fixture
def site_id(db):
    site_code = "__test_wf_bypass__"
    site = db.query(Site).filter_by(site_code=site_code).first()
    if not site:
        site = Site(site_code=site_code, name=site_code, province="测试")
        db.add(site)
        db.commit()
    # 初始化五阶段
    existing = db.query(WorkflowRecord).filter_by(site_id=site.id).first()
    if not existing:
        W.init_stages(db, site.id)
    else:
        # Reset all stages to not_started
        for rec in db.query(WorkflowRecord).filter_by(site_id=site.id).all():
            rec.status = "not_started"
            rec.is_completed = False
            rec.is_returned = False
            rec.advanced_to_next = False
        db.commit()
    return site.id


class TestWorkflowBypassBlocked:
    """P0-4: 绕过路径——全部必须被拒绝"""

    def test_direct_complete_rejected(self, db, site_id):
        """is_completed=True from not_started -> MUST FAIL"""
        with pytest.raises(ValueError, match="不允许"):
            W.update_stage(db, site_id, "survey", is_completed=True)

    def test_direct_returned_rejected(self, db, site_id):
        """is_returned=True from not_started -> MUST FAIL"""
        with pytest.raises(ValueError, match="不允许"):
            W.update_stage(db, site_id, "survey", is_returned=True)

    def test_returned_to_completed_rejected(self, db, site_id):
        """returned -> completed (via is_completed) -> MUST FAIL"""
        W.update_stage(db, site_id, "survey", status="in_progress")
        W.update_stage(db, site_id, "survey", status="returned", is_returned=True)
        with pytest.raises(ValueError, match="不允许"):
            W.update_stage(db, site_id, "survey", is_completed=True)

    def test_completed_to_returned_allowed(self, db, site_id):
        """completed -> returned: 审批退回场景, 需 is_returned=True + review_comment"""
        W.update_stage(db, site_id, "survey", status="in_progress")
        W.update_stage(db, site_id, "survey", status="completed", is_completed=True)
        stages = W.update_stage(db, site_id, "survey", is_returned=True,
                                review_comment="数据不合格需补充")
        s = [x for x in stages if x["stage"] == "survey"][0]
        assert s["status"] == "returned"
        assert s["is_returned"] is True


class TestWorkflowLegalPath:
    """合法路径: 确保正常流程不受修复影响"""

    def test_normal_flow_works(self, db, site_id):
        """not_started -> in_progress -> completed (via status param)"""
        stages1 = W.update_stage(db, site_id, "survey", status="in_progress")
        s1 = [s for s in stages1 if s["stage"] == "survey"][0]
        assert s1["status"] == "in_progress"

        stages2 = W.update_stage(db, site_id, "survey", status="completed",
                                 is_completed=True, review_comment="调查完成")
        s2 = [s for s in stages2 if s["stage"] == "survey"][0]
        assert s2["status"] == "completed"
        assert s2["is_completed"]

    def test_advance_chain_works(self, db, site_id):
        """正常五阶段推进: 依次完成 + advance"""
        for stage in W.STAGE_ORDER:
            W.update_stage(db, site_id, stage, status="in_progress")
            W.update_stage(db, site_id, stage, status="completed",
                           is_completed=True, review_comment=f"{stage} 完成")
            if stage != W.STAGE_ORDER[-1]:
                next_idx = W.STAGE_ORDER.index(stage) + 1
                W.update_stage(db, site_id, W.STAGE_ORDER[next_idx],
                               status="in_progress", advance=True)

        stages = W.get_stages(db, site_id)
        for s in stages:
            assert s["is_completed"], f"{s['stage']} should be completed"

    def test_reopen_completed_requires_reason(self, db, site_id):
        """completed → in_progress 必须填写原因"""
        W.update_stage(db, site_id, "survey", status="in_progress")
        W.update_stage(db, site_id, "survey", status="completed", is_completed=True)
        # 无 reason 应拒绝
        with pytest.raises(ValueError, match="审核意见"):
            W.update_stage(db, site_id, "survey", status="in_progress")
        # 有 reason 应通过
        stages = W.update_stage(db, site_id, "survey", status="in_progress",
                                review_comment="需要补充检测数据")
        s = [s for s in stages if s["stage"] == "survey"][0]
        assert s["status"] == "in_progress"
