from __future__ import annotations

"""SQLite 存储初始化与通用方法。"""

import json
import logging
import sqlite3
from pathlib import Path
from typing import Iterable, Optional

logger = logging.getLogger(__name__)


def get_connection(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    """确保给定数据表存在指定列。"""

    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table})")
    columns = {row["name"] for row in cursor.fetchall()}
    if column not in columns:
        logger.info("为数据表 %s 增加缺失字段 %s", table, column)
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        conn.commit()


def init_db(conn: sqlite3.Connection) -> None:
    logger.info("初始化 SQLite 数据表")
    cursor = conn.cursor()
    cursor.executescript(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            related_doc_ids TEXT,
            FOREIGN KEY(session_id) REFERENCES sessions(id)
        );
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER NOT NULL,
            "like" INTEGER,
            solved INTEGER,
            note TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(message_id) REFERENCES messages(id)
        );
        CREATE TABLE IF NOT EXISTS ocr_docs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            pages INTEGER,
            created_at TEXT NOT NULL,
            meta_json TEXT
        );
        CREATE TABLE IF NOT EXISTS annotations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sample_path TEXT NOT NULL,
            label TEXT,
            reasons TEXT,
            note TEXT,
            owner TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS hit_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sample_path TEXT NOT NULL,
            window_start REAL,
            window_end REAL,
            score REAL,
            created_at TEXT NOT NULL
        );
        """
    )
    conn.commit()
    # 表结构向后兼容升级
    ensure_column(conn, "hit_queue", "model_version", "TEXT")
    ensure_column(conn, "hit_queue", "predicted_label", "INTEGER DEFAULT 1")
    ensure_column(conn, "hit_queue", "status", "TEXT DEFAULT '待标注'")
    ensure_column(conn, "hit_queue", "raw_path", "TEXT")
    ensure_column(conn, "hit_queue", "payload_json", "TEXT")
    ensure_column(conn, "annotations", "status", "TEXT DEFAULT '待审核'")
    ensure_column(conn, "annotations", "reviewed_by", "TEXT")
    ensure_column(conn, "annotations", "reviewed_at", "TEXT")


def insert_json(cursor: sqlite3.Cursor, table: str, data: dict) -> int:
    placeholders = ", ".join(data.keys())
    marks = ", ".join([":" + key for key in data.keys()])
    query = f"INSERT INTO {table} ({placeholders}) VALUES ({marks})"
    cursor.execute(query, data)
    return int(cursor.lastrowid)


def fetch_all(cursor: sqlite3.Cursor, query: str, params: Optional[Iterable] = None) -> list[dict]:
    cursor.execute(query, params or [])
    rows = cursor.fetchall()
    return [dict(row) for row in rows]


def update_feedback(conn: sqlite3.Connection, message_id: int, like: Optional[int], solved: Optional[int], note: str) -> None:
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO feedback(message_id, \"like\", solved, note, created_at) VALUES (?, ?, ?, ?, datetime('now'))",
        (message_id, like, solved, note),
    )
    conn.commit()


def record_message(
    conn: sqlite3.Connection,
    session_id: int,
    role: str,
    content: str,
    related_doc_ids: Optional[list[str]] = None,
) -> int:
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO messages(session_id, role, content, created_at, related_doc_ids) VALUES (?, ?, ?, datetime('now'), ?)",
        (session_id, role, content, json.dumps(related_doc_ids or [])),
    )
    conn.commit()
    return int(cursor.lastrowid)


def ensure_session(conn: sqlite3.Connection, name: str) -> int:
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM sessions WHERE name = ?", (name,))
    row = cursor.fetchone()
    if row:
        return int(row["id"])
    cursor.execute(
        "INSERT INTO sessions(name, created_at) VALUES(?, datetime('now'))",
        (name,),
    )
    conn.commit()
    return int(cursor.lastrowid)


def list_sessions(conn: sqlite3.Connection) -> list[dict]:
    cursor = conn.cursor()
    return fetch_all(cursor, "SELECT id, name, created_at FROM sessions ORDER BY created_at DESC")
