"""AI 助手 API。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.services.ai_service import chat
from app.services.audit_service import log

router = APIRouter(prefix=get_settings().api_v1_prefix + "/ai", tags=["ai"])


class ChatBody(BaseModel):
    message: str
    site_id: int | None = None
    history: list[dict] | None = None


@router.get("/status")
def ai_status(user: User = Depends(get_current_user)):
    s = get_settings()
    return {"configured": bool(s.ai_base_url and s.ai_api_key),
            "model": s.ai_model if s.ai_base_url else None}


@router.post("/chat")
def ai_chat(body: ChatBody, user: User = Depends(get_current_user),
            db: Session = Depends(get_db)):
    res = chat(db, body.message, site_id=body.site_id, history=body.history)
    log(db, action="ai_chat", user_id=user.id, resource_type="ai",
        detail={"site_id": body.site_id, "configured": res.get("configured")})
    return res
