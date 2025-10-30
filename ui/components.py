from __future__ import annotations

"""复用型 UI 组件。"""

import streamlit as st


def document_table(documents: list[dict]) -> None:
    if not documents:
        st.info("尚未索引文档，上传后即可检索。")
        return
    for doc in documents:
        with st.expander(f"📄 {doc['filename']} | 共 {doc['pages']} 页", expanded=False):
            st.write(doc.get("meta", ""))
            st.caption(f"入库时间: {doc['created_at']}")
            st.caption(f"文档 ID: {doc['id']}")


def source_cards(sources: list[dict]) -> None:
    if not sources:
        return
    st.markdown("#### 📚 引用来源")
    for idx, item in enumerate(sources, start=1):
        with st.expander(f"[Doc-{idx}] 来源 {item.get('id', '')} (页码 {item.get('page')}, 相似度 {item.get('score'):.3f})"):
            st.write(item.get("preview", ""))


def feedback_buttons(message_id: int) -> None:
    st.markdown("<div class='ztt-feedback'>", unsafe_allow_html=True)
    cols = st.columns(3)
    with cols[0]:
        if st.button("👍 满意", key=f"like_{message_id}"):
            st.session_state.setdefault("feedback_queue", []).append((message_id, True))
    with cols[1]:
        if st.button("👎 待改进", key=f"dislike_{message_id}"):
            st.session_state.setdefault("feedback_queue", []).append((message_id, False))
    with cols[2]:
        st.session_state.setdefault("survey", {})[message_id] = st.selectbox(
            "是否解决问题？",
            options=["未选择", "是", "否"],
            key=f"solved_{message_id}",
        )
    st.markdown("</div>", unsafe_allow_html=True)
