import json
from typing import Any

from ..db import fetch_all, get_cursor

_TABLE_READY = False

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS AI_CHAT_LICH_SU (
    MaChat BIGINT AUTO_INCREMENT PRIMARY KEY,
    MaTK BIGINT NOT NULL,
    VaiTro ENUM('user', 'assistant') NOT NULL,
    NoiDung MEDIUMTEXT NOT NULL,
    CheDo VARCHAR(40) NULL,
    DongCo VARCHAR(40) NULL,
    DuLieuKemJson JSON NULL,
    ThoiGianTao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX IDX_AI_CHAT_TK_CHAT (MaTK, MaChat),
    CONSTRAINT FK_AI_CHAT_TK FOREIGN KEY (MaTK) REFERENCES TAI_KHOAN(MaTK) ON DELETE CASCADE
) ENGINE=InnoDB
"""


def ensure_ai_chat_table() -> None:
    """Idempotently ensure the AI_CHAT_LICH_SU persistence table exists."""
    global _TABLE_READY
    if _TABLE_READY:
        return
    with get_cursor(autocommit=True) as cur:
        cur.execute(_CREATE_TABLE_SQL)
    _TABLE_READY = True


def _deserialize_meta(raw: Any) -> dict[str, Any]:
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, (str, bytes)):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def get_user_chat_history(ma_tk: int, limit: int = 80) -> list[dict[str, Any]]:
    """Return chronological chat turns saved for the given account (MaTK)."""
    ensure_ai_chat_table()
    safe_limit = max(1, min(int(limit), 200))
    rows = fetch_all(
        """
        SELECT MaChat, VaiTro, NoiDung, CheDo, DongCo, DuLieuKemJson, ThoiGianTao
        FROM AI_CHAT_LICH_SU
        WHERE MaTK = %s
        ORDER BY MaChat DESC
        LIMIT %s
        """,
        (int(ma_tk), safe_limit),
    )
    items: list[dict[str, Any]] = []
    for row in reversed(rows):
        meta = _deserialize_meta(row.get("DuLieuKemJson"))
        items.append(
            {
                "id": int(row["MaChat"]),
                "role": row["VaiTro"],
                "content": row["NoiDung"],
                "mode": row.get("CheDo"),
                "engine": row.get("DongCo"),
                "citations": meta.get("citations") or [],
                "tool_traces": meta.get("tool_traces") or [],
                "sql_preview": meta.get("sql_preview"),
                "suggested_action": meta.get("suggested_action"),
                "created_at": row["ThoiGianTao"].isoformat() if row.get("ThoiGianTao") else None,
            }
        )
    return items


def get_recent_llm_history(ma_tk: int, limit: int = 6) -> list[dict[str, str]]:
    """Return compact recent {role, content} turns from DB for multi-turn context."""
    items = get_user_chat_history(ma_tk, limit=limit)
    return [{"role": item["role"], "content": item["content"]} for item in items]


def append_chat_exchange(
    ma_tk: int,
    user_message: str,
    assistant_result: dict[str, Any],
) -> None:
    """Persist a user prompt and its assistant reply atomically for MaTK."""
    ensure_ai_chat_table()
    compact_citations = [
        {
            "id": c.get("id"),
            "source": c.get("source"),
            "title": c.get("title"),
            "category": c.get("category"),
            "ma_cn": c.get("ma_cn"),
        }
        for c in (assistant_result.get("citations") or [])[:5]
    ]
    meta_payload = {
        "citations": compact_citations,
        "tool_traces": assistant_result.get("tool_traces") or [],
        "sql_preview": assistant_result.get("sql_preview"),
        "suggested_action": assistant_result.get("suggested_action"),
    }
    meta_json = json.dumps(meta_payload, ensure_ascii=False, default=str)

    with get_cursor(autocommit=False) as cur:
        cur.execute(
            """
            INSERT INTO AI_CHAT_LICH_SU (MaTK, VaiTro, NoiDung, CheDo, DongCo, DuLieuKemJson)
            VALUES (%s, 'user', %s, %s, NULL, NULL)
            """,
            (int(ma_tk), user_message, assistant_result.get("mode")),
        )
        cur.execute(
            """
            INSERT INTO AI_CHAT_LICH_SU (MaTK, VaiTro, NoiDung, CheDo, DongCo, DuLieuKemJson)
            VALUES (%s, 'assistant', %s, %s, %s, %s)
            """,
            (
                int(ma_tk),
                str(assistant_result.get("reply") or ""),
                assistant_result.get("mode"),
                assistant_result.get("engine"),
                meta_json,
            ),
        )


def clear_user_chat_history(ma_tk: int) -> int:
    """Delete all saved chat messages belonging to MaTK and return deleted row count."""
    ensure_ai_chat_table()
    with get_cursor(autocommit=True) as cur:
        cur.execute("DELETE FROM AI_CHAT_LICH_SU WHERE MaTK = %s", (int(ma_tk),))
        return int(cur.rowcount or 0)
