"""审计日志: 所有写操作统一记录。"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import AuditLog


def log(db: Session, action: str, user_id: int | None = None,
        resource_type: str | None = None, resource_id: int | None = None,
        result: str = "success", detail: dict | None = None,
        ip: str | None = None, user_agent: str | None = None,
        commit: bool = True) -> AuditLog:
    entry = AuditLog(user_id=user_id, action=action, resource_type=resource_type,
                     resource_id=resource_id, result=result, detail=detail,
                     ip=ip, user_agent=user_agent)
    db.add(entry)
    if commit:
        db.commit()
    return entry
