from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.security import get_optional_user, require_permission
from app.services.ai_agent import get_agent_capabilities, run_ai_agent
from app.services.rag_engine import build_rag_index

router = APIRouter(prefix="/api/ai", tags=["AI Assistant & RAG"])


class ChatTurn(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., min_length=1, max_length=4000)


class AiChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    history: list[ChatTurn] = Field(default_factory=list)
    ma_cn: int | None = None


@router.get("/capabilities")
def ai_capabilities(user: dict[str, Any] | None = Depends(get_optional_user)):
    return get_agent_capabilities(user)


@router.post("/chat")
def ai_chat(payload: AiChatRequest, user: dict[str, Any] | None = Depends(get_optional_user)):
    history_dicts = [turn.model_dump() for turn in payload.history]
    return run_ai_agent(user, payload.message, history=history_dicts, ma_cn=payload.ma_cn)


@router.post("/reindex")
def ai_reindex(user: dict[str, Any] = Depends(require_permission("SYSTEM.ALL"))):
    index = build_rag_index(force=True)
    return {
        "status": "reindexed",
        "rag_chunks_count": len(index.get("docs", [])),
        "triggered_by": user.get("username"),
    }
