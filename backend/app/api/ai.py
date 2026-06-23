"""AI 助手 API。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import assert_site_access, get_current_user
from app.db.session import get_db
from app.models import Site, User
from app.services.ai_service import chat
from app.services.audit_service import log

router = APIRouter(prefix=get_settings().api_v1_prefix + "/ai", tags=["ai"])


class ChatBody(BaseModel):
    message: str
    site_id: int | None = None
    history: list[dict] | None = None


@router.get("/status")
def ai_status(user: User = Depends(get_current_user)):
    from app.core.ai_config import effective_ai
    cfg = effective_ai()
    return {"configured": cfg["configured"],
            "model": cfg["model"] if cfg["configured"] else None,
            "source": cfg["source"],
            "degraded_hint": not cfg["configured"]}  # brief 4.7: 未配置→将走 RAG 降级, 前端提示


@router.post("/chat")
def ai_chat(body: ChatBody, user: User = Depends(get_current_user),
            db: Session = Depends(get_db)):
    if body.site_id is not None:
        site = db.get(Site, body.site_id)
        if not site:
            from fastapi import HTTPException
            raise HTTPException(404, "场地不存在")
        assert_site_access(db, user, site)
    res = chat(db, body.message, site_id=body.site_id, history=body.history)
    log(db, action="ai_chat", user_id=user.id, resource_type="ai",
        detail={"site_id": body.site_id, "configured": res.get("configured")})
    return res
