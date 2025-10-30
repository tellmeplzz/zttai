from __future__ import annotations

"""信号切片与缩略图生成。"""

import csv
import logging
from pathlib import Path
from typing import List, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

logger = logging.getLogger(__name__)


def load_signal(file_path: str) -> Tuple[List[float], List[float]]:
    times: List[float] = []
    values: List[float] = []
    with open(file_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            times.append(float(row["time"]))
            values.append(float(row["amplitude"]))
    return times, values


def slice_window(times: List[float], values: List[float], center_index: int, window: int = 5) -> Tuple[List[float], List[float]]:
    start = max(center_index - window, 0)
    end = min(center_index + window, len(times))
    return times[start:end], values[start:end]


def save_thumbnail(times: List[float], values: List[float], output_path: str) -> None:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(3, 2))
    plt.plot(times, values, color="#2f7bff", linewidth=2)
    plt.scatter(times, values, color="#ff6b6b")
    plt.xlabel("时间(s)")
    plt.ylabel("幅值")
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()


def find_anomalies(values: List[float], threshold: float = 0.7) -> List[int]:
    return [idx for idx, value in enumerate(values) if value >= threshold]
