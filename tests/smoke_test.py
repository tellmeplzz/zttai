from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:  # pragma: no cover - 依赖可选
    import fitz  # type: ignore
except Exception:  # pragma: no cover
    fitz = None  # type: ignore

try:  # pragma: no cover - 轻量文本解析
    from pypdf import PdfReader  # type: ignore
except Exception:  # pragma: no cover
    PdfReader = None  # type: ignore

from agents import OpsAgent, load_llm
from config.settings import load_app_config
from services import MonitorService, RagService, add_message, get_or_create_session, storage


def test_end_to_end_smoke(tmp_path):
    config = load_app_config()
    config.embedding.provider = "fake"
    config.llm.provider = "DEMO"
    db_path = tmp_path / "test.db"
    conn = storage.get_connection(str(db_path))
    storage.init_db(conn)
    rag = RagService(config.vector_store, config.embedding)
    # 使用临时向量目录
    rag.vector_config.persist_path = str(tmp_path / "vector")
    Path(rag.vector_config.persist_path).mkdir(parents=True, exist_ok=True)

    pdf_path = Path("data/docs/设备维护手册_示例.pdf")
    texts: list[str] = []
    metadatas: list[dict] = []
    if fitz is not None:
        doc = fitz.open(str(pdf_path))
        for page_index, page in enumerate(doc):
            for chunk in RagService.split_text(page.get_text("text")):
                texts.append(chunk)
                metadatas.append({"source": pdf_path.name, "page": page_index + 1})
    elif PdfReader is not None:
        reader = PdfReader(str(pdf_path))
        for page_index, page in enumerate(reader.pages):
            page_text = page.extract_text() or ""
            for chunk in RagService.split_text(page_text):
                texts.append(chunk)
                metadatas.append({"source": pdf_path.name, "page": page_index + 1})
    else:  # pragma: no cover - 运行环境极端缺失
        raise RuntimeError("缺少 PDF 解析依赖，请安装 pymupdf 或 pypdf")
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
