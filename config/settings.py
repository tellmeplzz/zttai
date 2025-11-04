from __future__ import annotations

"""全局配置管理模块，负责读取 Streamlit secrets 或环境变量。"""

from dataclasses import dataclass
from functools import lru_cache
import os
from typing import Any, Dict

try:
    import streamlit as st
except Exception:  # pragma: no cover - Streamlit 不一定在测试中可用
    st = None  # type: ignore

try:  # pragma: no cover - 仅在运行期可用
    from streamlit.errors import StreamlitSecretNotFoundError
except Exception:  # pragma: no cover
    StreamlitSecretNotFoundError = Exception  # type: ignore[misc,assignment]


@dataclass
class LLMConfig:
    provider: str = "OLLAMA"
    model: str = "llama3"
    temperature: float = 0.1


@dataclass
class EmbeddingConfig:
    provider: str = "sentence-transformers"
    model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


@dataclass
class VectorStoreConfig:
    backend: str = "chromadb"
    persist_path: str = "data/vector_store"


@dataclass
class StorageConfig:
    sqlite_path: str = "data/ztt_agent.db"


@dataclass
class OcrConfig:
    use_gpu: bool = False
    fallback: str = "pytesseract"


@dataclass
class TTSConfig:
    provider: str = "pyttsx3"
    voice: str = "default"
    rate: int = 180


@dataclass
class AppConfig:
    llm: LLMConfig
    embedding: EmbeddingConfig
    vector_store: VectorStoreConfig
    storage: StorageConfig
    ocr: OcrConfig
    tts: TTSConfig
    extra: Dict[str, Any]


SECRET_KEYS = {
    "LLM_PROVIDER": "OLLAMA",
    "LLM_MODEL": "llama3",
    "LLM_TEMPERATURE": 0.1,
    "EMBEDDING_PROVIDER": "sentence-transformers",
    "EMBEDDING_MODEL": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    "VECTOR_BACKEND": "chromadb",
    "VECTOR_PATH": "data/vector_store",
    "SQLITE_PATH": "data/ztt_agent.db",
    "OCR_FALLBACK": "pytesseract",
    "TTS_PROVIDER": "pyttsx3",
    "TTS_VOICE": "default",
    "TTS_RATE": 180,
}


def _get_secret(key: str, default: Any) -> Any:
    if st is not None and hasattr(st, "secrets"):
        try:
            secrets_obj = st.secrets
            if key in secrets_obj:
                return secrets_obj[key]
        except StreamlitSecretNotFoundError:
            pass
        except Exception:  # pragma: no cover - 保护性容错
            pass
    return os.getenv(key, default)


@lru_cache()
def load_app_config() -> AppConfig:
    """加载应用配置，并缓存避免重复解析。"""

    secrets = {k: _get_secret(k, v) for k, v in SECRET_KEYS.items()}
    extra = {}
    if st is not None and hasattr(st, "secrets"):
        try:
            for key, value in st.secrets.items():
                if key not in secrets:
                    extra[key] = value
        except StreamlitSecretNotFoundError:
            pass
        except Exception:  # pragma: no cover
            pass

    llm = LLMConfig(
        provider=str(secrets["LLM_PROVIDER"]).upper(),
        model=str(secrets.get("LLM_MODEL", "llama3")),
        temperature=float(secrets.get("LLM_TEMPERATURE", 0.1)),
    )
    embedding = EmbeddingConfig(
        provider=str(secrets["EMBEDDING_PROVIDER"]),
        model=str(secrets["EMBEDDING_MODEL"]),
    )
    vector = VectorStoreConfig(
        backend=str(secrets["VECTOR_BACKEND"]).lower(),
        persist_path=str(secrets["VECTOR_PATH"]),
    )
    storage = StorageConfig(sqlite_path=str(secrets["SQLITE_PATH"]))
    ocr = OcrConfig(fallback=str(secrets["OCR_FALLBACK"]))
    tts = TTSConfig(
        provider=str(secrets["TTS_PROVIDER"]),
        voice=str(secrets["TTS_VOICE"]),
        rate=int(secrets["TTS_RATE"]),
    )
    return AppConfig(llm=llm, embedding=embedding, vector_store=vector, storage=storage, ocr=ocr, tts=tts, extra=extra)


__all__ = [
    "LLMConfig",
    "EmbeddingConfig",
    "VectorStoreConfig",
    "StorageConfig",
    "OcrConfig",
    "TTSConfig",
    "AppConfig",
    "load_app_config",
]
