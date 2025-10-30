from __future__ import annotations

"""TTS 播报服务，默认使用 pyttsx3，可切换 edge-tts。"""

import asyncio
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

try:  # pragma: no cover - 测试环境可能缺少依赖
    import edge_tts  # type: ignore
except Exception:  # pragma: no cover
    edge_tts = None  # type: ignore

try:  # pragma: no cover
    import pyttsx3  # type: ignore
except Exception:  # pragma: no cover
    pyttsx3 = None  # type: ignore


class TTSService:
    def __init__(self, provider: str = "pyttsx3", voice: str = "default", rate: int = 180) -> None:
        self.provider = provider.lower()
        self.voice = voice
        self.rate = rate
        self._engine = None
        if self.provider == "pyttsx3" and pyttsx3 is not None:
            self._engine = pyttsx3.init()
            if rate:
                self._engine.setProperty("rate", rate)
            if voice != "default":
                try:
                    self._engine.setProperty("voice", voice)
                except Exception:  # pragma: no cover
                    logger.warning("指定的本地语音不可用: %s", voice)

    async def synthesize(self, text: str, output_path: str = "data/tts_last.mp3") -> str:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        if self.provider == "edge-tts" and edge_tts is not None:
            communicate = edge_tts.Communicate(text, voice=self.voice or "zh-CN-XiaoxiaoNeural", rate="+0%")
            with open(output_path, "wb") as f:
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        f.write(chunk["data"])
            logger.info("edge-tts 音频生成完毕: %s", output_path)
        elif self.provider == "pyttsx3" and self._engine is not None:
            self._engine.save_to_file(text, output_path)
            self._engine.runAndWait()
            logger.info("pyttsx3 音频生成完毕: %s", output_path)
        else:
            logger.warning("未找到 TTS 引擎，将生成占位文本音频")
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(text)
        return output_path

    def synthesize_sync(self, text: str, output_path: str = "data/tts_last.mp3") -> str:
        return asyncio.get_event_loop().run_until_complete(self.synthesize(text, output_path))
