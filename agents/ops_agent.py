from __future__ import annotations

"""运维助手智能体。"""

import logging
import sqlite3
from typing import Dict, List

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.language_models import BaseLanguageModel

from services import rag_service, session_service

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE = """
你是专业的工业设备运维专家，请基于以下上下文回答用户问题。

【知识库片段】
{context}

【历史对话】
{history}

【格式要求】
1. 首句给出结论或建议。
2. 使用条列形式整理操作步骤。
3. 列出引用来源编号，格式如 [Doc-1]。

问题: {question}
"""


class OpsAgent:
    def __init__(
        self,
        llm: BaseLanguageModel,
        rag: rag_service.RagService,
        conn: sqlite3.Connection,
    ) -> None:
        self.llm = llm
        self.rag = rag
        self.conn = conn

    def build_context(self, docs: List) -> str:
        parts = []
        for idx, doc in enumerate(docs, start=1):
            metadata = doc.metadata or {}
            parts.append(
                f"[Doc-{idx}] 页面:{metadata.get('page', '?')} 分数:{metadata.get('score', 0):.3f} 内容:{doc.page_content[:200]}"
            )
        return "\n".join(parts) if parts else "未检索到相关文档，可根据经验回答。"

    def _load_history(self, session_id: int) -> str:
        messages = session_service.list_messages(self.conn, session_id, limit=10)
        history_lines = []
        for message in messages:
            prefix = "用户" if message["role"] == "user" else "助手"
            history_lines.append(f"{prefix}: {message['content']}")
        return "\n".join(history_lines[-6:])

    def invoke(
        self,
        session_id: int,
        question: str,
        top_k: int = 4,
        threshold: float = 0.4,
        carry_history: bool = True,
    ) -> Dict:
        docs = self.rag.retrieve(question, top_k=top_k, score_threshold=threshold)
        context = self.build_context(docs)
        history = self._load_history(session_id) if carry_history else ""
        prompt = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
        chain = prompt | self.llm
        response = chain.invoke({"context": context, "history": history, "question": question})
        answer = response.content if hasattr(response, "content") else str(response)
        doc_ids = [doc.metadata.get("source", "") for doc in docs]
        message_id = session_service.add_message(self.conn, session_id, "assistant", answer, doc_ids)
        return {
            "answer": answer,
            "documents": [
                {
                    "id": doc.metadata.get("source", ""),
                    "page": doc.metadata.get("page"),
                    "score": doc.metadata.get("score"),
                    "preview": doc.page_content[:200],
                }
                for doc in docs
            ],
            "message_id": message_id,
        }


__all__ = ["OpsAgent"]
