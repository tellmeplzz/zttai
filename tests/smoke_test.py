from __future__ import annotations

from pathlib import Path

import fitz  # type: ignore

from agents import OpsAgent, load_llm
from config.settings import load_app_config
from services import MonitorService, RagService, add_message, get_or_create_session, storage


def test_end_to_end_smoke(tmp_path):
    config = load_app_config()
    db_path = tmp_path / "test.db"
    conn = storage.get_connection(str(db_path))
    storage.init_db(conn)
    rag = RagService(config.vector_store, config.embedding)
    # 使用临时向量目录
    rag.vector_config.persist_path = str(tmp_path / "vector")
    Path(rag.vector_config.persist_path).mkdir(parents=True, exist_ok=True)

    pdf_path = Path("data/docs/设备维护手册_示例.pdf")
    doc = fitz.open(str(pdf_path))
    texts = []
    metadatas = []
    for page_index, page in enumerate(doc):
        for chunk in RagService.split_text(page.get_text()):
            texts.append(chunk)
            metadatas.append({"source": pdf_path.name, "page": page_index + 1})
    rag.index_documents("test_doc", texts, metadatas)

    llm = load_llm(config.llm.provider, config.llm.model)
    agent = OpsAgent(llm, rag, conn)
    session_id = get_or_create_session(conn, "smoke")
    add_message(conn, session_id, "user", "如何进行设备维护？")
    result = agent.invoke(session_id, "如何进行设备维护？", top_k=2)
    assert result["answer"]
    assert result["documents"]

    monitor = MonitorService(conn)
    hit_id = monitor.run_mock_task()
    assert hit_id is None or hit_id > 0
