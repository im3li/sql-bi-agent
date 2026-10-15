"""
Streamlit UI for the Conversational SQL & Automated BI Agent.

A polished, provider-agnostic BI cockpit.

Run with:
    streamlit run app.py
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path

import streamlit as st

from src.agent import BRAND_COLORS, auto_chart, build_llm, generate_sql
from src.database import DB_PATH, get_schema, run_query
from src.guardrails import validate_sql

# =============================================================================
# Constants
# =============================================================================
DEFAULT_ROW_LIMIT = 2_000
PREVIEW_ROWS = 25
FOOTER_HEIGHT = 56
SIDEBAR_WIDTH = 340

PROVIDERS: dict[str, dict[str, str]] = {
    "Groq (free, fast)": {
        "base_url": "https://api.groq.com/openai/v1",
        "default_model": "openai/gpt-oss-120b",
        "key_hint": "starts with gsk_",
    },
    "OpenAI": {
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
        "key_hint": "starts with sk-",
    },
    "Google Gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "default_model": "gemini-2.5-flash",
        "key_hint": "starts with AIza",
    },
    "Ollama (local)": {
        "base_url": "http://localhost:11434/v1",
        "default_model": "qwen2.5-coder:7b",
        "key_hint": "any string, e.g. 'ollama'",
    },
    "Custom endpoint": {
        "base_url": "",
        "default_model": "",
        "key_hint": "whatever your provider requires",
    },
}

EXAMPLE_QUESTIONS = [
    "What are the top 5 best-selling products by total revenue?",
    "Show monthly revenue trend for 2023.",
    "Which countries have the most customers?",
    "What is the average order value by product category?",
    "Who are the top 5 customers by total spend?",
    "Show the distribution of order statuses.",
]

LOGO_PATH = Path(__file__).parent / "assets" / "logo.png"
FAVICON = str(LOGO_PATH) if LOGO_PATH.exists() else "◈"

st.set_page_config(
    page_title="SQL BI Agent",
    page_icon=FAVICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

# =============================================================================
# Session state
# =============================================================================
_DEFAULTS = {
    "messages": [],
    "provider": "Groq (free, fast)",
    "base_url": PROVIDERS["Groq (free, fast)"]["base_url"],
    "model": PROVIDERS["Groq (free, fast)"]["default_model"],
    "api_key": "",
    "row_limit": DEFAULT_ROW_LIMIT,
    "show_followups": True,
    "query_history": [],
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v


# =============================================================================
# Dark theme tokens (locked)
# =============================================================================
T = {
    "bg": "#0a0c12", "bg_glow_1": "rgba(124,138,255,0.09)",
    "bg_glow_2": "rgba(167,139,250,0.06)",
    "bg_elev": "#0f1219", "bg_elev_2": "#161a23",
    "border": "#232834", "border_2": "#2e3441",
    "text": "#e8ecf3", "text_dim": "#9aa4b8", "text_mute": "#6b7385",
    "accent": "#7c8aff", "accent_2": "#a78bfa",
    "accent_glow": "rgba(124,138,255,0.15)",
    "accent_soft": "rgba(124,138,255,0.12)",
    "accent_fg": "#ffffff",
    "success": "#34d399", "danger": "#f87171",
    "code_bg": "#0a0d14", "code_text": "#e8ecf3",
    "hero_from": "#ffffff", "hero_to": "#b8c0d4",
    "grid": "#232834",
    "chatbar_fade": "linear-gradient(to top, #0a0c12 65%, rgba(10,12,18,0))",
}

# =============================================================================
# CSS
# =============================================================================
CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

/* Streamlit internal variables — dark */
:root, html, body, .stApp {{
    --primary-color: {T['accent']};
    --background-color: {T['bg']};
    --secondary-background-color: {T['bg_elev']};
    --text-color: {T['text']};
    --font: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    --font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}}

:root {{
    --bg: {T['bg']};
    --bg-elev: {T['bg_elev']};
    --bg-elev-2: {T['bg_elev_2']};
    --border: {T['border']};
    --border-2: {T['border_2']};
    --text: {T['text']};
    --text-dim: {T['text_dim']};
    --text-mute: {T['text_mute']};
    --accent: {T['accent']};
    --accent-2: {T['accent_2']};
    --accent-glow: {T['accent_glow']};
    --accent-soft: {T['accent_soft']};
    --accent-fg: {T['accent_fg']};
    --success: {T['success']};
    --danger: {T['danger']};
    --code-bg: {T['code_bg']};
    --code-text: {T['code_text']};
    --footer-h: {FOOTER_HEIGHT}px;
    --sidebar-w: {SIDEBAR_WIDTH}px;
    --radius: 12px;
    --radius-sm: 8px;

    /* glide-data-grid */
    --gdg-accent-color: {T['accent']};
    --gdg-accent-fg: {T['accent_fg']};
    --gdg-accent-light: {T['accent_soft']};
    --gdg-text-dark: {T['text']};
    --gdg-text-medium: {T['text_dim']};
    --gdg-text-light: {T['text_mute']};
    --gdg-text-bubble: {T['text']};
    --gdg-bg-icon-header: {T['bg_elev_2']};
    --gdg-fg-icon-header: {T['text_dim']};
    --gdg-text-header: {T['text_dim']};
    --gdg-text-group-header: {T['text']};
    --gdg-text-header-selected: {T['accent_fg']};
    --gdg-bg-cell: {T['bg_elev']};
    --gdg-bg-cell-medium: {T['bg_elev_2']};
    --gdg-bg-header: {T['bg_elev_2']};
    --gdg-bg-header-hovered: {T['bg_elev_2']};
    --gdg-bg-header-has-focus: {T['bg_elev_2']};
    --gdg-bg-bubble: {T['bg_elev_2']};
    --gdg-bg-bubble-selected: {T['bg_elev_2']};
    --gdg-bg-search-result: {T['accent_soft']};
    --gdg-border-color: {T['border']};
    --gdg-horizontal-border-color: {T['border']};
    --gdg-drilldown-border: {T['border']};
    --gdg-link-color: {T['accent']};
    --gdg-font-family: 'Inter', sans-serif;
    --gdg-editor-font-size: 12px;
}}

/* ================== GLOBAL ================== */
html, body, [class*="css"] {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    font-feature-settings: 'cv02','cv03','cv04','cv11';
}}
.stApp {{
    background:
        radial-gradient(1200px 600px at 15% -10%, {T['bg_glow_1']}, transparent 55%),
        radial-gradient(900px 500px at 95% 5%, {T['bg_glow_2']}, transparent 55%),
        var(--bg);
    color: var(--text);
}}

/* ================== CHROME ================== */
#MainMenu {{ visibility: hidden; }}
[data-testid="stDecoration"] {{ display: none !important; }}
[data-testid="stStatusWidget"] {{ visibility: hidden !important; }}
[data-testid="stToolbarActions"],
[data-testid="stDeployButton"],
[data-testid="stAppDeployButton"] {{
    display: none !important;
}}
header[data-testid="stHeader"] {{
    background: transparent !important;
    box-shadow: none !important;
    visibility: visible !important;
    overflow: visible !important;
}}

/* ================== SIDEBAR ================== */
[data-testid="stSidebar"] {{
    background: var(--bg-elev) !important;
    border-right: 1px solid var(--border) !important;
}}
[data-testid="stSidebar"] > div:first-child {{
    padding: 0.9rem 0.85rem 1.5rem 0.85rem;
    overflow-y: auto;
}}
[data-testid="stSidebar"] * {{ color: var(--text); }}

[data-testid="stSidebarHeader"] {{
    padding: 8px 8px 0 8px !important;
    display: flex !important;
    justify-content: flex-start !important;
    align-items: center !important;
}}
[data-testid="stSidebarCollapseButton"] {{
    margin-left: 0 !important;
    margin-right: auto !important;
    order: 0 !important;
}}

[data-testid="stSidebarCollapseButton"] button {{
    background: var(--bg-elev-2) !important;
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
    color: var(--text) !important;
    transition: all .15s ease !important;
}}
[data-testid="stSidebarCollapseButton"] button:hover {{
    border-color: var(--accent) !important;
    color: var(--accent) !important;
    background: var(--accent-soft) !important;
}}
[data-testid="stSidebarCollapseButton"] button svg,
[data-testid="stSidebarCollapseButton"] button span {{
    fill: currentColor !important;
    color: inherit !important;
}}

/* Reopen (›) button */
[data-testid="stSidebarCollapsedControl"],
[data-testid="collapsedControl"],
[data-testid="stSidebarCollapsedControlButton"] {{
    display: flex !important;
    visibility: visible !important;
    opacity: 1 !important;
    pointer-events: auto !important;
    position: fixed !important;
    top: 14px !important;
    left: 14px !important;
    z-index: 999999 !important;
    width: 40px !important;
    height: 40px !important;
    background: var(--bg-elev) !important;
    border: 1px solid var(--border-2) !important;
    border-radius: 10px !important;
    color: var(--text) !important;
    box-shadow: 0 6px 20px rgba(0, 0, 0, 0.22) !important;
    align-items: center !important;
    justify-content: center !important;
    padding: 0 !important;
    margin: 0 !important;
    transition: all .15s ease !important;
}}
[data-testid="stSidebarCollapsedControl"]:hover,
[data-testid="collapsedControl"]:hover,
[data-testid="stSidebarCollapsedControlButton"]:hover {{
    border-color: var(--accent) !important;
    color: var(--accent) !important;
    background: var(--accent-soft) !important;
}}
[data-testid="stSidebarCollapsedControl"] button,
[data-testid="collapsedControl"] button,
[data-testid="stSidebarCollapsedControlButton"] button {{
    background: transparent !important;
    border: none !important;
    color: inherit !important;
    width: 100% !important;
    height: 100% !important;
    padding: 0 !important;
}}
[data-testid="stSidebarCollapsedControl"] svg,
[data-testid="collapsedControl"] svg,
[data-testid="stSidebarCollapsedControlButton"] svg {{
    fill: currentColor !important;
    color: inherit !important;
}}
button[kind="header"], button[kind="headerNoPadding"] {{
    visibility: visible !important;
    opacity: 1 !important;
    pointer-events: auto !important;
}}

/* Sidebar brand */
.sidebar-brand {{
    display: flex; align-items: center; gap: 8px;
    margin: 0 0 6px 0; line-height: 1.2;
}}
.sidebar-brand .logo {{
    width: 40px; height: 40px; border-radius: 11px;
    background: linear-gradient(135deg, var(--accent), var(--accent-2));
    display: flex; align-items: center; justify-content: center;
    color: #fff; flex-shrink: 0;
    box-shadow: 0 6px 18px var(--accent-glow);
}}
.sidebar-brand .logo svg {{
    width: 22px !important;
    height: 22px !important;
}}
.sidebar-brand .name {{
    font-weight: 700; font-size: 19px; line-height: 1.15;
    letter-spacing: -0.02em;
    color: var(--text);
}}
.sidebar-brand .tag {{
    font-size: 11.5px; color: var(--text-mute); line-height: 1.3;
    margin-top: 2px;
}}
.sb-section {{
    font-size: 10px; font-weight: 600; letter-spacing: 0.09em;
    text-transform: uppercase; color: var(--text-mute);
    margin: 10px 0 4px 2px;
}}
.sb-divider {{
    border: none; border-top: 1px solid var(--border);
    margin: 8px 0;
}}

/* Sidebar expanders */
[data-testid="stSidebar"] [data-testid="stExpander"] {{
    margin-bottom: 6px !important;
    background: var(--bg-elev-2) !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
}}
[data-testid="stSidebar"] [data-testid="stExpander"] summary {{
    padding: 8px 12px !important;
    font-size: 12px !important;
}}
[data-testid="stSidebar"] .stTextInput,
[data-testid="stSidebar"] .stSelectbox,
[data-testid="stSidebar"] .stSlider {{
    margin-bottom: 4px !important;
}}

/* ================== MAIN CONTENT ================== */
.block-container {{
    padding: 2rem 2.5rem 10rem 2.5rem !important;
    max-width: 1080px !important;
    margin: 0 auto !important;
}}

/* ================== TEXT INPUTS ================== */
.stTextInput [data-baseweb="input"],
.stTextInput [data-testid="stTextInputRootElement"] {{
    background: var(--bg-elev-2) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius-sm) !important;
    transition: border-color .15s ease, box-shadow .15s ease;
    overflow: hidden;
}}
.stTextInput [data-baseweb="input"]:focus-within,
.stTextInput [data-testid="stTextInputRootElement"]:focus-within {{
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 3px var(--accent-glow) !important;
}}
.stTextInput input {{
    background: transparent !important;
    border: none !important;
    color: var(--text) !important;
    font-size: 13px !important;
    outline: none !important;
    box-shadow: none !important;
}}
.stTextInput input::placeholder {{
    color: var(--text-mute) !important; opacity: 1 !important;
}}
.stTextInput label {{
    font-size: 12px !important;
    color: var(--text-dim) !important;
    font-weight: 500 !important;
}}
.stTextInput [data-baseweb="input"] button,
.stTextInput [data-testid="stTextInputRootElement"] button {{
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    color: var(--text-dim) !important;
    padding: 0 10px !important;
    transition: color .15s ease !important;
}}
.stTextInput [data-baseweb="input"] button:hover,
.stTextInput [data-testid="stTextInputRootElement"] button:hover {{
    background: transparent !important;
    color: var(--accent) !important;
}}
.stTextInput [data-baseweb="input"] button svg {{
    color: inherit !important;
    fill: currentColor !important;
}}

/* ================== SELECTBOX ================== */
.stSelectbox [data-baseweb="select"],
.stSelectbox [data-baseweb="select"] > div,
.stSelectbox [data-baseweb="select"] > div > div,
.stSelectbox [data-baseweb="select"] [data-baseweb="block"],
.stSelectbox [data-baseweb="select"] [role="button"],
.stSelectbox [data-baseweb="select"] [role="combobox"],
.stSelectbox [data-baseweb="select"] div[aria-haspopup="listbox"] {{
    background-color: var(--bg-elev-2) !important;
    background: var(--bg-elev-2) !important;
    color: var(--text) !important;
    border-color: var(--border) !important;
}}
.stSelectbox [data-baseweb="select"] *:not(svg):not(path) {{
    background-color: transparent !important;
    color: var(--text) !important;
}}
.stSelectbox [data-baseweb="select"] {{
    background-color: var(--bg-elev-2) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius-sm) !important;
}}
.stSelectbox [data-baseweb="select"] svg {{
    fill: var(--text-dim) !important;
    color: var(--text-dim) !important;
}}
.stSelectbox [data-baseweb="select"]:focus-within {{
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 3px var(--accent-glow) !important;
}}
.stSelectbox label {{
    font-size: 12px !important;
    color: var(--text-dim) !important;
    font-weight: 500 !important;
}}

/* Dropdown popover */
[data-baseweb="popover"],
[data-baseweb="popover"] > div,
[data-baseweb="popover"] [data-baseweb="menu"],
[data-baseweb="menu"],
[role="listbox"],
ul[data-testid="stSelectboxVirtualDropdown"] {{
    background: var(--bg-elev) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius-sm) !important;
    box-shadow: 0 8px 28px rgba(0, 0, 0, 0.18) !important;
    color: var(--text) !important;
}}
[role="option"],
[data-baseweb="menu"] li,
[data-baseweb="menu"] [role="option"] {{
    background: transparent !important;
    color: var(--text) !important;
    font-size: 13px !important;
}}
[role="option"]:hover,
[data-baseweb="menu"] li:hover,
[data-baseweb="menu"] [role="option"]:hover,
[aria-selected="true"][role="option"] {{
    background: var(--accent-soft) !important;
    color: var(--accent) !important;
}}

/* ================== SLIDER ================== */
[data-testid="stSlider"] [data-baseweb="slider"] div[role="slider"] {{
    background-color: var(--accent) !important;
    border-color: var(--accent) !important;
}}
[data-testid="stSlider"] [data-baseweb="slider"] div[data-testid="stSliderTrack"] {{
    background: var(--accent) !important;
}}
[data-testid="stSlider"] label {{
    font-size: 12px !important;
    color: var(--text-dim) !important;
}}

/* ================== TOOLTIP ================== */
[data-testid="stTooltipIcon"] svg {{ fill: var(--text-mute) !important; }}
[data-testid="stTooltipIcon"]:hover svg {{ fill: var(--accent) !important; }}

/* ================== BUTTONS ================== */
.stButton > button {{
    background: var(--bg-elev-2) !important;
    border: 1px solid var(--border) !important;
    color: var(--text) !important;
    border-radius: var(--radius-sm) !important;
    font-weight: 500 !important;
    font-size: 13px !important;
    padding: 8px 14px !important;
    min-height: 38px !important;
    transition: all .15s ease !important;
}}
.stButton > button:hover {{
    border-color: var(--accent) !important;
    color: var(--accent) !important;
    box-shadow: 0 6px 18px var(--accent-glow);
}}
.stButton > button p {{ margin: 0 !important; }}

.stDownloadButton > button {{
    background: linear-gradient(135deg, var(--accent), var(--accent-2)) !important;
    border: none !important;
    color: #fff !important;
    font-weight: 500 !important;
    border-radius: var(--radius-sm) !important;
    padding: 10px 18px !important;
    transition: all .15s ease !important;
}}
.stDownloadButton > button:hover {{
    box-shadow: 0 10px 26px var(--accent-glow);
}}

/* ================== HERO ================== */
.hero {{ margin-bottom: 24px; }}
.hero .badge {{
    display: inline-flex; align-items: center; gap: 6px;
    padding: 4px 10px;
    background: rgba(52,211,153,0.08);
    border: 1px solid rgba(52,211,153,0.2);
    border-radius: 999px;
    font-size: 11px; color: var(--success); font-weight: 500;
    margin-bottom: 12px;
}}
.hero .badge .dot {{
    width: 6px; height: 6px; background: var(--success);
    border-radius: 50%; box-shadow: 0 0 8px var(--success);
    animation: pulse 2s infinite;
}}
@keyframes pulse {{ 0%,100% {{ opacity: 1; }} 50% {{ opacity: .35; }} }}
.hero h1 {{
    font-size: 30px; font-weight: 700;
    letter-spacing: -0.03em; line-height: 1.15;
    margin: 0 0 6px 0;
    background: linear-gradient(135deg, {T['hero_from']} 0%, {T['hero_to']} 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}}
.hero p {{
    font-size: 14px; color: var(--text-dim);
    margin: 0; max-width: 620px; line-height: 1.55;
}}

/* ================== EMPTY STATE ================== */
.empty-wrap {{ padding: 30px 0 14px 0; text-align: center; }}
.empty-icon {{
    display: inline-flex; align-items: center; justify-content: center;
    width: 60px; height: 60px; border-radius: 18px;
    background: linear-gradient(135deg, var(--accent-soft), rgba(167,139,250,0.10));
    border: 1px solid var(--accent-glow);
    margin-bottom: 14px;
    color: var(--accent);
}}
.empty-title {{
    font-size: 20px; font-weight: 600;
    letter-spacing: -0.02em; margin-bottom: 6px;
}}
.empty-sub {{ color: var(--text-dim); font-size: 14px; margin-bottom: 22px; }}
.sugg-label {{
    font-size: 10.5px; font-weight: 600; letter-spacing: .09em;
    text-transform: uppercase; color: var(--text-mute);
    text-align: left; margin-bottom: 8px; padding-left: 2px;
}}

/* ================== FOLLOW-UP CHIPS ================== */
.followup-wrap {{
    margin-top: 14px;
    padding-top: 14px;
    border-top: 1px dashed var(--border);
}}
.followup-label {{
    display: flex; align-items: center; gap: 6px;
    font-size: 10.5px; font-weight: 600; letter-spacing: .09em;
    text-transform: uppercase; color: var(--text-mute);
    margin-bottom: 8px;
}}
.followup-label svg {{ fill: var(--accent); }}
.followup-wrap .stButton > button {{
    text-align: left !important;
    height: auto !important;
    padding: 10px 12px !important;
    font-size: 12.5px !important;
    line-height: 1.4 !important;
    font-weight: 400 !important;
    white-space: normal !important;
    background: var(--bg-elev-2) !important;
    border: 1px solid var(--border) !important;
}}
.followup-wrap .stButton > button:hover {{
    border-color: var(--accent) !important;
    background: var(--accent-soft) !important;
    color: var(--accent) !important;
}}

/* ================== CHAT ================== */
[data-testid="stChatMessage"] {{
    background: transparent !important;
    border: none !important;
    padding: 0 !important;
    margin-bottom: 6px;
}}
[data-testid="stChatMessage"] [data-testid="stChatMessageContent"] {{
    background: var(--bg-elev) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
    padding: 14px 16px !important;
    font-size: 14px !important;
    line-height: 1.55;
    color: var(--text) !important;
}}
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) [data-testid="stChatMessageContent"] {{
    background: linear-gradient(135deg, var(--accent-soft), rgba(167,139,250,0.07)) !important;
    border-color: var(--accent-glow) !important;
}}

/* ================== CHAT INPUT ================== */
[data-testid="stBottom"] {{
    bottom: var(--footer-h) !important;
    background: {T['chatbar_fade']} !important;
}}
[data-testid="stBottom"] > div,
[data-testid="stBottomBlockContainer"] {{
    background: transparent !important;
}}
[data-testid="stChatInput"] {{
    background: var(--bg-elev) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
    transition: border-color .15s ease, box-shadow .15s ease;
}}
[data-testid="stChatInput"]:focus-within {{
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 4px var(--accent-glow) !important;
}}
[data-testid="stChatInput"] > div,
[data-testid="stChatInput"] > div > div,
[data-testid="stChatInput"] div[data-baseweb="base-input"] {{
    background: transparent !important;
    border: none !important;
}}
[data-testid="stChatInput"] textarea {{
    background: transparent !important;
    color: var(--text) !important;
    font-size: 14px !important;
    caret-color: var(--accent) !important;
}}
[data-testid="stChatInput"] textarea::placeholder {{
    color: var(--text-mute) !important;
}}
[data-testid="stChatInput"] button {{
    background: var(--accent) !important;
    color: #fff !important;
    border-radius: 8px !important;
}}
[data-testid="stChatInput"] button:disabled {{
    background: var(--bg-elev-2) !important;
    color: var(--text-mute) !important;
}}
[data-testid="stChatInput"] button svg {{ fill: currentColor !important; }}

/* ================== METRICS ================== */
.metrics-strip {{
    display: grid; grid-template-columns: repeat(3, 1fr);
    gap: 10px; margin: 12px 0 14px 0;
}}
.metric-cell {{
    background: var(--bg-elev);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    padding: 12px 14px;
}}
.metric-cell .label {{
    font-size: 10.5px; text-transform: uppercase;
    letter-spacing: .07em; color: var(--text-mute);
    font-weight: 600; margin-bottom: 4px;
}}
.metric-cell .value {{
    font-size: 19px; font-weight: 600;
    letter-spacing: -0.02em; color: var(--text);
    font-variant-numeric: tabular-nums;
}}
.metric-cell .value.accent {{ color: var(--accent); }}
.metric-cell .value.success {{ color: var(--success); }}

/* ================== EXPANDER ================== */
[data-testid="stExpander"] {{
    background: var(--bg-elev) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
    margin-bottom: 12px;
    overflow: hidden;
}}
[data-testid="stExpander"] details,
[data-testid="stExpander"] > details {{
    background: var(--bg-elev) !important;
}}
[data-testid="stExpander"] summary {{
    padding: 11px 16px !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    color: var(--text) !important;
    background: var(--bg-elev) !important;
}}
[data-testid="stExpander"] summary:hover {{ color: var(--accent) !important; }}

[data-testid="stExpanderDetails"],
[data-testid="stExpanderDetails"] > div,
[data-testid="stExpanderDetails"] > div > div,
[data-testid="stExpanderDetails"] [data-testid="stVerticalBlock"],
[data-testid="stExpanderDetails"] [data-testid="stVerticalBlockBorderWrapper"],
[data-testid="stExpanderDetails"] [data-testid="stVerticalBlockBorderWrapper"] > div,
[data-testid="stExpanderDetails"] [data-testid="stMarkdownContainer"] {{
    background: var(--bg-elev) !important;
    background-color: var(--bg-elev) !important;
    color: var(--text) !important;
    border-color: var(--border) !important;
}}
[data-testid="stExpander"] [data-testid="stExpanderDetails"] {{
    padding: 0 14px 14px 14px !important;
    border-top: 1px solid var(--border) !important;
}}

/* ================== CODE BLOCK ================== */
[data-testid="stCodeBlock"],
[data-testid="stCodeBlock"] > div,
[data-testid="stCodeBlock"] > div > div,
[data-testid="stCodeBlock"] > div > div > div,
[data-testid="stCodeBlock"] pre,
[data-testid="stCodeBlock"] pre > code,
[data-testid="stCodeBlock"] code {{
    background: var(--code-bg) !important;
    background-color: var(--code-bg) !important;
    color: var(--code-text) !important;
    border-color: var(--border) !important;
}}
[data-testid="stCodeBlock"] {{
    border: 1px solid var(--border) !important;
    border-radius: var(--radius-sm) !important;
}}
[data-testid="stCodeBlock"] pre,
[data-testid="stCodeBlock"] code,
[data-testid="stCodeBlock"] span,
[data-testid="stCodeBlock"] .token {{
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 12.5px !important;
    color: var(--code-text) !important;
    background: transparent !important;
    background-color: transparent !important;
}}

/* ================== DATAFRAME ================== */
[data-testid="stDataFrame"],
[data-testid="stDataFrame"] > div,
[data-testid="stDataFrame"] [data-testid="stDataFrameResizable"],
[data-testid="stDataFrame"] [role="grid"],
[data-testid="stDataFrame"] [role="gridcell"],
[data-testid="stDataFrame"] [role="columnheader"],
[data-testid="stDataFrame"] [role="rowheader"],
[data-testid="stDataFrame"] [role="row"] {{
    background-color: var(--bg-elev) !important;
    color: var(--text) !important;
    border-color: var(--border) !important;
}}
[data-testid="stDataFrame"] {{
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
    overflow: hidden;
}}
[data-testid="stDataFrame"] input,
[data-testid="stDataFrame"] [data-baseweb="input"] {{
    background: var(--bg-elev-2) !important;
    color: var(--text) !important;
    border-color: var(--border) !important;
}}

/* ================== ALERTS ================== */
.stAlert {{
    background: var(--bg-elev) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
    color: var(--text) !important;
}}

.stSpinner > div {{ border-top-color: var(--accent) !important; }}

/* ================== SCROLLBAR ================== */
::-webkit-scrollbar {{ width: 8px; height: 8px; }}
::-webkit-scrollbar-track {{ background: transparent; }}
::-webkit-scrollbar-thumb {{ background: var(--border-2); border-radius: 8px; }}
::-webkit-scrollbar-thumb:hover {{ background: var(--accent); }}

/* ================== STATUS PILL ================== */
.status-pill {{
    display: inline-flex; align-items: center; gap: 6px;
    padding: 5px 9px;
    background: rgba(52,211,153,0.08);
    border: 1px solid rgba(52,211,153,0.2);
    border-radius: 8px;
    font-size: 11px; color: var(--success);
    font-weight: 500; margin-bottom: 4px;
}}
.status-pill.warn {{
    background: rgba(248,113,113,0.08);
    border-color: rgba(248,113,113,0.2);
    color: var(--danger);
}}
.status-pill .dot {{
    width: 6px; height: 6px; border-radius: 50%;
    background: currentColor;
}}

/* History rows */
.hist-row {{
    display: flex; flex-direction: column; gap: 2px;
    padding: 6px 0;
}}
.hist-row .q {{
    font-size: 12px; font-weight: 500; color: var(--text);
    line-height: 1.35;
    overflow: hidden; text-overflow: ellipsis;
    display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
}}
.hist-row .t {{
    font-size: 10px; color: var(--text-mute);
}}

/* ================== FOOTER ================== */
.app-footer {{
    position: fixed;
    left: 0;
    right: 0;
    bottom: 0;
    height: var(--footer-h);
    z-index: 40;
    padding: 0 32px;
    background: var(--bg-elev);
    border-top: 1px solid var(--border);
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 14px;
    color: var(--text-dim);
    font-size: 12.5px;
    transition: left .18s ease;
}}
.stApp:has([data-testid="stSidebar"][aria-expanded="true"]) .app-footer {{
    left: var(--sidebar-w);
}}
.stApp:has([data-testid="stSidebar"][aria-expanded="false"]) .app-footer {{
    left: 0;
}}
.app-footer .author .name {{ color: var(--text); font-weight: 600; }}
.app-footer .author .sep {{ color: var(--text-mute); margin: 0 8px; }}
.app-footer .author .role {{ color: var(--text-mute); }}
.footer-social {{ display: flex; gap: 8px; }}
.footer-social a {{
    display: inline-flex; align-items: center; justify-content: center;
    width: 32px; height: 32px;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    color: var(--text-dim) !important;
    transition: all .15s ease;
    text-decoration: none !important;
}}
.footer-social a:hover {{
    color: var(--accent) !important;
    border-color: var(--accent);
    transform: translateY(-1px);
}}
.footer-social a svg {{ display: block; }}

span[data-testid="stIconMaterial"] {{ font-size: 16px !important; }}
</style>
"""

st.markdown(CSS, unsafe_allow_html=True)

# =============================================================================
# Icons
# =============================================================================
ICON_LOGO = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="16" height="16" '
    'fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" '
    'stroke-linejoin="round"><path d="M3 3v18h18"/><path d="M7 14l4-4 3 3 5-6"/></svg>'
)
ICON_EMPTY = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="28" height="28" '
    'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
    'stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>'
)
ICON_SPARK = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="12" height="12" '
    'fill="currentColor"><path d="M12 2l2.4 7.4H22l-6.2 4.5 2.4 7.4L12 16.8 5.8 21.3l2.4-7.4L2 9.4h7.6z"/></svg>'
)
ICON_LINKEDIN = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="16" height="16" '
    'fill="currentColor"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 '
    '0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 '
    '3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 '
    '2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 '
    '1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 '
    '22.222 0h.003z"/></svg>'
)
ICON_INSTAGRAM = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="16" height="16" '
    'fill="currentColor"><path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 '
    '4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 '
    '4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 '
    '0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 '
    '4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 '
    '8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98C8.333 23.986 8.741 24 '
    '12 24c3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 '
    '0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 '
    '0zm0 5.838a6.162 6.162 0 100 12.324 6.162 6.162 0 000-12.324zM12 16a4 4 0 110-8 4 4 0 010 '
    '8zm6.406-11.845a1.44 1.44 0 100 2.881 1.44 1.44 0 000-2.881z"/></svg>'
)


# =============================================================================
# Helpers
# =============================================================================
def _secret(name: str, default: str = "") -> str:
    try:
        return st.secrets[name]
    except Exception:
        return default


def _on_provider_change() -> None:
    preset = PROVIDERS.get(st.session_state.provider, {})
    if preset.get("base_url"):
        st.session_state.base_url = preset["base_url"]
    if preset.get("default_model"):
        st.session_state.model = preset["default_model"]


def _resolve_credentials() -> tuple[str, str, str]:
    key = (
        st.session_state.get("api_key", "")
        or os.environ.get("GROQ_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or _secret("GROQ_API_KEY")
        or _secret("OPENAI_API_KEY")
    )
    model = (
        st.session_state.get("model")
        or _secret("GROQ_MODEL")
        or PROVIDERS[st.session_state.provider]["default_model"]
    )
    url = (
        st.session_state.get("base_url", "").strip()
        or os.environ.get("OPENAI_API_BASE")
        or _secret("GROQ_API_BASE")
        or PROVIDERS[st.session_state.provider]["base_url"]
    )
    return key, model, url


def suggest_followups(api_key: str, model: str, base_url: str | None,
                      question: str, sql: str, df) -> list[str]:
    if df is None or df.empty:
        return []
    try:
        from langchain_core.messages import HumanMessage
        llm = build_llm(api_key=api_key, model=model, base_url=base_url)
        cols = ", ".join(map(str, df.columns.tolist()[:8]))
        prompt = (
            "You are a senior data analyst. The user just asked:\n"
            f'"{question}"\n\n'
            "You ran this SQL:\n"
            f"{sql}\n\n"
            f"The result has {len(df)} rows with columns: {cols}\n\n"
            "Generate exactly 3 short follow-up questions (each under 60 characters, "
            "no numbering, no quotes) that would help the user drill deeper into "
            "THIS SPECIFIC analysis. Focus on comparisons, breakdowns, trends, "
            "filters, or top-N variations. One question per line. No explanations."
        )
        resp = llm.invoke([HumanMessage(content=prompt)])
        text = resp.content if isinstance(resp.content, str) else str(resp.content)
        lines = [
            ln.strip().lstrip("-•*0123456789. ").strip('"\'')
            for ln in text.splitlines()
        ]
        return [ln for ln in lines if ln and len(ln) < 100][:3]
    except Exception:
        return []


def apply_chart_theme(fig):
    if fig is None:
        return None
    fig.update_layout(
        template="plotly_dark", colorway=BRAND_COLORS,
        font=dict(family="Inter, sans-serif", size=12, color=T["text"]),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=40, r=20, t=52, b=40),
        title=dict(font=dict(size=15, color=T["text"])),
        legend=dict(bgcolor="rgba(0,0,0,0)",
                    font=dict(color=T["text_dim"], size=11)),
    )
    fig.update_xaxes(gridcolor=T["grid"], linecolor=T["grid"],
                     tickfont=dict(color=T["text_dim"]),
                     title_font=dict(color=T["text_dim"]),
                     zerolinecolor=T["grid"])
    fig.update_yaxes(gridcolor=T["grid"], linecolor=T["grid"],
                     tickfont=dict(color=T["text_dim"]),
                     title_font=dict(color=T["text_dim"]),
                     zerolinecolor=T["grid"])
    return fig


def render_hero() -> None:
    db_label = DB_PATH.name if DB_PATH.exists() else "no database"
    html = (
        '<div class="hero">'
        f'<div class="badge"><span class="dot"></span>Connected &middot; {db_label}</div>'
        '<h1>Conversational SQL &amp; Automated BI Agent</h1>'
        '<p>Ask questions in plain English. Get validated SQL, results, and '
        'interactive charts &mdash; safely and instantly.</p>'
        '</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def render_empty_state() -> None:
    html = (
        '<div class="empty-wrap">'
        f'<div class="empty-icon">{ICON_EMPTY}</div>'
        '<div class="empty-title">Ask your first question</div>'
        '<div class="empty-sub">Type below, or pick one of the examples to get started.</div>'
        '</div>'
    )
    st.markdown(html, unsafe_allow_html=True)
    st.markdown('<div class="sugg-label">Suggested questions</div>',
                unsafe_allow_html=True)
    cols = st.columns(2)
    for i, q in enumerate(EXAMPLE_QUESTIONS):
        with cols[i % 2]:
            if st.button(q, key=f"chip_{i}", use_container_width=True):
                st.session_state.trigger = q
                st.rerun()


def render_metrics(df, elapsed: float) -> None:
    html = (
        '<div class="metrics-strip">'
        '<div class="metric-cell"><div class="label">Rows</div>'
        f'<div class="value accent">{len(df):,}</div></div>'
        '<div class="metric-cell"><div class="label">Columns</div>'
        f'<div class="value">{len(df.columns)}</div></div>'
        '<div class="metric-cell"><div class="label">Query time</div>'
        f'<div class="value success">{elapsed:.2f}s</div></div>'
        '</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def render_assistant_results(
    sql: str,
    df,
    elapsed: float,
    suggestions: list[str] | None = None,
    msg_idx: int = 0,
) -> None:
    with st.expander(":material/terminal: Generated SQL", expanded=True):
        st.code(sql, language="sql")

    if df is None or df.empty:
        st.info("The query returned no rows.")
    else:
        render_metrics(df, elapsed)
        st.dataframe(df.head(PREVIEW_ROWS), use_container_width=True)

        col_a, _ = st.columns([1, 3])
        with col_a:
            st.download_button(
                ":material/download: Download CSV",
                data=df.to_csv(index=False).encode("utf-8"),
                file_name="query_result.csv", mime="text/csv",
                use_container_width=True,
                key=f"csv_download_{msg_idx}",
            )

        fig = apply_chart_theme(auto_chart(df))
        if fig is not None:
            st.plotly_chart(fig, use_container_width=True, theme=None)
        else:
            st.caption("No chart auto-generated for this result shape.")

    if suggestions:
        st.markdown(
            f'<div class="followup-wrap">'
            f'<div class="followup-label">{ICON_SPARK} Continue your analysis</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        fcols = st.columns(len(suggestions))
        for j, s in enumerate(suggestions):
            with fcols[j % len(fcols)]:
                if st.button(s, key=f"fu_{msg_idx}_{j}",
                             use_container_width=True):
                    st.session_state.trigger = s
                    st.rerun()


def process_question(prompt: str, api_key: str, model: str,
                     base_url: str | None, messages: list[dict]) -> None:
    with st.chat_message("assistant"):
        with st.spinner("Analyzing your question…"):
            try:
                schema = get_schema()
                llm = build_llm(api_key=api_key, model=model, base_url=base_url)
                raw_sql = generate_sql(llm, schema, prompt, messages)
                ok, result = validate_sql(raw_sql)
                if not ok:
                    st.error(f"Query rejected by guardrail: {result}")
                    st.session_state.messages.append(
                        {"role": "assistant",
                         "content": f"Query rejected: {result}"})
                    return

                safe_sql = result
                t0 = time.perf_counter()
                df = run_query(safe_sql)
                elapsed = time.perf_counter() - t0
                limit = int(st.session_state.get("row_limit", DEFAULT_ROW_LIMIT))
                if len(df) > limit:
                    df = df.head(limit)

                suggestions: list[str] = []
                if st.session_state.get("show_followups", True) and not df.empty:
                    suggestions = suggest_followups(
                        api_key, model, base_url, prompt, safe_sql, df,
                    )

                render_assistant_results(
                    safe_sql, df, elapsed, suggestions,
                    msg_idx=len(st.session_state.messages),
                )

                hist = st.session_state.setdefault("query_history", [])
                hist.insert(0, {
                    "prompt": prompt,
                    "sql": safe_sql,
                    "ts": datetime.now().strftime("%H:%M:%S"),
                })
                st.session_state.query_history = hist[:10]

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": f"Returned {len(df):,} row(s).",
                    "sql": safe_sql, "df": df, "elapsed": elapsed,
                    "suggestions": suggestions,
                })
            except Exception as exc:  # noqa: BLE001
                st.error(f"{type(exc).__name__}: {exc}")
                st.session_state.messages.append(
                    {"role": "assistant", "content": f"Error: {exc}"})


def render_footer() -> None:
    html = (
        '<div class="app-footer">'
        '<div class="author">'
        'Developed by <span class="name">Ali Al Sulaimani</span>'
        '<span class="sep">&middot;</span>'
        '<span class="role">AI Developer &amp; Researcher</span>'
        '</div>'
        '<div class="footer-social">'
        f'<a href="https://www.linkedin.com/in/alialsulaimani/" target="_blank" rel="noopener" title="LinkedIn">{ICON_LINKEDIN}</a>'
        f'<a href="https://www.instagram.com/alisulaimanii/" target="_blank" rel="noopener" title="Instagram">{ICON_INSTAGRAM}</a>'
        '</div>'
        '</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def _reset_settings() -> None:
    """Reset button callback.

    Runs BEFORE widgets are re-instantiated on the next rerun, so it is
    safe to overwrite widget-backed keys like `provider`, `model`, etc.
    Messages and query history are preserved.
    """
    for k, v in _DEFAULTS.items():
        if k not in ("messages", "query_history"):
            st.session_state[k] = v


# =============================================================================
# Sidebar
# =============================================================================
with st.sidebar:
    # --- Brand (no theme toggle) ---
    st.markdown(
        '<div class="sidebar-brand">'
        f'<div class="logo">{ICON_LOGO}</div>'
        '<div>'
        '<div class="name">SQL BI Agent</div>'
        '<div class="tag">Conversational analytics</div>'
        '</div></div>',
        unsafe_allow_html=True,
    )

    st.markdown('<hr class="sb-divider">', unsafe_allow_html=True)

    st.markdown('<div class="sb-section">Provider</div>', unsafe_allow_html=True)
    st.selectbox(
        "Provider",
        options=list(PROVIDERS.keys()),
        key="provider",
        on_change=_on_provider_change,
        help="Pick your AI provider. Base URL and model auto-fill.",
        label_visibility="collapsed",
    )
    st.text_input(
        ":material/key: API Key",
        type="password", key="api_key", placeholder="gsk_…",
        help="Your provider's secret key.",
    )

    with st.expander(":material/tune: Advanced provider settings"):
        st.text_input(
            ":material/memory: Model", key="model",
            help="AI model ID for the current provider.",
        )
        st.text_input(
            ":material/language: Base URL", key="base_url",
            help="API endpoint — auto-filled based on provider.",
        )

    st.markdown('<div class="sb-section">Database</div>', unsafe_allow_html=True)
    if DB_PATH.exists():
        st.markdown(
            f'<div class="status-pill"><span class="dot"></span>{DB_PATH.name}</div>',
            unsafe_allow_html=True,
        )
        with st.expander(":material/schema: View schema"):
            st.code(get_schema(), language="text")
    else:
        st.markdown(
            '<div class="status-pill warn"><span class="dot"></span>No database found</div>',
            unsafe_allow_html=True,
        )
        st.caption("Run `python init_db.py` first.")

    history = st.session_state.get("query_history", [])
    if history:
        with st.expander(f":material/history: Recent queries ({len(history)})"):
            for i_hist, h in enumerate(history[:6]):
                st.markdown(
                    '<div class="hist-row">'
                    f'<div class="q">{h["prompt"]}</div>'
                    f'<div class="t">{h["ts"]}</div>'
                    '</div>',
                    unsafe_allow_html=True,
                )
                if st.button(
                    "Re-run",
                    key=f"hist_rerun_{i_hist}_{h['ts']}",
                    use_container_width=True,
                ):
                    st.session_state.trigger = h["prompt"]
                    st.rerun()
            if st.button(":material/delete: Clear history",
                         use_container_width=True,
                         key="clear_history_btn"):
                st.session_state.query_history = []
                st.rerun()

    with st.expander(":material/settings: Settings"):
        st.slider(
            "Row limit",
            min_value=100, max_value=10_000,
            step=100, key="row_limit",
            help="Maximum rows to keep from each query result.",
        )
        st.toggle(
            "Suggest follow-up questions",
            key="show_followups",
            help="Generate 3 AI-suggested follow-ups after each answer.",
        )

    st.markdown('<div class="sb-section">Actions</div>', unsafe_allow_html=True)
    if st.button(":material/refresh: Clear conversation",
                 use_container_width=True,
                 key="clear_conversation_btn"):
        st.session_state.messages = []
        st.rerun()

    if st.session_state.messages:
        history_txt = "\n\n".join(
            f"{m['role'].upper()}: {m.get('content', '')}"
            + (f"\nSQL: {m['sql']}" if m.get("sql") else "")
            for m in st.session_state.messages
        )
        st.download_button(
            ":material/download: Export chat log",
            data=history_txt.encode("utf-8"),
            file_name="chat_log.txt", mime="text/plain",
            use_container_width=True,
            key="export_chat_log",
        )
        session_export = {
            "exported_at": datetime.now().isoformat(),
            "provider": st.session_state.provider,
            "model": st.session_state.model,
            "history": st.session_state.get("query_history", []),
            "messages": [
                {"role": m["role"], "content": m.get("content", ""),
                 "sql": m.get("sql"), "elapsed": m.get("elapsed")}
                for m in st.session_state.messages
            ],
        }
        st.download_button(
            ":material/data_object: Export session (JSON)",
            data=json.dumps(session_export, indent=2).encode("utf-8"),
            file_name="session.json", mime="application/json",
            use_container_width=True,
            key="export_session_json",
        )

        st.button(
        ":material/restart_alt: Reset settings",
        use_container_width=True,
        key="reset_settings_btn",
        on_click=_reset_settings,
        help="Restore default provider, model, and preferences.",
    )


# =============================================================================
# Main area
# =============================================================================
render_hero()

if not st.session_state.messages:
    render_empty_state()
else:
    for idx, msg in enumerate(st.session_state.messages):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg["role"] == "assistant" and msg.get("sql"):
                render_assistant_results(
                    msg["sql"],
                    msg.get("df"),
                    msg.get("elapsed", 0.0),
                    msg.get("suggestions"),
                    msg_idx=idx,
                )

render_footer()


# =============================================================================
# Chat input
# =============================================================================
prompt = st.chat_input("Ask a question about your data…")
if st.session_state.get("trigger"):
    prompt = st.session_state.pop("trigger")

if prompt:
    if not DB_PATH.exists():
        st.error("Database not found. Please run `python init_db.py` first.")
        st.stop()

    resolved_key, resolved_model, resolved_base_url = _resolve_credentials()
    if not resolved_key:
        st.error(
            "No API key found. Paste your key in the sidebar, "
            "or add it to `.streamlit/secrets.toml`."
        )
        st.stop()

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    process_question(
        prompt=prompt, api_key=resolved_key, model=resolved_model,
        base_url=resolved_base_url, messages=st.session_state.messages,
    )
    st.rerun()