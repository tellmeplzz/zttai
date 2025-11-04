from __future__ import annotations

"""RAG 服务：文档切块、嵌入、向量检索。"""

import logging
from pathlib import Path
from typing import List, Optional

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config.settings import EmbeddingConfig, VectorStoreConfig

logger = logging.getLogger(__name__)


class RagService:
    def __init__(
        self,
        vector_config: VectorStoreConfig,
        embedding_config: EmbeddingConfig,
    ) -> None:
        self.vector_config = vector_config
        self.embedding_config = embedding_config
        self._embeddings: Optional[Embeddings] = None
        Path(vector_config.persist_path).mkdir(parents=True, exist_ok=True)

    @property
    def embeddings(self) -> Embeddings:
        if self._embeddings is None:
            if self.embedding_config.provider == "sentence-transformers":
                try:
                    logger.info("加载本地嵌入模型: %s", self.embedding_config.model)
                    self._embeddings = HuggingFaceEmbeddings(model_name=self.embedding_config.model)
                except Exception as exc:  # pragma: no cover
                    logger.warning("嵌入模型加载失败，启用简单哈希向量: %s", exc)
                    from langchain_community.embeddings import FakeEmbeddings  # type: ignore

                    self._embeddings = FakeEmbeddings(size=768)
            elif self.embedding_config.provider == "fake":
                from langchain_community.embeddings import FakeEmbeddings  # type: ignore

                logger.info("使用 FakeEmbeddings 作为轻量嵌入实现")
                self._embeddings = FakeEmbeddings(size=256)
            else:
                raise ValueError("暂不支持的嵌入模型提供方")
        return self._embeddings

    def load_vector_store(self) -> Chroma:
        return Chroma(
            collection_name="ztt_docs",
            embedding_function=self.embeddings,
            persist_directory=self.vector_config.persist_path,
        )

    def index_documents(self, doc_id: str, texts: List[str], metadatas: List[dict]) -> None:
        logger.info("索引文档 doc_id=%s, blocks=%s", doc_id, len(texts))
        vector_store = self.load_vector_store()
        vector_store.add_texts(texts=texts, metadatas=metadatas, ids=[f"{doc_id}_{i}" for i in range(len(texts))])
        vector_store.persist()

    def delete_document(self, doc_id: str) -> None:
        vector_store = self.load_vector_store()
        ids = vector_store.get(include=["metadatas"])
        if ids and ids["ids"]:
            to_delete = [item_id for item_id in ids["ids"] if str(item_id).startswith(f"{doc_id}_")]
            if to_delete:
                vector_store.delete(ids=to_delete)
                vector_store.persist()

    def retrieve(self, query: str, top_k: int = 4, score_threshold: float = 0.4) -> List[Document]:
        vector_store = self.load_vector_store()
        logger.debug("RAG 检索 query=%s top_k=%s", query, top_k)
        results = vector_store.similarity_search_with_score(query, k=top_k)
        docs = []
        for doc, score in results:
            if score <= score_threshold:
                doc.metadata["score"] = score
                docs.append(doc)
        if not docs and results:
            best_doc, best_score = results[0]
            best_doc.metadata["score"] = best_score
            docs.append(best_doc)
        return docs

    @staticmethod
    def split_text(text: str) -> List[str]:
        splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        return splitter.split_text(text)
