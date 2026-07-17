"""v1.0.2: 数据备份与恢复 API(GPT 第九节 + 裴总决策: 本轮实现)。

端点:
  POST /api/v1/backup          创建备份(权限: system:backup)
  GET  /api/v1/backup/list     列出备份
  POST /api/v1/backup/restore  恢复备份(权限: system:backup + 二次确认)
  POST /api/v1/backup/verify   恢复演练
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import require_permission
from app.db.session import get_db
from app.models import User
from app.services.audit_service import log
from app.services.backup_service import create_backup, list_backups, restore_backup, verify_backup

router = APIRouter(prefix="/api/v1", tags=["backup"])


class BackupCreateReq(BaseModel):
    label: str = "manual"


class BackupRestoreReq(BaseModel):
    backup_path: str
    confirm: bool = False  # 必须显式确认


class BackupVerifyReq(BaseModel):
    backup_path: str


@router.post("/backup")
def api_create_backup(req: BackupCreateReq,
                      user: User = Depends(require_permission("system:backup")),
                      db: Session = Depends(get_db)):
    """创建数据库备份(AES 加密 + SHA256 校验)。"""
    try:
        result = create_backup(label=req.label)
        log(db, action="create_backup", user_id=user.id,
            resource_type="backup", detail=result)
        db.commit()
        return {"ok": True, **result}
    except Exception as e:
        raise HTTPException(500, f"备份失败: {e}")


@router.get("/backup/list")
def api_list_backups(user: User = Depends(require_permission("system:backup"))):
    """列出所有备份。"""
    return {"backups": list_backups()}


@router.post("/backup/restore")
def api_restore_backup(req: BackupRestoreReq,
                       user: User = Depends(require_permission("system:backup")),
                       db: Session = Depends(get_db)):
    """从备份恢复数据库(需二次确认)。"""
    if not req.confirm:
        raise HTTPException(400, "恢复操作必须 confirm=True(防止误操作)")
    try:
        result = restore_backup(req.backup_path, confirm=True)
        log(db, action="restore_backup", user_id=user.id,
            resource_type="backup", detail=result)
        db.commit()
        return {"ok": True, **result}
    except Exception as e:
        raise HTTPException(500, f"恢复失败: {e}")


@router.post("/backup/verify")
def api_verify_backup(req: BackupVerifyReq,
                      user: User = Depends(require_permission("system:backup"))):
    """恢复演练: 验证备份可恢复(不覆盖生产库)。"""
    try:
        result = verify_backup(req.backup_path)
        return {"ok": True, **result}
    except Exception as e:
        raise HTTPException(500, f"验证失败: {e}")
