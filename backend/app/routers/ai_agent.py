from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.security import get_current_user, get_optional_user, require_permission
from app.services.ai_agent import get_agent_capabilities, run_ai_agent
from app.services.ai_chat_history import (
    append_chat_exchange,
    clear_user_chat_history,
    get_recent_llm_history,
    get_user_chat_history,
)
from app.services.rag_engine import build_rag_index

router = APIRouter(prefix="/api/ai", tags=["AI Assistant & RAG"])


class ChatTurn(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., min_length=1, max_length=4000)


class AiChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    history: list[ChatTurn] | None = None
    ma_cn: int | None = None


@router.get("/capabilities")
def ai_capabilities(user: dict[str, Any] | None = Depends(get_optional_user)):
    return get_agent_capabilities(user)


@router.get("/history")
def ai_history(
    limit: int = Query(default=80, ge=1, le=200),
    user: dict[str, Any] = Depends(get_current_user),
):
    return {"items": get_user_chat_history(int(user["MaTK"]), limit=limit)}


@router.delete("/history")
def ai_clear_history(user: dict[str, Any] = Depends(get_current_user)):
    deleted = clear_user_chat_history(int(user["MaTK"]))
    return {"cleared": deleted}


@router.post("/chat")
def ai_chat(payload: AiChatRequest, user: dict[str, Any] | None = Depends(get_optional_user)):
    if payload.history is None:
        history_dicts = (
            get_recent_llm_history(int(user["MaTK"]), limit=6)
            if user and user.get("MaTK")
            else []
        )
    else:
        history_dicts = [turn.model_dump() for turn in payload.history]
    result = run_ai_agent(user, payload.message, history=history_dicts, ma_cn=payload.ma_cn)
    if user and user.get("MaTK"):
        append_chat_exchange(int(user["MaTK"]), payload.message, result)
    return result


@router.post("/reindex")
def ai_reindex(user: dict[str, Any] = Depends(require_permission("SYSTEM.ALL"))):
    index = build_rag_index(force=True)
    return {
        "status": "reindexed",
        "rag_chunks_count": len(index.get("docs", [])),
        "triggered_by": user.get("username"),
    }
