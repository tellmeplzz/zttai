from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from types import SimpleNamespace
from typing import List

try:  # pragma: no cover - 运行环境可能缺少 PyMuPDF
    import fitz  # type: ignore
except Exception:  # pragma: no cover
    fitz = None  # type: ignore

try:  # pragma: no cover - 作为 PDF 文本提取备选
    from pypdf import PdfReader  # type: ignore
except Exception:  # pragma: no cover
    PdfReader = None  # type: ignore

import streamlit as st

from agents import OpsAgent, load_llm
from config.settings import load_app_config
from services import (
    MonitorService,
    OcrService,
    RagService,
    TTSService,
    add_message,
    classify_intent,
    get_or_create_session,
    list_messages,
    list_sessions,
    storage,
    submit_feedback,
)
from ui import feedback_buttons, header, inject, sidebar, source_cards

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(page_title="ZTT 工业智能体一体机", layout="wide")

config = load_app_config()
conn = storage.get_connection(config.storage.sqlite_path)
storage.init_db(conn)
rag = RagService(config.vector_store, config.embedding)
ocr_service = OcrService(use_gpu=config.ocr.use_gpu, fallback=config.ocr.fallback)
tts_service = TTSService(config.tts.provider, config.tts.voice, config.tts.rate)
llm = load_llm(config.llm.provider, config.llm.model, config.llm.temperature)
ops_agent = OpsAgent(llm, rag, conn)
monitor_service = MonitorService(conn)

if "ztt_dark_mode" not in st.session_state:
    st.session_state["ztt_dark_mode"] = False

header()
theme = "dark" if st.session_state.get("ztt_dark_mode") else "light"
inject(theme)

agents = ["🛠️ 运维助手", "📄 文档管理", "🧑‍🏭 标注工作台"]
current_agent, smart_route = sidebar(theme, agents, agents[0])

st.markdown("---")

if smart_route:
    st.subheader("✨ 智能路由")
    command = st.text_input("请输入操作指令，例如：上传 PDF 并索引")
    if command:
        intent = classify_intent(command)
        if intent == "ocr":
            current_agent = "📄 文档管理"
            st.success("已识别为文档管理任务，请在下方上传文件。")
        elif intent == "annotation":
            current_agent = "🧑‍🏭 标注工作台"
            st.success("已识别为异常标注流程。")
        elif intent == "ops":
            current_agent = "🛠️ 运维助手"
            st.success("已识别为运维问答。")
        else:
            st.warning("暂未识别到明确意图，请手动选择页面。")


uploads_dir = Path("data/uploads")
uploads_dir.mkdir(parents=True, exist_ok=True)


def _extract_pdf_pages(file_path: str) -> list[str]:
    """从 PDF 中提取每页文本，支持 PyMuPDF 或 PyPDF."""
    texts: list[str] = []
    if fitz is not None:  # pragma: no cover - 依赖外部库
        doc = fitz.open(file_path)  # type: ignore[arg-type]
        for page in doc:
            texts.append(page.get_text("text"))
        return texts
    if PdfReader is not None:
        reader = PdfReader(file_path)
        for page in reader.pages:
            texts.append(page.extract_text() or "")
        return texts
    logger.warning("缺少 PDF 解析库，将返回空文本: %s", file_path)
    return texts


def load_ocr_docs(keyword: str = "") -> List[dict]:
    cursor = conn.cursor()
    if keyword:
        cursor.execute(
            "SELECT id, filename, pages, created_at, meta_json FROM ocr_docs WHERE filename LIKE ? ORDER BY created_at DESC",
            (f"%{keyword}%",),
        )
    else:
        cursor.execute("SELECT id, filename, pages, created_at, meta_json FROM ocr_docs ORDER BY created_at DESC")
    docs = []
    for row in cursor.fetchall():
        meta = json.loads(row["meta_json"] or "{}")
        docs.append(
            {
                "id": row["id"],
                "filename": row["filename"],
                "pages": row["pages"],
                "created_at": row["created_at"],
                "meta": meta.get("preview", ""),
            }
        )
    return docs


def insert_ocr_doc(filename: str, pages: int, meta: dict) -> int:
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO ocr_docs(filename, pages, created_at, meta_json) VALUES(?, ?, datetime('now'), ?)",
        (filename, pages, json.dumps(meta, ensure_ascii=False)),
    )
    conn.commit()
    return int(cursor.lastrowid)


def delete_ocr_doc(doc_id: int) -> None:
    cursor = conn.cursor()
    cursor.execute("DELETE FROM ocr_docs WHERE id = ?", (doc_id,))
    conn.commit()


if current_agent == "📄 文档管理":
    st.title("📄 文档管理")
    uploaded_files = st.file_uploader(
        "上传 PDF/图片，系统将自动 OCR 并入库",
        accept_multiple_files=True,
        type=["pdf", "png", "jpg", "jpeg", "tiff"],
    )
    if uploaded_files:
        for uploaded in uploaded_files:
            file_path = uploads_dir / uploaded.name
            file_path.write_bytes(uploaded.getvalue())
            blocks = ocr_service.run(str(file_path))
            if not blocks and uploaded.name.lower().endswith(".pdf"):
                page_texts = _extract_pdf_pages(str(file_path))
                blocks = [
                    SimpleNamespace(page=idx, bbox=[0, 0, 0, 0], text=text)
                    for idx, text in enumerate(page_texts)
                ]
            pages = max([block.page for block in blocks], default=0) + 1 if blocks else 1
            text_chunks = []
            metadatas = []
            for idx, block in enumerate(blocks):
                if not block.text:
                    continue
                for chunk in rag.split_text(block.text):
                    text_chunks.append(chunk)
                    metadatas.append(
                        {
                            "source": uploaded.name,
                            "page": block.page + 1,
                            "block_index": idx,
                        }
                    )
            preview_text = "\n".join(block.text[:80] for block in blocks[:3]) if blocks else ""
            doc_id = insert_ocr_doc(uploaded.name, pages, {"preview": preview_text})
            if text_chunks:
                rag.index_documents(str(doc_id), text_chunks, metadatas)
                st.success(f"文档 {uploaded.name} 已入库，共 {len(text_chunks)} 个片段。")
            else:
                st.warning("未识别到有效文本，请确认 OCR 依赖已安装。")
    search_keyword = st.text_input("关键字搜索")
    docs = load_ocr_docs(search_keyword)
    if st.button("刷新文档列表"):
        docs = load_ocr_docs(search_keyword)
    for doc in docs:
        with st.expander(f"📄 {doc['filename']} (共 {doc['pages']} 页)"):
            st.write(doc.get("meta", ""))
            col1, col2 = st.columns(2)
            with col1:
                if st.button("重新索引", key=f"reindex_{doc['id']}"):
                    file_path = uploads_dir / doc["filename"]
                    if file_path.exists():
                        blocks = ocr_service.run(str(file_path))
                        if not blocks and doc["filename"].lower().endswith(".pdf"):
                            page_texts = _extract_pdf_pages(str(file_path))
                            blocks = [
                                SimpleNamespace(page=idx, bbox=[0, 0, 0, 0], text=text)
                                for idx, text in enumerate(page_texts)
                            ]
                        text_chunks = []
                        metadatas = []
                        for idx, block in enumerate(blocks):
                            for chunk in rag.split_text(block.text):
                                text_chunks.append(chunk)
                                metadatas.append(
                                    {
                                        "source": doc["filename"],
                                        "page": block.page + 1,
                                        "block_index": idx,
                                    }
                                )
                        rag.delete_document(str(doc["id"]))
                        if text_chunks:
                            rag.index_documents(str(doc["id"]), text_chunks, metadatas)
                            st.success("重新索引完成")
                        else:
                            st.warning("重新索引失败，未检测到文本片段")
            with col2:
                if st.button("删除", key=f"delete_{doc['id']}"):
                    delete_ocr_doc(doc["id"])
                    rag.delete_document(str(doc["id"]))
                    st.warning("已删除文档及向量索引")
    st.caption("上传文件默认存储于 data/uploads，可手动替换为真实文档。")

elif current_agent == "🛠️ 运维助手":
    st.title("🛠️ 运维助手")
    sessions = list_sessions(conn)
    session_names = [item["name"] for item in sessions]
    if "current_session" not in st.session_state:
        st.session_state["current_session"] = session_names[0] if session_names else "默认会话"
    new_session = st.text_input("新会话名称", placeholder="例如：泵站巡检")
    if st.button("创建会话") and new_session:
        get_or_create_session(conn, new_session)
        st.session_state["current_session"] = new_session
        st.experimental_rerun()
    session_choice = st.selectbox("选择会话", options=session_names or ["默认会话"], index=0 if session_names else 0)
    session_id = get_or_create_session(conn, session_choice)
    st.session_state["current_session"] = session_choice
    carry_history = st.toggle("携带历史上下文", value=True)
    top_k = st.slider("检索 Top-K", min_value=1, max_value=8, value=4)
    threshold = st.slider("相似度阈值", min_value=0.1, max_value=1.0, value=0.4)
    question = st.text_area("请输入设备故障或运维问题：", height=120)
    if st.button("发送") and question:
        user_message_id = add_message(conn, session_id, "user", question)
        # 如果用户紧接着追问，则认为上一轮未解决
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM messages WHERE session_id = ? AND role = 'assistant' ORDER BY id DESC LIMIT 1",
            (session_id,),
        )
        last_assistant = cursor.fetchone()
        if last_assistant:
            submit_feedback(conn, int(last_assistant["id"]), like=None, solved=False, note="追问自动判定")
        result = ops_agent.invoke(session_id, question, top_k=top_k, threshold=threshold, carry_history=carry_history)
        st.session_state["last_answer"] = result["answer"]
        st.success("智能体已回复，见下方历史。")
    messages = list_messages(conn, session_id, limit=20)
    for message in messages:
        if message["role"] == "user":
            st.markdown(f"**👤 用户：** {message['content']}")
        else:
            st.markdown(f"**🤖 智能体：** {message['content']}")
            if message.get("related_doc_ids"):
                doc_ids = json.loads(message["related_doc_ids"])
                sources = []
                for doc_id in doc_ids:
                    sources.append({"id": doc_id, "page": "?", "score": 0.0, "preview": "参见知识库片段"})
                source_cards(sources)
            feedback_buttons(message["id"])
    if st.session_state.get("feedback_queue"):
        for message_id, like in st.session_state.pop("feedback_queue"):
            submit_feedback(conn, message_id, like=like)
    survey = st.session_state.get("survey", {})
    for message_id, value in list(survey.items()):
        if value in ("是", "否"):
            submit_feedback(conn, message_id, solved=value == "是")
            survey.pop(message_id)

elif current_agent == "🧑‍🏭 标注工作台":
    st.title("🧑‍🏭 标注工作台")
    st.caption("监控小模型输出，异常片段将自动入队等待人工确认。")
    if st.button("运行一次异常检测"):
        hit_id = monitor_service.run_mock_task()
        if hit_id:
            st.success(f"已生成异常样本，记录 ID: {hit_id}")
        else:
            st.info("未检测到异常样本。")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM hit_queue ORDER BY created_at DESC LIMIT 20")
    hits = [dict(row) for row in cursor.fetchall()]
    for hit in hits:
        with st.expander(
            f"异常样本 {hit['id']} | 时间窗 {hit['window_start']:.2f}-{hit['window_end']:.2f}s | 评分 {hit['score']:.2f}"
        ):
            if Path(hit["sample_path"]).exists():
                st.image(hit["sample_path"], caption="波形缩略图")
            owner = st.text_input("责任人", key=f"owner_{hit['id']}")
            label = st.selectbox(
                "异常类型",
                ["机械振动", "电气噪声", "工况切换", "传感器故障", "其他"],
                key=f"label_{hit['id']}",
            )
            reasons = st.multiselect(
                "异常原因",
                ["轴承磨损", "润滑不足", "负载波动", "线路松动", "待确认"],
                key=f"reason_{hit['id']}",
            )
            note = st.text_area("备注", key=f"note_{hit['id']}")
            if st.button("提交标注", key=f"submit_{hit['id']}"):
                cursor.execute(
                    "INSERT INTO annotations(sample_path, label, reasons, note, owner, created_at) VALUES(?, ?, ?, ?, ?, datetime('now'))",
                    (
                        hit["sample_path"],
                        label,
                        ",".join(reasons),
                        note,
                        owner,
                    ),
                )
                conn.commit()
                st.success("标注已保存")
    if st.button("导出标注 CSV"):
        cursor.execute("SELECT * FROM annotations ORDER BY created_at DESC")
        rows = cursor.fetchall()
        csv_lines = ["id,sample_path,label,reasons,note,owner,created_at"]
        for row in rows:
            csv_lines.append(
                ",".join(
                    [
                        str(row["id"]),
                        row["sample_path"],
                        row["label"] or "",
                        row["reasons"] or "",
                        row["note"] or "",
                        row["owner"] or "",
                        row["created_at"] or "",
                    ]
                )
            )
        st.download_button("下载 CSV", "\n".join(csv_lines), file_name="annotations.csv")

st.markdown("---")
if st.session_state.get("last_answer"):
    with st.container():
        st.markdown(
            """
            <div class='ztt-floating'>
                <strong>🧠 数智助手</strong>
                <p style="font-size:14px;">点击按钮朗读最近一次回复。</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("🔊 朗读最新回复"):
            audio_path = asyncio.run(tts_service.synthesize(st.session_state["last_answer"]))
            st.audio(audio_path)

st.caption("数据持久化：SQLite 存储会话与反馈，Chroma 存储向量索引。")
