from __future__ import annotations

"""输入意图识别与智能路由服务。"""

import logging
from typing import Literal

logger = logging.getLogger(__name__)

Intent = Literal["ocr", "ops", "annotation", "unknown"]


KEYWORDS = {
    "ocr": ["上传", "识别", "OCR", "文档", "索引"],
    "ops": ["运维", "故障", "问答", "排查", "维修"],
    "annotation": ["标注", "异常", "监控", "告警", "样本"],
}


def classify_intent(text: str) -> Intent:
    normalized = text.lower()
    for intent, keywords in KEYWORDS.items():
        for keyword in keywords:
            if keyword.lower() in normalized:
                logger.debug("规则命中意图: %s", intent)
                return intent  # type: ignore
    logger.info("未识别的指令: %s", text)
    return "unknown"
