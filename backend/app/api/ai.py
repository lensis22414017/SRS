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
    from app.core.ai_config import connectivity_status, effective_ai
    cfg = effective_ai()
    conn = connectivity_status()
    has_config = cfg["configured"]
    connectivity_ok = conn["ok"] is True  # None(未测)/False 都不算"已连通"
    # brief 4.7 + 裴总 P0-2: 区分"已配置"与"已连通"; configured 旧字段保留兼容, UI 以 has_config/connectivity_ok 为准
    return {
        "has_config": has_config,
        "configured": has_config,  # 兼容旧前端
        "connectivity_ok": connectivity_ok,
        "connectivity_stale": conn["stale"],  # 缓存过期 → 前端提示重测
        "last_test_error": conn["error"],
        "last_checked": conn["last_checked"],
        "provider": cfg["provider"],
        "model": cfg["model"] if has_config else None,
        "source": cfg["source"],
        # 仅"已配置且连通"才算就绪; 未配置/未连通都走 RAG 降级提示
        "degraded_hint": not (has_config and connectivity_ok),
    }


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
