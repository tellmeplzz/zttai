from __future__ import annotations

"""LLM 提供方适配器。"""

import logging
from typing import Optional

from langchain.schema import BaseLanguageModel
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain.llms.base import LLM

logger = logging.getLogger(__name__)


class DemoLLM(LLM):
    """极简 LLM，离线时用于回退。"""

    def _call(self, prompt: str, stop: Optional[list[str]] = None) -> str:
        return "【离线应答】" + prompt.split("问题:")[-1].strip()

    @property
    def _identifying_params(self) -> dict:
        return {"name": "DemoLLM"}

    @property
    def _llm_type(self) -> str:
        return "demo"


def load_llm(provider: str, model: str, temperature: float = 0.1) -> BaseLanguageModel:
    provider = provider.upper()
    try:
        if provider == "OPENAI":
            from langchain_openai import ChatOpenAI  # type: ignore

            return ChatOpenAI(model=model, temperature=temperature)
        if provider == "DEEPSEEK":
            from langchain_openai import ChatOpenAI  # type: ignore

            return ChatOpenAI(model=model, temperature=temperature, base_url="https://api.deepseek.com/v1")
        if provider == "OLLAMA":
            from langchain_community.chat_models import ChatOllama  # type: ignore

            return ChatOllama(model=model, temperature=temperature)
    except Exception as exc:  # pragma: no cover
        logger.warning("加载真实 LLM 失败，切换至 DemoLLM: %s", exc)
    logger.info("使用 DemoLLM 作为回退模型")
    return DemoLLM()
