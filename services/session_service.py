from __future__ import annotations

"""会话与消息管理服务。"""

import logging
from typing import Optional

import sqlite3

from services import storage

logger = logging.getLogger(__name__)


def get_or_create_session(conn: sqlite3.Connection, name: str) -> int:
    logger.info("获取/创建会话: %s", name)
    return storage.ensure_session(conn, name)


def list_sessions(conn: sqlite3.Connection) -> list[dict]:
    return storage.list_sessions(conn)


def list_messages(conn: sqlite3.Connection, session_id: int, limit: int = 20) -> list[dict]:
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, role, content, created_at, related_doc_ids FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT ?",
        (session_id, limit),
    )
    rows = cursor.fetchall()
    return [dict(row) for row in rows][::-1]


def add_message(
    conn: sqlite3.Connection,
    session_id: int,
    role: str,
    content: str,
    related_doc_ids: Optional[list[str]] = None,
) -> int:
    logger.debug("写入消息，role=%s, session=%s", role, session_id)
    return storage.record_message(conn, session_id, role, content, related_doc_ids)
