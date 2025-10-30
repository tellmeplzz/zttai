from __future__ import annotations

"""模拟设备监控信号并推送异常事件。"""

import logging
import random
import sqlite3
from pathlib import Path
from typing import Iterable, Optional

from services import storage
from services import signal_service

logger = logging.getLogger(__name__)


class MonitorService:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def stream_signal(self, source: str = "data/signals/sample1.csv", threshold: float = 0.7) -> Iterable[dict]:
        times, values = signal_service.load_signal(source)
        for idx, value in enumerate(values):
            yield {"index": idx, "time": times[idx], "value": value, "flag": 1 if value >= threshold else 0}

    def enqueue_anomaly(
        self,
        sample_path: str,
        window_start: float,
        window_end: float,
        score: float,
    ) -> int:
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO hit_queue(sample_path, window_start, window_end, score, created_at) VALUES(?, ?, ?, ?, datetime('now'))",
            (sample_path, window_start, window_end, score),
        )
        self.conn.commit()
        logger.info("异常样本入队: %s", sample_path)
        return int(cursor.lastrowid)

    def run_mock_task(self, source: str = "data/signals/sample1.csv", threshold: float = 0.7) -> Optional[int]:
        """模拟扫描信号，一旦检测到异常立即入队。"""

        times, values = signal_service.load_signal(source)
        anomalies = signal_service.find_anomalies(values, threshold=threshold)
        if not anomalies:
            return None
        target_index = anomalies[0]
        sliced_times, sliced_values = signal_service.slice_window(times, values, target_index)
        output_dir = Path("data/thumbnails")
        output_dir.mkdir(parents=True, exist_ok=True)
        thumbnail_path = output_dir / f"thumb_{target_index}.png"
        signal_service.save_thumbnail(sliced_times, sliced_values, str(thumbnail_path))
        score = min(1.0, max(values[target_index], random.uniform(threshold, 1.0)))
        return self.enqueue_anomaly(
            sample_path=str(thumbnail_path),
            window_start=sliced_times[0],
            window_end=sliced_times[-1],
            score=score,
        )


__all__ = ["MonitorService"]
