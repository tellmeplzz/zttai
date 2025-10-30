from __future__ import annotations

"""UI 布局组件。"""

import streamlit as st


def header() -> None:
    cols = st.columns([1, 6, 1])
    with cols[0]:
        st.image("assets/generated/ztt_logo.png", width=72)
    with cols[1]:
        st.markdown(
            "<h1 style='margin-bottom:0;'>ZTT 工业智能体一体机 Demo</h1>",
            unsafe_allow_html=True,
        )
        st.caption("Streamlit + LangChain 多智能体集成示例")
    with cols[2]:
        st.toggle("深色模式", key="ztt_dark_mode")


def sidebar(theme: str, agents: list[str], default_agent: str) -> tuple[str, bool]:
    st.sidebar.image("assets/generated/ztt_logo.png", width=120)
    st.sidebar.title("智能体选择")
    intelligent = st.sidebar.toggle("开启智能路由", value=False, key="smart_route")
    agent = st.sidebar.radio("当前工作模式", agents, index=agents.index(default_agent))
    st.sidebar.markdown("---")
    st.sidebar.subheader("主题设置")
    st.sidebar.write("当前主题: " + ("深色" if theme == "dark" else "浅色"))
    return agent, intelligent


def card(title: str, body: str, badge: str | None = None) -> None:
    st.markdown("<div class='ztt-card'>", unsafe_allow_html=True)
    cols = st.columns([4, 1])
    with cols[0]:
        st.subheader(title)
    with cols[1]:
        if badge:
            st.markdown(f"<span class='ztt-badge'>{badge}</span>", unsafe_allow_html=True)
    st.markdown(body, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
