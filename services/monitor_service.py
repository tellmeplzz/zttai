from __future__ import annotations

"""模拟设备监控信号并推送异常事件。"""

import csv
import json
import logging
import random
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional

from services import signal_service

logger = logging.getLogger(__name__)


class MonitorService:
    """围绕监控小模型输出的业务逻辑。"""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def stream_signal(
        self,
        source: str = "data/signals/sample1.csv",
        threshold: float = 0.7,
        model_version: str = "demo-small-v1",
    ) -> Iterable[dict]:
        """逐条产生小模型的预测输出。"""

        times, values = signal_service.load_signal(source)
        for idx, value in enumerate(values):
            probability = float(max(0.0, min(1.0, value)))
            flag = 1 if probability >= threshold else 0
            yield {
                "index": idx,
                "time": times[idx],
                "value": value,
                "probability": probability,
                "flag": flag,
                "model_version": model_version,
            }

    def _export_segment(
        self,
        times: List[float],
        values: List[float],
        target_index: int,
        model_version: str,
    ) -> dict:
        """生成缩略图与原始片段 CSV，返回路径信息。"""

        base_dir = Path("data/monitor_artifacts")
        thumb_dir = base_dir / "thumbnails"
        raw_dir = base_dir / "segments"
        thumb_dir.mkdir(parents=True, exist_ok=True)
        raw_dir.mkdir(parents=True, exist_ok=True)
        thumbnail_path = thumb_dir / f"thumb_{model_version}_{target_index}.png"
        raw_path = raw_dir / f"segment_{model_version}_{target_index}.csv"
        signal_service.save_thumbnail(times, values, str(thumbnail_path))
        with raw_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["time", "amplitude"])
            for t, v in zip(times, values):
                writer.writerow([f"{t:.4f}", f"{v:.6f}"])
        return {"thumbnail": str(thumbnail_path), "raw": str(raw_path)}

    def enqueue_anomaly(
        self,
        sample_path: str,
        window_start: float,
        window_end: float,
        score: float,
        model_version: str,
        payload: dict,
        raw_path: Optional[str] = None,
    ) -> int:
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO hit_queue(
                sample_path,
                window_start,
                window_end,
                score,
                created_at,
                model_version,
                predicted_label,
                status,
                raw_path,
                payload_json
            )
            VALUES(?, ?, ?, ?, datetime('now'), ?, 1, '待标注', ?, ?)
            """,
            (
                sample_path,
                window_start,
                window_end,
                score,
                model_version,
                raw_path,
                json.dumps(payload, ensure_ascii=False),
            ),
        )
        self.conn.commit()
        hit_id = int(cursor.lastrowid)
        logger.info("异常样本入队: %s | hit_id=%s", sample_path, hit_id)
        return hit_id

    def run_mock_task(
        self,
        source: str = "data/signals/sample1.csv",
        threshold: float = 0.7,
        model_version: str = "demo-small-v1",
    ) -> Optional[int]:
        """模拟扫描信号，一旦检测到异常立即入队。"""

        times, values = signal_service.load_signal(source)
        anomalies = signal_service.find_anomalies(values, threshold=threshold)
        if not anomalies:
            return None
        target_index = anomalies[0]
        sliced_times, sliced_values = signal_service.slice_window(times, values, target_index)
        paths = self._export_segment(sliced_times, sliced_values, target_index, model_version)
        score = min(1.0, max(values[target_index], random.uniform(threshold, 1.0)))
        payload = {
            "center_index": target_index,
            "center_time": times[target_index],
            "threshold": threshold,
            "probability": score,
            "source": source,
        }
        return self.enqueue_anomaly(
            sample_path=paths["thumbnail"],
            window_start=sliced_times[0],
            window_end=sliced_times[-1],
            score=score,
            model_version=model_version,
            payload=payload,
            raw_path=paths["raw"],
        )

    def record_stream_once(
        self,
        source: str = "data/signals/sample1.csv",
        threshold: float = 0.7,
        model_version: str = "demo-small-v1",
    ) -> Optional[int]:
        """遍历一遍信号流，返回首个入队的异常 ID。"""

        times, values = signal_service.load_signal(source)
        for event in self.stream_signal(source, threshold=threshold, model_version=model_version):
            if event["flag"] != 1:
                continue
            target_index = event["index"]
            sliced_times, sliced_values = signal_service.slice_window(times, values, target_index)
            paths = self._export_segment(sliced_times, sliced_values, target_index, model_version)
            payload = {
                "center_index": target_index,
                "center_time": event["time"],
                "threshold": threshold,
                "probability": event["probability"],
                "source": source,
            }
            return self.enqueue_anomaly(
                sample_path=paths["thumbnail"],
                window_start=sliced_times[0],
                window_end=sliced_times[-1],
                score=event["probability"],
                model_version=model_version,
                payload=payload,
                raw_path=paths["raw"],
            )
        return None

    def fetch_queue(self, status: Optional[List[str]] = None, limit: int = 50) -> List[dict]:
        cursor = self.conn.cursor()
        query = "SELECT * FROM hit_queue"
        params: List[object] = []
        if status:
            placeholders = ",".join(["?"] * len(status))
            query += f" WHERE status IN ({placeholders})"
            params.extend(status)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def update_hit_status(self, hit_id: int, status: str) -> None:
        cursor = self.conn.cursor()
        cursor.execute("UPDATE hit_queue SET status = ? WHERE id = ?", (status, hit_id))
        self.conn.commit()

    def save_annotation(
        self,
        hit_id: int,
        sample_path: str,
        label: str,
        reasons: List[str],
        note: str,
        owner: str,
        status: str,
        reviewer: Optional[str] = None,
    ) -> int:
        """Persist an annotation result and synchronize queue status."""
        cursor = self.conn.cursor()
        reviewed_at: Optional[str] = None
        if status != "待审核" and reviewer:
            reviewed_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            """
            INSERT INTO annotations(
                sample_path,
                label,
                reasons,
                note,
                owner,
                status,
                reviewed_by,
                reviewed_at,
                created_at
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (
                sample_path,
                label,
                ",".join(reasons),
                note,
                owner,
                status,
                reviewer,
                reviewed_at,
            ),
        )
        annotation_id = int(cursor.lastrowid)
        self.update_hit_status(hit_id, status)
        logger.info("样本 %s 标注完成，状态=%s", hit_id, status)
        return annotation_id


__all__ = ["MonitorService"]
