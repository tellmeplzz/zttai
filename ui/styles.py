from __future__ import annotations

"""负责注入全局 CSS 与主题切换。"""

from assets.generate_assets import ensure_assets
import streamlit as st

ensure_assets()

LIGHT_STYLE = """
<style>
body {
    background-image: url('assets/generated/ai_bg.png');
    background-size: cover;
    background-attachment: fixed;
}
[data-testid="stAppViewContainer"] {
    background: transparent;
}
.ztt-card {
    background: rgba(255, 255, 255, 0.78);
    border-radius: 16px;
    box-shadow: 0 12px 32px rgba(18, 28, 68, 0.25);
    padding: 1.5rem;
    margin-bottom: 1rem;
    backdrop-filter: blur(12px);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.ztt-card:hover {
    transform: translateY(-4px);
    box-shadow: 0 16px 40px rgba(18, 28, 68, 0.35);
}
.ztt-badge {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 12px;
    background: linear-gradient(135deg, #3d7fff, #61d9ff);
    color: #fff;
    font-weight: 600;
}
.ztt-feedback button {
    border-radius: 999px !important;
    margin-right: 0.5rem;
}
.ztt-floating {
    position: fixed;
    right: 24px;
    bottom: 24px;
    z-index: 999;
    background: rgba(24, 34, 64, 0.85);
    color: #fff;
    padding: 16px;
    border-radius: 18px;
    width: 280px;
    box-shadow: 0 20px 48px rgba(0,0,0,0.35);
}
</style>
"""

DARK_STYLE = """
<style>
body {
    background: radial-gradient(circle at top, #1f3b6d, #0b1221 70%);
}
[data-testid="stAppViewContainer"] {
    background: transparent;
    color: #f0f4ff;
}
.ztt-card {
    background: rgba(18, 28, 68, 0.78);
    border-radius: 16px;
    box-shadow: 0 12px 32px rgba(5, 8, 20, 0.6);
    padding: 1.5rem;
    margin-bottom: 1rem;
    backdrop-filter: blur(12px);
    color: #f4f8ff;
}
.ztt-card:hover {
    transform: translateY(-4px);
    box-shadow: 0 16px 40px rgba(5, 8, 20, 0.7);
}
.ztt-badge {
    background: linear-gradient(135deg, #61d9ff, #8b7bff);
}
</style>
"""


def inject(theme: str = "light") -> None:
    style = LIGHT_STYLE if theme == "light" else DARK_STYLE
    st.markdown(style, unsafe_allow_html=True)
