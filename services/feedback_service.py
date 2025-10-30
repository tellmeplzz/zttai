from __future__ import annotations

"""用户反馈与问卷处理服务。"""

import logging
import sqlite3
from typing import Optional

from services import storage

logger = logging.getLogger(__name__)


def submit_feedback(
    conn: sqlite3.Connection,
    message_id: int,
    like: Optional[bool] = None,
    solved: Optional[bool] = None,
    note: str = "",
) -> None:
    logger.info(
        "记录反馈 message=%s like=%s solved=%s note=%s",
        message_id,
        like,
        solved,
        note,
    )
    storage.update_feedback(
        conn,
        message_id=message_id,
        like=int(like) if like is not None else None,
        solved=int(solved) if solved is not None else None,
        note=note,
    )
