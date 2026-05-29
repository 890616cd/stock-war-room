"""
app.py
美股投資戰情室 ── Streamlit UI 主程式

啟動方式：
  streamlit run app.py

需求：
  pip install streamlit yfinance anthropic requests feedparser python-dotenv plotly pandas numpy
"""

import os
import json
import streamlit as st
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── 頁面基本設定（必須在所有 st 呼叫前）──────────────────
st.set_page_config(
    page_title  = "美股投資戰情室",
    page_icon   = "⚔️",
    layout      = "wide",
    initial_sidebar_state = "collapsed",
)

# ── 全域 CSS（主題動態注入）────────────────────────────────
_thm = st.session_state.get("_theme", "light")
_dk  = _thm == "dark"

st.markdown(f"""
<style>
/* ═══ 隱藏 Streamlit 預設 Chrome ═══ */
[data-testid="stSidebar"]               {{ display:none!important; }}
[data-testid="stToolbarActions"]         {{ display:none!important; }}
header[data-testid="stHeader"]           {{ display:none!important; }}
button[data-testid="collapsedControl"]   {{ display:none!important; }}
#MainMenu                               {{ display:none!important; }}
footer                                  {{ display:none!important; }}

/* ═══ 主題色彩 CSS 變數 ═══ */
:root {{
    --surface:   {'#0F172A' if _dk else '#F8F9FA'};
    --card:      {'#1E293B' if _dk else '#FFFFFF'};
    --card2:     {'#243347' if _dk else '#F1F5F9'};
    --text:      {'#E2E8F0' if _dk else '#334155'};
    --muted:     {'#94A3B8' if _dk else '#64748B'};
    --border:    {'#334155' if _dk else '#E2E8F0'};
    --up:        #10B981;
    --down:      #EF4444;
    --brand:     #D4AF37;
    --shadow:    {'0 4px 20px -2px rgba(0,0,0,0.45)' if _dk else '0 4px 20px -2px rgba(0,0,0,0.05), 0 0 3px rgba(0,0,0,0.02)'};
    --navbar-bg: {'rgba(15,23,42,0.90)' if _dk else 'rgba(255,255,255,0.90)'};
}}

/* ═══ App 背景 ═══ */
.stApp, [data-testid="stAppViewContainer"],
section[data-testid="stMain"],
section[data-testid="stMain"] > div {{
    background-color: var(--surface) !important;
    color: var(--text) !important;
}}

/* ═══ 主內容區：讓出頂部導覽列空間 ═══ */
.block-container, [data-testid="stMainBlockContainer"] {{
    padding-top: 80px !important;
    max-width: 1100px !important;
    padding-left: 2rem !important;
    padding-right: 2rem !important;
}}

/* ═══ 固定頂部導覽列 ═══ */
.war-navbar {{
    position: fixed; top:0; left:0; right:0;
    height: 64px;
    background: var(--navbar-bg);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border-bottom: 1px solid var(--border);
    z-index: 999;
    display: flex; align-items: center;
    justify-content: space-between;
    padding: 0 28px;
    box-sizing: border-box;
}}
.nav-brand {{ display:flex; align-items:center; gap:10px; }}
.nav-logo {{
    width:36px; height:36px;
    background: {'#D4AF37' if _dk else '#1E293B'};
    border-radius: 10px;
    display:flex; align-items:center; justify-content:center;
    font-size:18px; line-height:1;
}}
.nav-title {{ font-size:17px; font-weight:700; color:var(--text); letter-spacing:.01em; }}
.nav-right {{ display:flex; align-items:center; gap:12px; }}
.nav-user  {{ display:flex; align-items:center; gap:8px; color:var(--muted); font-size:12px; }}

/* ═══ 導覽列按鈕：用 CSS 定位 Streamlit 按鈕至固定列右側 ═══ */
/* 隱藏哨兵佔位容器 */
div:has(> .nav-btn-sentinel) {{
    height:0!important; overflow:hidden!important;
    margin:0!important; padding:0!important;
}}
/* 哨兵後緊接的水平區塊 → 固定在導覽列右側 */
div:has(> .nav-btn-sentinel) + [data-testid="stHorizontalBlock"] {{
    position:fixed!important;
    top:10px!important; right:28px!important; left:auto!important;
    width:auto!important; min-width:0!important;
    z-index:1001!important;
    gap:2px!important; margin:0!important; padding:0!important;
    background:transparent!important;
    flex-wrap:nowrap!important;
    align-items:center!important;
}}
div:has(> .nav-btn-sentinel) + [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {{
    flex:none!important; min-width:0!important;
    padding:0!important; width:auto!important;
}}
/* 按鈕本體：透明背景，融入導覽列 */
div:has(> .nav-btn-sentinel) + [data-testid="stHorizontalBlock"] [data-testid="stButton"] button {{
    background:transparent!important;
    border:1px solid transparent!important;
    color:var(--text)!important;
    padding:4px 9px!important;
    font-size:15px!important;
    border-radius:8px!important;
    height:34px!important; min-height:34px!important;
    line-height:1!important;
    white-space:nowrap!important;
    box-shadow:none!important;
}}
div:has(> .nav-btn-sentinel) + [data-testid="stHorizontalBlock"] [data-testid="stButton"] button:hover {{
    background:{'rgba(255,255,255,0.12)' if _dk else 'rgba(0,0,0,0.06)'}!important;
    border-color:transparent!important;
}}
/* 登出按鈕：小字樣式 */
div:has(> .nav-btn-sentinel) + [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:last-child [data-testid="stButton"] button {{
    font-size:12px!important; font-weight:600!important;
    color:var(--muted)!important;
}}

/* ═══ KPI 指標卡片 ═══ */
[data-testid="stMetric"] {{
    background: var(--card) !important;
    border: 1px solid var(--border) !important;
    border-radius: 18px !important;
    padding: 14px 18px !important;
    box-shadow: var(--shadow) !important;
}}
[data-testid="stMetricLabel"] {{ font-size:11px!important; opacity:.65; text-transform:uppercase; letter-spacing:.5px; color:var(--text)!important; }}
[data-testid="stMetricValue"] {{ font-size:20px!important; font-weight:700; font-family:'Courier New',monospace; color:var(--text)!important; }}
[data-testid="stMetricDelta"] {{ font-size:12px!important; }}

/* ═══ 區塊容器 ═══ */
[data-testid="stVerticalBlockBorderWrapper"] {{
    background: var(--card) !important;
    border: 1px solid var(--border) !important;
    border-radius: 20px !important;
    padding: 20px !important;
    box-shadow: var(--shadow) !important;
}}

/* ═══ 警戒等級徽章 ═══ */
.alert-green  {{ color:#0a5c47; background:#d4f5e9; padding:5px 18px; border-radius:20px; font-weight:700; font-size:13px; display:inline-flex; align-items:center; gap:6px; border:1px solid #a8e6d3; }}
.alert-yellow {{ color:#7a4500; background:#fef3cd; padding:5px 18px; border-radius:20px; font-weight:700; font-size:13px; display:inline-flex; align-items:center; gap:6px; border:1px solid #fddfa0; }}
.alert-red    {{ color:#8b1a1a; background:#fde8e8; padding:5px 18px; border-radius:20px; font-weight:700; font-size:13px; display:inline-flex; align-items:center; gap:6px; border:1px solid #f5b7b7; }}
.alert-black  {{ color:#e8e8e8; background:#2c2c2c; padding:5px 18px; border-radius:20px; font-weight:700; font-size:13px; display:inline-flex; align-items:center; gap:6px; border:1px solid #555; }}

/* ═══ 觸發規則卡片 ═══ */
.rule-red  {{ border-left:3px solid #e24b4a; padding:8px 14px; margin:5px 0; background:#fff5f5; border-radius:0 8px 8px 0; font-size:13px; line-height:1.5; }}
.rule-yell {{ border-left:3px solid #f0a500; padding:8px 14px; margin:5px 0; background:#fffbf0; border-radius:0 8px 8px 0; font-size:13px; line-height:1.5; }}
.rule-blk  {{ border-left:3px solid #555;    padding:8px 14px; margin:5px 0; background:#f5f5f5; border-radius:0 8px 8px 0; font-size:13px; line-height:1.5; }}

/* ═══ 分隔線 ═══ */
hr {{ margin:14px 0!important; opacity:.2; border-color:var(--border); }}

/* ═══ 報告 Markdown ═══ */
.stMarkdown h2 {{ font-size:17px!important; margin-top:18px!important; padding-bottom:4px; border-bottom:1px solid var(--border); color:var(--text); }}
.stMarkdown h3 {{ font-size:15px!important; margin-top:14px!important; color:var(--text); }}
.stMarkdown p  {{ font-size:14px; line-height:1.7; color:var(--text); }}
.stMarkdown li {{ font-size:14px; line-height:1.6; color:var(--text); }}
.stMarkdown blockquote {{ border-left:3px solid #4A90E2; padding-left:12px; font-size:13px; }}

/* ═══ DataFrame ═══ */
[data-testid="stDataFrame"] {{ border-radius:12px!important; overflow:hidden!important; }}

/* ═══ Expander ═══ */
[data-testid="stExpander"] {{
    background: var(--card) !important;
    border: 1px solid var(--border) !important;
    border-radius: 14px !important;
}}
[data-testid="stExpander"] summary {{ color:var(--text)!important; }}

/* ═══ Input / Textarea ═══ */
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea {{
    background: var(--card2) !important;
    color: var(--text) !important;
    border-color: var(--border) !important;
    border-radius: 10px !important;
}}

/* ═══ Tabs ═══ */
.stTabs [data-baseweb="tab-list"] {{ gap:4px; background:transparent; }}
.stTabs [data-baseweb="tab"] {{ border-radius:8px 8px 0 0; color:var(--text); }}
.stTabs [data-baseweb="tab-panel"] {{ background:transparent; }}

/* ═══ Alert/Info boxes ═══ */
[data-testid="stAlert"] {{ border-radius:12px!important; }}

/* ═══ 深淺色：Widget 標籤、表單元件全套覆蓋 ═══ */
/* Widget label text */
[data-testid="stWidgetLabel"] p,
[data-testid="stWidgetLabel"] label,
[data-testid="stWidgetLabel"] span {{ color:var(--text)!important; }}

/* Caption / helper / info */
[data-testid="stCaptionContainer"] p,
small {{ color:var(--muted)!important; }}

/* Headings */
h1,h2,h3,h4,h5,h6,
[data-testid="stHeading"] h1,
[data-testid="stHeading"] h2,
[data-testid="stHeading"] h3 {{ color:var(--text)!important; }}

/* Number input */
[data-testid="stNumberInput"] input {{
    background:var(--card2)!important;
    color:var(--text)!important;
    border-color:var(--border)!important;
    border-radius:10px!important;
}}

/* Selectbox / multiselect trigger box */
[data-testid="stSelectbox"]   [data-baseweb="select"] > div,
[data-testid="stMultiSelect"] [data-baseweb="select"] > div {{
    background:var(--card2)!important;
    border-color:var(--border)!important;
    border-radius:10px!important;
}}
[data-testid="stSelectbox"]   [data-baseweb="select"] span,
[data-testid="stMultiSelect"] [data-baseweb="select"] span,
[data-testid="stSelectbox"]   [data-baseweb="select"] div[class],
[data-testid="stMultiSelect"] [data-baseweb="select"] div[class] {{ color:var(--text)!important; }}

/* Dropdown popup list */
[data-baseweb="popover"],
[data-baseweb="menu"] {{ background:var(--card)!important; border-color:var(--border)!important; }}
[data-baseweb="popover"] [role="option"],
[data-baseweb="menu"] li {{
    background:var(--card)!important;
    color:var(--text)!important;
}}
[data-baseweb="popover"] [role="option"]:hover,
[data-baseweb="menu"] li:hover {{ background:var(--card2)!important; }}
[data-baseweb="popover"] [aria-selected="true"] {{ background:var(--card2)!important; }}

/* Checkbox */
[data-testid="stCheckbox"] label,
[data-testid="stCheckbox"] span {{ color:var(--text)!important; }}

/* Radio */
[data-testid="stRadio"] label,
[data-testid="stRadio"] p {{ color:var(--text)!important; }}

/* Multiselect tag chips */
[data-testid="stMultiSelect"] [data-baseweb="tag"] {{
    background:var(--card2)!important;
    color:var(--text)!important;
}}

/* Secondary buttons */
[data-testid="stButton"] button:not([kind="primary"]):not(.stDownloadButton button) {{
    background:var(--card2)!important;
    color:var(--text)!important;
    border-color:var(--border)!important;
}}
[data-testid="stButton"] button:not([kind="primary"]):hover {{
    background:var(--border)!important;
}}

/* st.text / st.write paragraphs */
[data-testid="stText"] p {{ color:var(--text)!important; }}

/* Block container background (for with st.container) */
[data-testid="stVerticalBlock"] {{ color:var(--text); }}

/* Expander summary & inner text */
[data-testid="stExpander"] summary p,
[data-testid="stExpander"] summary span {{ color:var(--text)!important; }}
[data-testid="stExpander"] [data-testid="stMarkdownContainer"] p {{ color:var(--text)!important; }}

/* Tab labels */
.stTabs [data-baseweb="tab"] {{ color:var(--text)!important; }}
.stTabs [data-baseweb="tab"][aria-selected="true"] {{ color:var(--text)!important; border-bottom-color:var(--brand)!important; }}

/* ═══ Alert / Info / Warning / Error 文字 ═══ */
[data-testid="stAlert"] div, [data-testid="stAlert"] p,
[data-testid="stAlert"] span {{ color:inherit!important; }}
div[data-testid="stAlert"][role="alert"] {{
    background:{'rgba(250,200,50,0.12)' if _dk else '#fffbf0'}!important;
    border-color:{'#f0a500' if _dk else '#f0a500'}!important;
    color:{'#fde68a' if _dk else '#7a4500'}!important;
}}
div[data-testid="stAlert"][data-baseweb="notification"] {{
    background:{'rgba(59,130,246,0.12)' if _dk else '#eff6ff'}!important;
}}

/* ═══ Expander 標題列完整暗色 ═══ */
[data-testid="stExpander"] details summary {{
    background:{'#1E293B' if _dk else '#F8F9FA'}!important;
    color:var(--text)!important;
    border-radius:12px!important;
}}
[data-testid="stExpander"] details[open] summary {{
    border-radius:12px 12px 0 0!important;
}}
[data-testid="stExpander"] details summary:hover {{
    background:var(--card2)!important;
}}
[data-testid="stExpander"] details > div {{
    background:var(--card)!important;
    color:var(--text)!important;
    border-radius:0 0 12px 12px!important;
}}

/* ═══ DataFrame 表格完整暗色 ═══ */
[data-testid="stDataFrame"] iframe {{
    background:transparent!important;
    color-scheme:{'dark' if _dk else 'light'}!important;
}}
[data-testid="stDataFrame"] [data-testid="stDataFrameResizable"] {{
    background:var(--card)!important;
    border-color:var(--border)!important;
}}
/* glide-data-grid 格式覆蓋 */
.dvn-scroller {{ background:var(--card)!important; }}

/* ═══ Button 主色文字保護 ═══ */
[data-testid="stButton"] button[kind="primary"],
[data-testid="stButton"] button[data-testid="baseButton-primary"] {{
    background:{'#1E40AF' if _dk else '#1E40AF'}!important;
    color:#ffffff!important;
}}
/* 次要按鈕 hover 效果 */
[data-testid="stButton"] button:not([kind="primary"]):hover {{
    background:var(--card2)!important;
    border-color:var(--border)!important;
}}

/* ═══ 自訂資料表格（取代 st.dataframe，完整深淺色支援）═══ */
.data-tbl {{ width:100%; border-collapse:collapse; font-size:13px; }}
.data-tbl th {{
    background:var(--card2); color:var(--muted);
    font-weight:600; font-size:11px; text-transform:uppercase; letter-spacing:.5px;
    padding:8px 12px; text-align:left;
    border-bottom:2px solid var(--border);
}}
.data-tbl td {{
    padding:9px 12px; color:var(--text);
    border-bottom:1px solid var(--border);
    font-family:'Courier New',monospace; font-size:13px;
}}
.data-tbl tr:last-child td {{ border-bottom:none; }}
.data-tbl tr:hover td {{ background:var(--card2); transition:background .1s; }}
.data-tbl .up  {{ color:var(--up)!important; }}
.data-tbl .dn  {{ color:var(--down)!important; }}
.data-tbl .mut {{ color:var(--muted)!important; font-size:11px; }}

/* ═══ 手機響應式 ═══ */
@media (max-width: 768px) {{
    .block-container, [data-testid="stMainBlockContainer"] {{
        padding-left:1rem!important; padding-right:1rem!important;
        padding-top:72px!important;
    }}
    h1, [data-testid="stHeading"] h1 {{ font-size:20px!important; }}
    h2, [data-testid="stHeading"] h2 {{ font-size:17px!important; }}
    [data-testid="stMetricValue"] {{ font-size:16px!important; }}
    [data-testid="stMetricLabel"] {{ font-size:9px!important; }}
    [data-testid="stMetricDelta"] {{ font-size:11px!important; }}
    .stMarkdown p, .stMarkdown li {{ font-size:13px!important; }}
    [data-testid="stAlert"] {{ font-size:12px!important; padding:.55rem .75rem!important; }}
    [data-testid="stButton"] button {{ min-height:44px!important; }}
    .war-navbar {{ padding:0 16px; }}
    .nav-title {{ font-size:15px; }}
    .stTabs [data-baseweb="tab"] {{ font-size:11px!important; padding:6px 7px!important; white-space:nowrap; }}
    [data-testid="stDataFrame"] {{ overflow-x:auto!important; }}
    [data-testid="stExpander"] [data-testid="stHorizontalBlock"] {{ flex-wrap:nowrap!important; align-items:stretch!important; }}
    [data-testid="stExpander"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {{ min-width:0!important; overflow:hidden; }}
}}
@media (max-width: 768px) {{
    .stMarkdown table {{ display:block!important; overflow-x:auto!important; white-space:nowrap!important; font-size:12px!important; }}
}}
</style>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════
#  Session state 初始化
# ════════════════════════════════════════════════════════

_ALL_KEY_VARS = (
    "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY",
    "MARKETAUX_API_KEY", "FINNHUB_KEY", "FMP_KEY", "ALPHA_VANTAGE_KEY",
)

def _init_state():
    defaults = {
        "market_data":    None,
        "assessment":     None,
        "market_analysis": None,
        "last_run":       None,
        "running":        False,
        "run_step":       "",
        "selected_stock": None,
        "selected_models":     [],
        "custom_prompt":       "",
        "multi_reports":       {},
        "stock_multi_reports": {},
        # ── API 金鑰：Session 建立時從 os.environ（本機 .env）預載；
        #    雲端 os.environ 不含使用者金鑰，預載結果是空字串。
        #    之後只讀寫這個 dict，永遠不再碰 os.environ，
        #    確保每位使用者完全隔離。
        "session_keys": {k: os.getenv(k, "") for k in _ALL_KEY_VARS},
        "setup_done":       False,
        "_custom_sectors":  {},   # 使用者自訂板塊 {key → 名稱}，隨 watchlist 一起持久化
        # ── PIN 碼保護（雲端用）────────────────────────────────
        "_pin_unlocked":  False,  # 本次頁面訪問是否已解鎖
        "_pin_fernet":    None,   # 解鎖後的 Fernet 物件（用於加解密）
        "_prev_nav_page": "",     # 上一次的導覽頁面（用於偵測頁面切換）
        "_user_has_pin":  False,  # 使用者是否已設定 PIN
        # ── 深淺色模式 ──────────────────────────────────────
        "_theme":         "light", # "light" | "dark"
        # ── 頁面路由（取代 sidebar radio）──────────────────
        "nav_page":       "🏠 戰情室主控台",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()

# ── 顯示跨 rerun 的 Toast 訊息（如同步結果）────────────────
_pt = st.session_state.pop("_pending_toast", None)
if _pt:
    st.toast(_pt[0], icon=_pt[1])

# ── 中繼導覽：在 sidebar（radio）渲染前套用，避免 widget key 衝突 ──
if "_go_to_page" in st.session_state:
    st.session_state["nav_page"] = st.session_state.pop("_go_to_page")


# ════════════════════════════════════════════════════════
#  登入驗證（自定義 Google OAuth，不依賴 st.login / session cookie）
# ════════════════════════════════════════════════════════

import urllib.parse
import secrets as _secrets
import requests as _http

_APP_URL      = "https://stock-war-room-ikuxxykprqgetqxbmygt6p.streamlit.app"
_GOOGLE_AUTH  = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"
_GOOGLE_INFO  = "https://www.googleapis.com/oauth2/v2/userinfo"


def _google_client_id() -> str:
    try:
        return str(st.secrets["auth"]["google"]["client_id"])
    except Exception:
        return ""


def _google_client_secret() -> str:
    try:
        return str(st.secrets["auth"]["google"]["client_secret"])
    except Exception:
        return ""


def _build_google_auth_url() -> str:
    cid = _google_client_id()
    if not cid:
        return ""
    # CSRF 防護：隨機 state，存入 session 供 callback 驗證
    state = _secrets.token_urlsafe(16)
    st.session_state["_oauth_state"] = state
    params = {
        "client_id":     cid,
        "redirect_uri":  _APP_URL,
        "response_type": "code",
        "scope":         "openid email profile",
        "access_type":   "online",
        "prompt":        "select_account",
        "state":         state,
    }
    return _GOOGLE_AUTH + "?" + urllib.parse.urlencode(params)


def _exchange_google_code(code: str) -> dict:
    """用 authorization code 換取使用者資訊"""
    try:
        token_resp = _http.post(_GOOGLE_TOKEN, data={
            "client_id":     _google_client_id(),
            "client_secret": _google_client_secret(),
            "code":          code,
            "grant_type":    "authorization_code",
            "redirect_uri":  _APP_URL,
        }, timeout=10)
        token_data = token_resp.json()
        if "access_token" not in token_data:
            return {}
        user_resp = _http.get(_GOOGLE_INFO,
            headers={"Authorization": f"Bearer {token_data['access_token']}"},
            timeout=10)
        return user_resp.json()
    except Exception:
        return {}


# ── 處理 OAuth callback（Google 把 ?code= 附在網址上）──────
_qp = st.query_params
if "code" in _qp and not st.session_state.get("_oauth_user"):
    # ── CSRF 防護：驗證 state 參數 ────────────────────────
    # Streamlit 架構說明：OAuth redirect 回來時會建立新的 WebSocket session，
    # 導致 _oauth_state 必然為空。因此只在 state 存在時驗證（有 state 且不符才擋），
    # 無 state 則繼續流程（依賴 Google 的 client_secret 伺服器端驗證作為主要防護）。
    _expected_state = st.session_state.get("_oauth_state", "")
    _received_state = _qp.get("state", "")
    if _expected_state and _received_state != _expected_state:
        st.error("⚠️ 登入驗證失敗（state 不符），可能為 CSRF 攻擊，請重新整理頁面再試。")
        st.query_params.clear()
        st.stop()
    # ── 換取 token & 使用者資訊 ───────────────────────────
    with st.spinner("登入中，請稍候…"):
        _user_info = _exchange_google_code(_qp["code"])
    if _user_info.get("email") and _user_info.get("verified_email", False):
        st.session_state["_oauth_user"] = _user_info
        st.session_state.pop("_oauth_state", None)   # 用完即清除
        st.query_params.clear()
        st.rerun()
    elif _user_info.get("email") and not _user_info.get("verified_email", False):
        st.error("⚠️ 您的 Google 帳號信箱尚未驗證，請先至 Google 帳號設定完成信箱驗證後再登入。")
        st.query_params.clear()
        st.stop()
    else:
        st.error("⚠️ Google 登入失敗，請重試。")
        st.query_params.clear()
        st.stop()

# ── LINE 外部瀏覽器中繼站 ────────────────────────────────
# LINE 在外部瀏覽器開啟此 URL 後，直接顯示登入按鈕即可
# （此時已是 Safari/Chrome，Google OAuth 可正常執行）
elif "openExternalBrowser" in _qp and not st.session_state.get("_oauth_user"):
    _auth_url_ext = _build_google_auth_url()
    _ext_dk = st.session_state.get("_theme", "light") == "dark"
    _ext_bg  = "#1E293B" if _ext_dk else "#FFFFFF"
    _ext_bdr = "#334155" if _ext_dk else "#E2E8F0"
    _ext_txt = "#E2E8F0" if _ext_dk else "#334155"
    _ext_mut = "#94A3B8" if _ext_dk else "#64748B"
    st.markdown(f"""
<style>
.block-container {{ padding-top:0!important; max-width:100vw!important; padding-left:0!important; padding-right:0!important; }}
</style>
""", unsafe_allow_html=True)
    _ec1, _ec2, _ec3 = st.columns([1, 2, 1])
    with _ec2:
        st.markdown(f"""
<div style="background:{_ext_bg};border-radius:28px;padding:40px 36px 28px;border:1px solid {_ext_bdr};text-align:center;margin-top:12vh;">
    <div style="font-size:48px;margin-bottom:14px;">⚔️</div>
    <h1 style="font-size:22px;font-weight:700;margin:0 0 6px;color:{_ext_txt};">美股投資戰情室</h1>
    <p style="color:{_ext_mut};font-size:13px;margin-bottom:24px;">已切換至外部瀏覽器</p>
</div>""", unsafe_allow_html=True)
        if _auth_url_ext:
            st.info("✅ 請點下方按鈕以 Google 帳號登入", icon="📱")
            st.link_button("🔵　使用 Google 帳號登入", _auth_url_ext,
                           use_container_width=True, type="primary")
    st.stop()

# ── 導覽列快捷操作（query param 觸發）────────────────────
elif "nav_action" in _qp:
    _nav_act = _qp.get("nav_action", "")
    st.query_params.clear()
    if _nav_act == "theme":
        st.session_state["_theme"] = (
            "dark" if st.session_state.get("_theme", "light") == "light" else "light"
        )
    elif _nav_act == "logout":
        st.session_state.pop("_oauth_user", None)
        st.session_state["user_data_loaded"] = False
    elif _nav_act == "sync":
        try:
            from module_storage import save_user_data
            _uid_sync = st.session_state.get("_current_user_id_cache", "")
            if _uid_sync and save_user_data(_uid_sync):
                st.session_state["_pending_toast"] = ("✅ 已同步至雲端", "☁️")
            else:
                st.session_state["_pending_toast"] = ("⚠️ 同步失敗，請確認網路連線", "⚠️")
        except Exception as _se:
            st.session_state["_pending_toast"] = (f"⚠️ 同步失敗：{_se}", "⚠️")
    st.rerun()

# ── 未登入：顯示歡迎頁 ────────────────────────────────────
if not st.session_state.get("_oauth_user"):
    _auth_url = _build_google_auth_url()

    # ── 伺服器端偵測瀏覽器類型（st.context.headers，無需 JS）──
    import re as _re
    _is_inline_browser = False
    try:
        _ua = st.context.headers.get("User-Agent", "")
        _is_inline_browser = bool(_re.search(
            r"Line\/|FBAN|FBAV|Instagram", _ua, _re.I
        ))
    except Exception:
        pass  # 舊版 Streamlit 不支援 st.context，預設為外部瀏覽器

    _btn_url = (_APP_URL + "?openExternalBrowser=1") if _is_inline_browser else (_auth_url or "")

    # ── 登入頁：全版置中卡片設計 ──────────────────────────
    _login_dk = st.session_state.get("_theme", "light") == "dark"
    st.markdown(f"""
<style>
.block-container, [data-testid="stMainBlockContainer"] {{
    padding-top: 0 !important;
    max-width: 100vw !important;
    padding-left: 0 !important;
    padding-right: 0 !important;
}}
.stApp, [data-testid="stAppViewContainer"] {{
    background: {'linear-gradient(135deg,#070d1a 0%,#0F172A 100%)' if _login_dk else 'linear-gradient(135deg,#EEF2FF 0%,#F8F9FA 100%)'} !important;
}}
</style>
""", unsafe_allow_html=True)

    _lc1, _lc2, _lc3 = st.columns([1, 2, 1])
    with _lc2:
        _card_bg  = "#1E293B" if _login_dk else "#FFFFFF"
        _card_bdr = "#334155" if _login_dk else "#E2E8F0"
        _txt_col  = "#E2E8F0" if _login_dk else "#334155"
        _muted    = "#94A3B8" if _login_dk else "#64748B"
        _shadow   = "0 20px 60px rgba(0,0,0,0.4)" if _login_dk else "0 20px 60px rgba(0,0,0,0.1)"
        st.markdown(f"""
<div style="
    background:{_card_bg};
    border-radius:28px;
    padding:48px 40px 32px;
    border:1px solid {_card_bdr};
    box-shadow:{_shadow};
    text-align:center;
    margin-top:12vh;
">
    <div style="
        width:72px;height:72px;
        background:#1E293B;border-radius:18px;
        display:inline-flex;align-items:center;justify-content:center;
        font-size:36px;margin-bottom:20px;
        border:2px solid #D4AF37;
    ">⚔️</div>
    <h1 style="font-size:24px;font-weight:800;margin:0 0 6px;color:{_txt_col};letter-spacing:.01em;">美股投資戰情室</h1>
    <p style="color:{_muted};font-size:13px;margin-bottom:32px;line-height:1.6;">
        AI 副官系統 · 登入後資料自動同步<br>無需重複設定
    </p>
</div>
""", unsafe_allow_html=True)
        if _btn_url:
            st.link_button("🔵　使用 Google 帳號登入", _btn_url,
                           use_container_width=True, type="primary")
        else:
            st.error("OAuth 設定有誤，請確認 Streamlit Secrets 中的 [auth.google] 設定。")
        st.markdown(f"""
<div style="text-align:center;margin-top:16px;">
    <span style="color:{_muted};font-size:11px;line-height:1.9;">
        🔒 登入資訊僅用於識別身份，不儲存密碼<br>
        API 金鑰以加密方式存入資料庫，僅你本人可讀取
    </span>
</div>
""", unsafe_allow_html=True)
    st.stop()

# ── 已登入：取得使用者識別資料 ──────────────────────────
_oauth_user        = st.session_state["_oauth_user"]
_current_user_id   = _oauth_user.get("email", "unknown")
_current_user_name = _oauth_user.get("name", _current_user_id)
_current_user_pic  = _oauth_user.get("picture", None)

# ── 首次登入此 Session：從 Supabase 載入資料 ─────────────
st.session_state["_current_user_id_cache"] = _current_user_id
if not st.session_state.get("user_data_loaded"):
    try:
        from module_storage import load_user_data
        load_user_data(_current_user_id)
    except Exception as _e:
        st.session_state["user_data_loaded"] = True


# ════════════════════════════════════════════════════════
#  個股輕量報價抓取（yfinance 免費，TTL 5 分鐘快取）
# ════════════════════════════════════════════════════════

@st.cache_data(ttl=300, show_spinner=False)
def fetch_stock_quick(symbol: str, name: str):
    """從 yfinance 抓取個股報價＋估值，不依賴主分析流程。
    抓取失敗時丟 RuntimeError，讓 st.cache_data 不快取空結果，
    下次重試才能真正重新請求 yfinance。
    """
    from module1_data_fetcher import _fetch_ticker_data
    result = _fetch_ticker_data(symbol, name)
    if result is None:
        raise RuntimeError(f"yfinance 無法取得 {symbol} 資料")
    return result


def _is_cloud() -> bool:
    """偵測是否在 Streamlit Community Cloud 執行"""
    return bool(
        os.getenv("STREAMLIT_SHARING_MODE")
        or "/mount/src/" in str(Path(__file__).resolve())
    )


def _get_key(env_var: str) -> str:
    """
    讀取 API 金鑰：
      1. session_keys（使用者本次 session，完全隔離）
      2. st.secrets（部署者在 Streamlit Cloud 設定的預設值）
    永遠不讀 os.environ — 雲端 os.environ 是跨 session 共用的，
    一旦讀取可能拿到其他使用者的 Key。
    本機 .env 的值已在 _init_state() 預載進 session_keys，無需再讀。
    """
    session_val = st.session_state.get("session_keys", {}).get(env_var, "")
    if session_val:
        return session_val
    try:
        if env_var in st.secrets:
            return str(st.secrets[env_var])
    except Exception:
        pass
    return ""


def _save_api_key(env_var: str, value: str):
    """
    儲存 API Key：
      1. session_keys（永遠寫入，各使用者完全隔離，雲端唯一儲存位置）
      2. .env 檔（僅本機執行時持久化；不寫 os.environ，避免跨 session 污染）
    """
    # 1. Session state（雲端 & 本機都寫）
    if "session_keys" not in st.session_state:
        st.session_state["session_keys"] = {k: "" for k in _ALL_KEY_VARS}
    st.session_state["session_keys"][env_var] = value
    # 2. 本機：持久化到 .env（不寫 os.environ，session_keys 已足夠）
    if not _is_cloud():
        try:
            env_path = Path(__file__).parent / ".env"
            lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
            updated = False
            for i, line in enumerate(lines):
                if line.startswith(f"{env_var}="):
                    lines[i] = f"{env_var}={value}"
                    updated = True
                    break
            if not updated:
                lines.append(f"{env_var}={value}")
            env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        except (PermissionError, OSError):
            pass
    # 3. 雲端：自動同步到 Supabase（登入狀態才執行）
    _uid = st.session_state.get("_current_user_id_cache", "")
    if _uid:
        try:
            if _is_cloud() and st.session_state.get("_user_has_pin", False):
                from module_storage import save_api_keys_pin
                save_api_keys_pin(_uid)
            else:
                from module_storage import save_user_data
                save_user_data(_uid)
        except Exception:
            pass


def _delete_api_key(env_var: str):
    """清除指定的 API Key（session + .env + Supabase）"""
    if "session_keys" not in st.session_state:
        st.session_state["session_keys"] = {k: "" for k in _ALL_KEY_VARS}
    st.session_state["session_keys"][env_var] = ""
    if not _is_cloud():
        try:
            env_path = Path(__file__).parent / ".env"
            if env_path.exists():
                lines = env_path.read_text(encoding="utf-8").splitlines()
                for i, line in enumerate(lines):
                    if line.startswith(f"{env_var}="):
                        lines[i] = f"{env_var}="
                        break
                env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        except (PermissionError, OSError):
            pass
    _uid = st.session_state.get("_current_user_id_cache", "")
    if _uid:
        try:
            if _is_cloud() and st.session_state.get("_user_has_pin", False):
                from module_storage import save_api_keys_pin
                save_api_keys_pin(_uid)
            else:
                from module_storage import save_user_data
                save_user_data(_uid)
        except Exception:
            pass


def _validate_api_key(env_var: str, key: str) -> tuple:
    """
    驗證 API Key 是否有效且填入正確欄位。
    返回 (is_valid: bool, message: str)
    使用最小化 API 呼叫，盡量不消耗用量。
    """
    import requests as _vreq
    key = key.strip()
    if not key:
        return False, "請輸入 Key"
    try:
        # ── AI 模型 ──────────────────────────────────────
        if env_var == "ANTHROPIC_API_KEY":
            import anthropic as _ant
            _ant.Anthropic(api_key=key).models.list()
            return True, "✅ Anthropic 金鑰驗證成功"

        elif env_var == "OPENAI_API_KEY":
            from openai import OpenAI as _OAI
            _OAI(api_key=key).models.list()
            return True, "✅ OpenAI 金鑰驗證成功"

        elif env_var == "GOOGLE_API_KEY":
            import google.generativeai as _genai
            _genai.configure(api_key=key)
            list(_genai.list_models())
            return True, "✅ Google 金鑰驗證成功"

        # ── 財經資料 API ──────────────────────────────────
        elif env_var == "MARKETAUX_API_KEY":
            r = _vreq.get(
                "https://api.marketaux.com/v1/news/all",
                params={"api_token": key, "limit": 1},
                timeout=10
            )
            data = r.json()
            if r.status_code == 200 and "data" in data:
                return True, "✅ Marketaux 金鑰驗證成功"
            err_msg = data.get("error", {}).get("message", "金鑰無效或填錯欄位")
            return False, f"❌ Marketaux 驗證失敗：{err_msg}"

        elif env_var == "FINNHUB_KEY":
            r = _vreq.get(
                "https://finnhub.io/api/v1/quote",
                params={"symbol": "AAPL", "token": key},
                timeout=10
            )
            data = r.json()
            if r.status_code == 200 and data.get("c"):
                return True, "✅ Finnhub 金鑰驗證成功"
            if r.status_code == 401 or "error" in data:
                return False, "❌ Finnhub 金鑰無效，請確認是否填入正確欄位"
            return False, "❌ Finnhub 驗證失敗"

        elif env_var == "FMP_KEY":
            r = _vreq.get(
                "https://financialmodelingprep.com/api/v3/profile/AAPL",
                params={"apikey": key},
                timeout=10
            )
            data = r.json()
            if isinstance(data, list) and data:
                return True, "✅ FMP 金鑰驗證成功"
            if isinstance(data, dict) and "Error Message" in data:
                return False, "❌ FMP 金鑰無效，請確認是否填入正確欄位"
            return False, "❌ FMP 驗證失敗"

        elif env_var == "ALPHA_VANTAGE_KEY":
            r = _vreq.get(
                "https://www.alphavantage.co/query",
                params={"function": "GLOBAL_QUOTE", "symbol": "IBM", "apikey": key},
                timeout=10
            )
            data = r.json()
            if "Global Quote" in data and data["Global Quote"]:
                return True, "✅ Alpha Vantage 金鑰驗證成功"
            if "Information" in data or "Note" in data:
                # 達頻率限制但金鑰本身存在
                return True, "⚠️ Alpha Vantage 已達免費方案頻率上限，但金鑰有效"
            return False, "❌ Alpha Vantage 金鑰無效，請確認是否填入正確欄位"

    except Exception:
        return False, "❌ 驗證失敗：請確認網路連線或稍後再試"

    return False, "❌ 未知錯誤"


# ════════════════════════════════════════════════════════
#  首次使用導引彈窗
# ════════════════════════════════════════════════════════

@st.dialog("👋 歡迎使用美股投資戰情室")
def _show_onboarding():
    st.markdown("""
使用 AI 分析功能需要至少一組 **AI 模型 API 金鑰**。

| 模型 | 費用 | 說明 |
|---|---|---|
| 🟠 **Anthropic Claude** ⭐ 推薦 | 依用量計費 | 報告品質最佳 |
| 🟢 **OpenAI GPT-4o** | 依用量計費 | 可與 Claude 交叉驗證 |
| 🔴 **Google Gemini 2.0 Flash** | **免費方案可用** | 適合作為第二模型 |

所有模型均為 **選填**，設定其中一個即可開始使用。

---

財經報價已內建 **Yahoo Finance 免費源**，不設定任何金鑰也能抓取股價數據。
FMP、Finnhub、Marketaux 為選填擴充，提供更完整的估值與新聞資料。

> 💡 點擊「前往設定」在教學指南直接輸入金鑰，儲存後立即生效。
    """)
    st.divider()
    c1, c2 = st.columns(2)
    if c1.button("🔑 前往 API 金鑰設定", type="primary", use_container_width=True):
        st.session_state["setup_done"]  = True
        st.session_state["_go_to_page"] = "📚 教學 & API設定"
        st.rerun()
    if c2.button("稍後再說", use_container_width=True):
        st.session_state["setup_done"] = True
        st.rerun()


# ════════════════════════════════════════════════════════
#  Watchlist 工具（直接讀寫 JSON，不依賴 CLI）
# ════════════════════════════════════════════════════════

WATCHLIST_FILE = Path(__file__).parent / "watchlist.json"
SECTOR_LABELS = {
    "semiconductor": "半導體",
    "tech":          "大型科技",
    "finance":       "金融 / 銀行",
    "energy":        "能源 / 大宗商品",
    "defense":       "國防 / 航太",
    "consumer":      "消費 / 零售",
    "etf":           "ETF / 指數基金",
}
MAX_SECTORS = 20   # 預設 7 + 自訂最多 13，合計不超過此值


def get_sector_label(key: str) -> str:
    """取得板塊顯示名稱（自訂板塊優先；內建其次；最後回傳 key 本身）"""
    custom = st.session_state.get("_custom_sectors", {})
    if key in custom:
        return custom[key]
    return SECTOR_LABELS.get(key, key)


def get_all_sector_keys() -> list:
    """返回全部板塊 key（預設 7 + 使用者自訂）"""
    custom = st.session_state.get("_custom_sectors", {})
    return list(SECTOR_LABELS.keys()) + list(custom.keys())


def _sync_custom_sectors_from_wl(data: dict):
    """從 _wl_data 的 _custom_sectors 欄位載入自訂板塊定義到 session state"""
    cs = data.get("_custom_sectors")
    if isinstance(cs, dict):
        st.session_state["_custom_sectors"] = cs
    elif "_custom_sectors" not in st.session_state:
        st.session_state["_custom_sectors"] = {}


def _wl_has_stocks(data: dict) -> bool:
    """data 中是否有實際股票（排除 _custom_sectors 元數據）"""
    return any(
        bool(v)
        for k, v in data.items()
        if k != "_custom_sectors" and isinstance(v, dict)
    )


def load_wl() -> dict:
    """
    讀取自選股清單。
    - 本機：優先 session state（有股票時）；否則從 watchlist.json 讀取
    - 雲端：每個使用者的 session state 即為其個人清單
    自訂板塊定義存在 data["_custom_sectors"] 裡，與清單一起持久化。
    """
    # session state 有資料且實際有股票 → 直接用（雲端主路徑；本機快取）
    if "_wl_data" in st.session_state and _wl_has_stocks(st.session_state["_wl_data"]):
        data = st.session_state["_wl_data"]
        _sync_custom_sectors_from_wl(data)
        for s in get_all_sector_keys():
            data.setdefault(s, {})
        return data
    # 本機：從檔案載入（含 session state 為空時的 fallback）
    if not _is_cloud() and WATCHLIST_FILE.exists():
        try:
            with open(WATCHLIST_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            _sync_custom_sectors_from_wl(data)
            for s in get_all_sector_keys():
                data.setdefault(s, {})
            st.session_state["_wl_data"] = data
            return data
        except Exception:
            pass
    # 雲端：session state 無股票（Supabase 空資料）→ 直接用空 session state
    if "_wl_data" in st.session_state:
        data = st.session_state["_wl_data"]
        _sync_custom_sectors_from_wl(data)
        for s in get_all_sector_keys():
            data.setdefault(s, {})
        return data
    # 預設空清單
    empty = {s: {} for s in SECTOR_LABELS}
    empty["_custom_sectors"] = {}
    st.session_state["_custom_sectors"] = {}
    st.session_state["_wl_data"] = empty
    return empty

def save_wl(data: dict):
    """
    儲存自選股清單。
    - 永遠更新 session state（即時生效）
    - 本機另外寫入 watchlist.json（持久化）；雲端略過
    """
    st.session_state["_wl_data"] = data
    if not _is_cloud():
        try:
            with open(WATCHLIST_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except (PermissionError, OSError):
            pass

def _cloud_sync_wl():
    """自選股變更後自動同步至 Supabase"""
    uid = st.session_state.get("_current_user_id_cache", "")
    if uid:
        try:
            from module_storage import save_user_data
            save_user_data(uid)
        except Exception:
            pass


def _save_custom_sectors():
    """將 _custom_sectors 寫回 _wl_data 並持久化"""
    data = load_wl()
    data["_custom_sectors"] = st.session_state.get("_custom_sectors", {})
    save_wl(data)
    _cloud_sync_wl()


def custom_sector_add(label: str) -> str:
    """新增自訂板塊，返回結果訊息"""
    label = label.strip()
    if not label:
        return "⚠️ 請輸入板塊名稱"
    custom = st.session_state.setdefault("_custom_sectors", {})
    if len(SECTOR_LABELS) + len(custom) >= MAX_SECTORS:
        return f"⚠️ 已達板塊上限（{MAX_SECTORS} 個），請先刪除不需要的板塊"
    all_labels = list(SECTOR_LABELS.values()) + list(custom.values())
    if label in all_labels:
        return f"⚠️ 板塊名稱「{label}」已存在"
    import time as _time
    key = f"cs_{int(_time.time() * 1000)}"
    custom[key] = label
    data = load_wl()
    data[key] = {}
    data["_custom_sectors"] = custom
    save_wl(data)
    _cloud_sync_wl()
    return f"✅ 已新增板塊「{label}」"


def custom_sector_delete(key: str) -> str:
    """刪除自訂板塊（板塊內有股票時拒絕），返回結果訊息"""
    custom = st.session_state.get("_custom_sectors", {})
    label  = custom.get(key, key)
    data   = load_wl()
    stocks = data.get(key, {})
    if stocks:
        return f"⚠️ 板塊「{label}」中還有 {len(stocks)} 檔股票，請先全部移除後再刪除板塊"
    custom.pop(key, None)
    data.pop(key, None)
    data["_custom_sectors"] = custom
    st.session_state["_custom_sectors"] = custom
    save_wl(data)
    _cloud_sync_wl()
    return f"✅ 已刪除板塊「{label}」"

def wl_add(symbol: str, name: str, sector: str) -> str:
    data = load_wl()
    sym  = symbol.upper().strip()
    display_name = name.strip() or sym   # 未填名稱時以代號作顯示名
    for sec, stocks in data.items():
        if sec == "_custom_sectors" or not isinstance(stocks, dict):
            continue
        if sym in stocks:
            if sec == sector:
                return f"⚠️ {sym} 已在「{get_sector_label(sec)}」板塊中"
            del stocks[sym]
            break
    data[sector][sym] = display_name
    save_wl(data)
    _cloud_sync_wl()
    return f"✅ {sym}（{display_name}）已加入【{get_sector_label(sector)}】"

def wl_remove(symbol: str) -> str:
    data = load_wl()
    sym  = symbol.upper().strip()
    for sec, stocks in data.items():
        if sec == "_custom_sectors" or not isinstance(stocks, dict):
            continue
        if sym in stocks:
            name = stocks.pop(sym)
            save_wl(data)
            _cloud_sync_wl()
            return f"✅ 已移除 {sym}（{name}）"
    return f"⚠️ {sym} 不在清單中"

def wl_total(data: dict) -> int:
    return sum(len(v) for k, v in data.items() if k != "_custom_sectors" and isinstance(v, dict))


# ════════════════════════════════════════════════════════
#  分析執行（串接五個模組）
# ════════════════════════════════════════════════════════

def run_full_analysis(prog=None):
    """
    依序執行模組一 → 模組二 → 模組三。
    進度更新寫入 session_state.run_step；若傳入 prog 則同步更新 Streamlit 進度條。
    """
    def _upd(pct: int, txt: str):
        st.session_state["run_step"] = txt
        if prog is not None:
            prog.progress(pct, text=txt)

    try:
        from module1_data_fetcher import run_data_fetcher
        from module2_discipline_warning import (
            DisciplineWarningProtocol, MarketSnapshot,
            format_emergency_output,
        )
        from module3_llm_summarizer import run_llm_summarizer

        # ── Module 1 ──
        _upd(5, "📡 正在抓取大盤指數 / VIX / US10Y / DXY 及三大類別新聞...")
        market_data = run_data_fetcher()
        st.session_state["market_data"] = market_data

        # ── Module 2 ──
        _upd(65, "🔒 執行紀律警告協議（硬邏輯評估中）...")
        snapshot = MarketSnapshot(
            vix               = market_data.vix,
            us10y             = market_data.us10y,
            sp500             = market_data.sp500,
            sp500_prev_close  = market_data.sp500_prev,
            nasdaq            = market_data.nasdaq,
            nasdaq_prev_close = market_data.nasdaq_prev,
        )
        assessment = DisciplineWarningProtocol(snapshot).run()
        st.session_state["assessment"] = assessment

        # ── Module 3：多模型市場分析 ──────────────────────
        if not assessment.should_block_llm:
            from module3_llm_summarizer import (
                build_system_prompt, build_user_prompt,
                call_model, format_final_report, MODEL_CATALOG,
            )
            custom_p  = st.session_state.get("custom_prompt", "")
            sel_models = st.session_state.get("selected_models", [])
            sys_p  = build_system_prompt(assessment, market_data, custom_p)
            user_p = build_user_prompt(market_data)
            multi: dict = {}
            for i, mid in enumerate(sel_models):
                lbl = MODEL_CATALOG.get(mid, {}).get("label", mid)
                pct = 72 + int(i / max(len(sel_models), 1) * 23)
                _upd(pct, f"🤖 {lbl} 生成市場情緒分析...")
                res = call_model(mid, sys_p, user_p)
                if not res.get("error"):
                    res["report"] = format_final_report(res["text"], assessment, market_data)
                multi[mid] = res
            st.session_state["multi_reports"]   = multi
            # 向後相容：market_analysis 指向第一個成功結果
            first = next((r["report"] for r in multi.values() if not r.get("error")), None)
            st.session_state["market_analysis"] = first
        else:
            from module2_discipline_warning import format_emergency_output
            st.session_state["market_analysis"] = format_emergency_output(assessment)
            st.session_state["multi_reports"]   = {}

        st.session_state["last_run"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        _upd(100, "✅ 分析完成")

    except Exception as e:
        import logging as _logging
        _logging.error("run_full_analysis failed", exc_info=True)
        st.session_state["run_step"] = "❌ 執行失敗，請稍後重試"
        st.session_state["report"]   = "**系統錯誤**\n\n請確認 API 金鑰設定是否正確後重試。若問題持續，請聯繫管理員。"



# ════════════════════════════════════════════════════════
#  個股詳細頁面
# ════════════════════════════════════════════════════════

def _html_table(rows: list[list], headers: list[str]) -> str:
    """產生完整尊重 CSS 變數的 HTML 表格（取代 st.dataframe）"""
    th = "".join(f"<th>{h}</th>" for h in headers)
    tbody = ""
    for row in rows:
        cells = ""
        for i, cell in enumerate(row):
            s = str(cell)
            cls = ""
            if i > 0:  # 數值欄位套色
                if s.startswith("+"):   cls = ' class="up"'
                elif s.startswith("-"): cls = ' class="dn"'
                elif s in ("N/A", "—"): cls = ' class="mut"'
            cells += f"<td{cls}>{s}</td>"
        tbody += f"<tr>{cells}</tr>"
    return f'<table class="data-tbl"><thead><tr>{th}</tr></thead><tbody>{tbody}</tbody></table>'


def render_stock_detail(symbol: str, name: str):
    """個股詳細頁面：K線圖 + 估值指標 + 近期新聞（獨立於主分析運行）"""
    from module_stock_chart import fetch_chart_data, build_stock_chart

    # ── 重新整理按鈕（浮在右側）──────────────────────────
    _, _rf_col = st.columns([8, 2])
    if _rf_col.button("🔄 重新整理", type="secondary", key="sd_refresh", use_container_width=True):
        fetch_stock_quick.clear()
        st.rerun()

    # ── 優先使用主分析快取；沒有則直接從 yfinance 抓 ────────
    md = st.session_state.get("market_data")
    stock = None
    if md and md.watchlist:
        for sector_stocks in md.watchlist.values():
            for s in sector_stocks:
                if s.symbol == symbol:
                    stock = s
                    break

    if stock is None:
        with st.spinner(f"正在載入 {symbol} 報價數據..."):
            try:
                stock = fetch_stock_quick(symbol, name)
            except Exception:
                stock = None

    if stock is None:
        st.warning(f"⚠️ Yahoo Finance 目前限速（Too Many Requests），暫時無法取得 {symbol} 詳細數據。請稍等 1～2 分鐘後點擊「🔄 重新整理數據」重試。")
        return

    # ── 股票標題與報價 ────────────────────────────────────
    import html as _sd_html
    _sd_dk = st.session_state.get("_theme", "light") == "dark"
    _price_color = "#10B981" if stock.change_pct >= 0 else "#EF4444"
    _chg_sign    = "+" if stock.change_pct >= 0 else ""
    _sd_txt  = "#E2E8F0" if _sd_dk else "#334155"
    _sd_muted= "#94A3B8" if _sd_dk else "#64748B"
    _safe_name = _sd_html.escape(str(stock.name))
    _safe_sym  = _sd_html.escape(str(stock.symbol))
    st.markdown(f"""
<div style="display:flex;justify-content:space-between;align-items:flex-end;flex-wrap:wrap;gap:12px;margin-bottom:24px;">
    <div>
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:4px;">
            <h1 style="font-size:36px;font-weight:800;margin:0;color:{_sd_txt};">{_safe_sym}</h1>
            <span style="font-size:18px;color:{_sd_muted};">{_safe_name}</span>
        </div>
        <div style="font-size:12px;color:{_sd_muted};">資料來源：Yahoo Finance · {datetime.now().strftime('%Y-%m-%d')}</div>
    </div>
    <div style="text-align:right;">
        <div style="font-size:38px;font-weight:800;font-family:'Courier New',monospace;color:{_price_color};">${stock.price:,.2f}</div>
        <div style="font-size:16px;font-weight:600;color:{_price_color};">{_chg_sign}{stock.change_pct:.2f}%</div>
    </div>
</div>
""", unsafe_allow_html=True)

    import pandas as pd

    # ── K 線圖（標題 + 股價之後即呈現）──────────────────────
    st.markdown("#### 📈 技術分析圖表（近一年日K）")
    st.caption("📡 資料來源：Yahoo Finance（yfinance）")
    with st.spinner(f"正在載入 {stock.symbol} 圖表數據..."):
        df  = fetch_chart_data(stock.symbol, period="1y")
        from module_stock_chart import build_macd_chart, build_kdj_chart, build_rsi_chart
        fig = build_stock_chart(df, stock.symbol, stock.name)
    # 深色模式：更新圖表樣式
    _is_dk_chart = st.session_state.get("_theme", "light") == "dark"
    if _is_dk_chart:
        _dk_layout = dict(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(15,23,42,0.4)",
            font=dict(color="#94A3B8"),
            xaxis=dict(gridcolor="rgba(51,65,85,0.5)", linecolor="rgba(51,65,85,0.4)",
                       tickfont=dict(color="#94A3B8")),
            yaxis=dict(gridcolor="rgba(51,65,85,0.5)", linecolor="rgba(51,65,85,0.4)",
                       tickfont=dict(color="#94A3B8")),
            legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color="#94A3B8")),
        )
        fig.update_layout(**_dk_layout)
    _chart_cfg = {
        "scrollZoom":     True,
        "displayModeBar": True,
        "modeBarButtonsToRemove": ["lasso2d", "select2d"],
        "modeBarButtonsToAdd":    ["toggleSpikelines"],
    }
    st.plotly_chart(fig, use_container_width=True, config=_chart_cfg)
    st.caption("💡 拖拽右側刻度可縮放 y 軸區間；滾輪縮放時間區間；雙擊還原視圖。")

    # ── 技術指標（可摺疊）──────────────────────────────────
    if not df.empty:
        def _apply_dk(f):
            if _is_dk_chart:
                f.update_layout(**_dk_layout)
            return f
        with st.expander("📉 MACD（12, 26, 9）", expanded=False):
            st.plotly_chart(_apply_dk(build_macd_chart(df)), use_container_width=True,
                            config=_chart_cfg)
        with st.expander("📊 KDJ（9, 3, 3）", expanded=False):
            st.plotly_chart(_apply_dk(build_kdj_chart(df)), use_container_width=True,
                            config=_chart_cfg)
        with st.expander("📈 RSI（6, 12, 24）", expanded=False):
            st.plotly_chart(_apply_dk(build_rsi_chart(df)), use_container_width=True,
                            config=_chart_cfg)

    st.divider()

    # ════════════════════════════════════════════════════
    #  技術分析面
    # ════════════════════════════════════════════════════
    st.markdown("#### 📊 技術分析面")
    st.caption("📡 資料來源：Yahoo Finance（yfinance）")

    def _fmt_vol(v):
        if not v: return "N/A"
        if v >= 1_000_000_000: return f"{v/1e9:.2f} B"
        if v >= 1_000_000:     return f"{v/1e6:.2f} M"
        return f"{v:,.0f}"

    # 技術分析面：估值標籤（依獲利與否切換 P/E 或 P/S）
    if stock.is_profitable:
        _cur_val_label  = "當前 F P/E"
        _hist_val_label = "3年均值 F P/E"
        _cur_val  = f"{stock.forward_pe:.1f}x"  if stock.forward_pe  else "N/A"
        _hist_val = f"{stock.pe_3y_avg:.1f}x"   if stock.pe_3y_avg   else "N/A"
    else:
        _cur_val_label  = "當前 F P/S"
        _hist_val_label = "Trailing P/S"
        _cur_val  = f"{stock.forward_ps:.2f}x"  if stock.forward_ps  else "N/A"
        _hist_val = f"{stock.trailing_ps:.2f}x" if stock.trailing_ps else "N/A"

    col_t1, col_t2 = st.columns(2)
    with col_t1:
        st.caption("價格 / 波動 / 估值")
        st.markdown(_html_table(
            headers=["指標", "數值"],
            rows=[
                ["開盤價",          f"${stock.open_price:,.2f}"  if stock.open_price  else "N/A"],
                ["最高價",          f"${stock.high_price:,.2f}"  if stock.high_price  else "N/A"],
                ["最低價",          f"${stock.low_price:,.2f}"   if stock.low_price   else "N/A"],
                ["收盤價",          f"${stock.price:,.2f}"],
                ["Beta（相對大盤波動）", f"{stock.beta:.2f}"     if stock.beta        else "N/A"],
                [_cur_val_label,    _cur_val],
                [_hist_val_label,   _hist_val],
            ]
        ), unsafe_allow_html=True)
    with col_t2:
        st.caption("成交量 / 52週區間")
        _pct_hi = f"{stock.pct_from_52w_high:.1f}%"
        st.markdown(_html_table(
            headers=["指標", "數值"],
            rows=[
                ["成交量",       _fmt_vol(stock.volume)],
                ["均量（10日）", _fmt_vol(stock.avg_volume)],
                ["量比",         f"{stock.volume_ratio:.2f} 倍"],
                ["52週高點",     f"${stock.week52_high:,.2f}"],
                ["52週低點",     f"${stock.week52_low:,.2f}"],
                ["距52週高",     _pct_hi],
                ["52週區間位置", f"{stock.range_position:.0f}%"],
            ]
        ), unsafe_allow_html=True)

    st.divider()

    # ════════════════════════════════════════════════════
    #  估值分析面
    # ════════════════════════════════════════════════════
    st.markdown("#### 💹 估值分析面")
    st.caption("📡 資料來源：FMP（多年 EPS / F P/E / 成長率預估，優先）· Yahoo Finance（備援）")

    def _fmt_pct(v):
        if v is None: return "N/A"
        return f"+{v:.1f}%" if v >= 0 else f"{v:.1f}%"

    # ── 多年 Forward P/E 或 P/S + 成長率表格 ─────────────
    pe_label = "Forward P/E" if stock.is_profitable else "Forward P/S"
    if stock.is_profitable:
        pe_disp = [
            f"{stock.fpe_2026:.1f}x" if stock.fpe_2026 else "N/A",
            f"{stock.fpe_2027:.1f}x" if stock.fpe_2027 else "N/A",
            f"{stock.fpe_2028:.1f}x" if stock.fpe_2028 else "N/A",
        ]
    else:
        pe_disp = [
            f"{stock.fps_2026:.2f}x" if stock.fps_2026 else "N/A",
            f"{stock.fps_2027:.2f}x" if stock.fps_2027 else "N/A",
            f"{stock.fps_2028:.2f}x" if stock.fps_2028 else "N/A",
        ]

    def _fmt_eps(v):
        return f"${v:.2f}" if v is not None else "N/A"

    st.markdown(_html_table(
        headers=["財年", "預估 EPS", pe_label, "年營收成長率", "EPS 年成長率"],
        rows=[
            ["2026",
             _fmt_eps(stock.eps_est_2026), pe_disp[0],
             _fmt_pct(stock.rev_growth_2026), _fmt_pct(stock.eps_growth_2026)],
            ["2027",
             _fmt_eps(stock.eps_est_2027), pe_disp[1],
             _fmt_pct(stock.rev_growth_2027), _fmt_pct(stock.eps_growth_2027)],
            ["2028（通常無數據）",
             _fmt_eps(stock.eps_est_2028), pe_disp[2],
             _fmt_pct(stock.rev_growth_2028), _fmt_pct(stock.eps_growth_2028)],
        ]
    ), unsafe_allow_html=True)

    # ── 分析師推薦分布（Finnhub）─────────────────────────
    has_rec = any(v is not None for v in [
        stock.rec_strong_buy, stock.rec_buy, stock.rec_hold,
        stock.rec_sell, stock.rec_strong_sell
    ])
    if has_rec:
        st.markdown("**📊 分析師推薦分布（Finnhub 最新一期）**")
        total_buy  = (stock.rec_strong_buy or 0) + (stock.rec_buy or 0)
        total_hold = stock.rec_hold or 0
        total_sell = (stock.rec_sell or 0) + (stock.rec_strong_sell or 0)
        total_all  = total_buy + total_hold + total_sell or 1
        rc1, rc2, rc3, rc4, rc5 = st.columns(5)
        rc1.metric("強力買入", stock.rec_strong_buy or 0,
                   f"{(stock.rec_strong_buy or 0)/total_all*100:.0f}%")
        rc2.metric("買入",    stock.rec_buy or 0,
                   f"{(stock.rec_buy or 0)/total_all*100:.0f}%")
        rc3.metric("持有",    stock.rec_hold or 0,
                   f"{(stock.rec_hold or 0)/total_all*100:.0f}%")
        rc4.metric("賣出",    stock.rec_sell or 0,
                   f"{(stock.rec_sell or 0)/total_all*100:.0f}%")
        rc5.metric("強力賣出", stock.rec_strong_sell or 0,
                   f"{(stock.rec_strong_sell or 0)/total_all*100:.0f}%")
        buy_pct = total_buy / total_all * 100
        bull_bar = "▓" * int(buy_pct / 5) + "░" * (20 - int(buy_pct / 5))
        st.caption(f"買進偏向：{bull_bar}  {buy_pct:.0f}% 買入 | {total_hold/total_all*100:.0f}% 持有 | {total_sell/total_all*100:.0f}% 賣出")

    st.divider()

    # ── 分析師目標價 ──────────────────────────────────────
    analyst_label = "📌 分析師目標價"
    if stock.analyst_count:
        analyst_label += f"　（共 {stock.analyst_count} 位分析師）"
    st.markdown(f"**{analyst_label}**")
    st.caption("📡 資料來源：Yahoo Finance（yfinance）")

    has_target = any([stock.target_low, stock.target_median,
                      stock.target_mean, stock.target_high])
    if has_target:
        tc1, tc2, tc3, tc4 = st.columns(4)
        def _tgt_delta(tgt):
            if not tgt: return None
            d = (tgt - stock.price) / stock.price * 100
            return f"{'+' if d>=0 else ''}{d:.1f}%"
        tc1.metric("目標最低", f"${stock.target_low:,.2f}"    if stock.target_low    else "N/A",
                   _tgt_delta(stock.target_low))
        tc2.metric("目標中位", f"${stock.target_median:,.2f}" if stock.target_median else "N/A",
                   _tgt_delta(stock.target_median))
        tc3.metric("目標平均", f"${stock.target_mean:,.2f}"   if stock.target_mean   else "N/A",
                   _tgt_delta(stock.target_mean))
        tc4.metric("目標最高", f"${stock.target_high:,.2f}"   if stock.target_high   else "N/A",
                   _tgt_delta(stock.target_high))
    else:
        st.caption("暫無分析師目標價數據")

    # ── AI 戰術建議 + 近期焦點新聞分析（單次 LLM 呼叫）──
    st.divider()

    assessment = st.session_state.get("assessment")
    md_data    = st.session_state.get("market_data")
    tactic_key = f"tactic_{stock.symbol}"
    news_key_s = f"news_{stock.symbol}"   # 快取個股新聞列表（供顯示用）

    if tactic_key not in st.session_state:
        st.session_state[tactic_key] = None
    if news_key_s not in st.session_state:
        st.session_state[news_key_s] = None

    if not assessment or not md_data:
        st.info("💡 AI 戰術建議需要大盤數據做市場背景，請先在戰情室主控台執行「啟動完整分析」後再生成。（K線圖與估值已獨立載入，不受影響）")
    elif st.session_state[tactic_key]:
        # ── 已生成：顯示結果（支援多模型）──────────
        cached = st.session_state[tactic_key]
        if isinstance(cached, dict):
            valid_r = {mid: r for mid, r in cached.items() if not r.get("error")}
            for mid, r in cached.items():
                if r.get("error"):
                    st.error(f"⚠️ {r.get('label', mid)} 生成失敗：{r['error']}")
            if valid_r:
                if len(valid_r) == 1:
                    mid, r = next(iter(valid_r.items()))
                    st.caption(f"{r.get('icon','🤖')} **{r.get('label')}** · ⏱ {r.get('elapsed_sec')}s · 輸入 {r.get('input_tokens',0):,} / 輸出 {r.get('output_tokens',0):,} tokens")
                    st.markdown(r.get("text", ""))
                else:
                    tab_labels = [f"{r.get('icon','🤖')} {r.get('label', mid)}" for mid, r in valid_r.items()]
                    tabs = st.tabs(tab_labels)
                    for tab, (mid, r) in zip(tabs, valid_r.items()):
                        with tab:
                            c1, c2, c3 = st.columns(3)
                            c1.metric("⏱ 生成時間", f"{r.get('elapsed_sec','?')} 秒")
                            c2.metric("📥 輸入", f"{r.get('input_tokens',0):,}")
                            c3.metric("📤 輸出", f"{r.get('output_tokens',0):,}")
                            st.markdown(r.get("text", ""))
        else:
            st.markdown(cached)  # 向後相容舊字串格式
        if st.button("🔄 重新生成", key=f"regen_{stock.symbol}", type="secondary"):
            st.session_state[tactic_key] = None
            st.session_state[news_key_s] = None
            st.rerun()
    else:
        # ── 尚未生成：顯示生成按鈕 + 立即抓新聞預覽 ──
        st.markdown("#### 🎯 AI 投資戰術建議 ＆ 📰 近期焦點新聞分析")
        st.caption("點擊下方按鈕，一次生成：操作方向、關鍵價位、風險提示，及近期新聞的影響與分析。")

        if st.button(
            f"🤖 生成 {stock.symbol} 完整分析",
            type = "primary",
            key  = f"gen_{stock.symbol}",
        ):
            import requests as _req, feedparser as _fp, re, email.utils
            from datetime import timedelta

            st.toast(f"⏳ 正在生成 {stock.symbol} 分析，請稍候 20–45 秒…", icon="🔄")
            _sprog = st.progress(0, text=f"📰 正在搜尋 {stock.symbol} 近期新聞...")

            # ── Step 1：抓取個股近 3 日新聞 ────────────
            fetched_news = []

            # 先從快取找
            if md_data and md_data.news_by_category:
                for items in md_data.news_by_category.values():
                    for item in items:
                        if stock.symbol in item.related_tickers:
                            fetched_news.append({
                                "title":   item.title,
                                "source":  item.source,
                                "url":     item.url,
                                "date":    item.published_at,
                                "summary": item.summary or "",
                            })

            # 快取不足時即時抓取
            if len(fetched_news) < 3:
                mktx_key = _get_key("MARKETAUX_API_KEY")
                since    = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%dT%H:%M")

                if mktx_key:
                    try:
                        resp = _req.get(
                            "https://api.marketaux.com/v1/news/all",
                            params = {
                                "api_token":      mktx_key,
                                "symbols":        stock.symbol,
                                "language":       "en",
                                "limit":          10,
                                "published_after": since,
                            },
                            timeout = 12,
                        )
                        if resp.ok:
                            for a in resp.json().get("data", []):
                                fetched_news.append({
                                    "title":   a.get("title", ""),
                                    "source":  a.get("source", "Marketaux"),
                                    "url":     a.get("url", ""),
                                    "date":    a.get("published_at", ""),
                                    "summary": a.get("description", "") or "",
                                })
                    except Exception:
                        pass

                # Finnhub 個股新聞（免費，按代號精準抓取）
                finnhub_key_fh = _get_key("FINNHUB_KEY")
                if finnhub_key_fh and len(fetched_news) < 5:
                    try:
                        from_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
                        to_date   = datetime.now().strftime("%Y-%m-%d")
                        resp_fh   = _req.get(
                            "https://finnhub.io/api/v1/company-news",
                            params  = {
                                "symbol": stock.symbol,
                                "from":   from_date,
                                "to":     to_date,
                                "token":  finnhub_key_fh,
                            },
                            timeout = 10,
                        )
                        if resp_fh.ok:
                            for a in resp_fh.json()[:10]:
                                headline = (a.get("headline") or "").strip()
                                if not headline:
                                    continue
                                ts = a.get("datetime", 0)
                                try:
                                    pub_str = datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d")
                                except Exception:
                                    pub_str = ""
                                fetched_news.append({
                                    "title":   headline,
                                    "source":  (a.get("source") or "Finnhub").strip(),
                                    "url":     a.get("url", "") or "",
                                    "date":    pub_str,
                                    "summary": (a.get("summary") or "")[:300],
                                })
                    except Exception:
                        pass

                # RSS 備援
                if len(fetched_news) < 3:
                    cutoff  = datetime.now() - timedelta(days=3)
                    pattern = re.compile(
                        re.escape(stock.symbol) + r"|" + re.escape(stock.name),
                        re.IGNORECASE
                    )
                    for rss_url in [
                        "https://feeds.reuters.com/reuters/technologyNews",
                        "https://feeds.reuters.com/reuters/businessNews",
                        "https://techcrunch.com/feed/",
                    ]:
                        try:
                            feed = _fp.parse(rss_url)
                            for entry in feed.entries[:30]:
                                title   = getattr(entry, "title",   "") or ""
                                summary = getattr(entry, "summary", "") or ""
                                if not pattern.search(f"{title} {summary}"):
                                    continue
                                pub_str = getattr(entry, "published", "")
                                try:
                                    pub_dt = datetime(*email.utils.parsedate(pub_str)[:6])
                                    if pub_dt < cutoff:
                                        continue
                                except Exception:
                                    pass
                                fetched_news.append({
                                    "title":   title,
                                    "source":  rss_url.split("/")[2].replace("feeds.", ""),
                                    "url":     getattr(entry, "link", ""),
                                    "date":    pub_str,
                                    "summary": summary[:300],
                                })
                        except Exception:
                            pass
                        if len(fetched_news) >= 5:
                            break

            fetched_news = fetched_news[:5]
            st.session_state[news_key_s] = fetched_news
            _sprog.progress(40, text="📊 新聞蒐集完成，正在準備分析數據...")

            # ── Step 2：組合 LLM Prompt ─────────────────

            # 把新聞列表格式化給 LLM
            if fetched_news:
                news_for_llm = "\n".join(
                    f"  {i+1}. [{n['source']}] {n['title']}\n"
                    f"     連結：{n['url']}\n"
                    f"     摘要：{n['summary'][:200]}"
                    for i, n in enumerate(fetched_news)
                )
            else:
                news_for_llm = "  （近 3 日內未找到相關新聞）"

            level  = assessment.alert_level.value.upper()
            rules  = "\n".join(f"  - {r}" for r in assessment.triggered_rules) or "  （無觸發規則）"
            val_info = (
                f"F P/E={stock.forward_pe:.1f}x, 歷史均值={stock.pe_3y_avg:.1f}x"
                if stock.is_profitable and stock.forward_pe and stock.pe_3y_avg
                else f"F P/E={stock.forward_pe:.1f}x"
                if stock.is_profitable and stock.forward_pe
                else f"Trailing P/E={stock.trailing_pe:.1f}x"
                if stock.is_profitable and stock.trailing_pe
                else f"F P/S={stock.forward_ps:.2f}x"
                if stock.forward_ps
                else f"Trailing P/S={stock.trailing_ps:.2f}x"
                if stock.trailing_ps
                else "估值數據不足"
            )

            # 分析師推薦彙整
            if any(v is not None for v in [stock.rec_strong_buy, stock.rec_buy,
                                            stock.rec_hold, stock.rec_sell,
                                            stock.rec_strong_sell]):
                _buy_tot  = (stock.rec_strong_buy or 0) + (stock.rec_buy or 0)
                _hold_tot = stock.rec_hold or 0
                _sell_tot = (stock.rec_sell or 0) + (stock.rec_strong_sell or 0)
                rec_summary = (
                    f"強買{stock.rec_strong_buy or 0} 買{stock.rec_buy or 0} "
                    f"持{stock.rec_hold or 0} 賣{stock.rec_sell or 0} "
                    f"強賣{stock.rec_strong_sell or 0}（買入合計 {_buy_tot}，賣出合計 {_sell_tot}）"
                )
            else:
                rec_summary = "N/A"

            # 多年估值快照
            val_multi = []
            for yr, eps, fpe, fps, rg, eg in [
                (2026, stock.eps_est_2026, stock.fpe_2026, stock.fps_2026,
                       stock.rev_growth_2026, stock.eps_growth_2026),
                (2027, stock.eps_est_2027, stock.fpe_2027, stock.fps_2027,
                       stock.rev_growth_2027, stock.eps_growth_2027),
                (2028, stock.eps_est_2028, stock.fpe_2028, stock.fps_2028,
                       stock.rev_growth_2028, stock.eps_growth_2028),
            ]:
                pe_ps = (f"F P/E={fpe:.1f}x" if fpe else
                         f"F P/S={fps:.2f}x" if fps else "N/A")
                val_multi.append(
                    f"  {yr}：EPS=${eps:.2f}" if eps else f"  {yr}：EPS=N/A",
                )
                val_multi[-1] += (
                    f"  {pe_ps}"
                    f"  營收成長={rg:+.1f}%" if rg is not None else ""
                ) + (f"  EPS成長={eg:+.1f}%" if eg is not None else "")
            val_multi_str = "\n".join(val_multi)

            # ── Step 3：多模型呼叫 ────────────────────────
            from module3_llm_summarizer import call_model, MODEL_CATALOG
            sel = st.session_state.get("selected_models", [])
            custom_p = st.session_state.get("custom_prompt", "").strip()

            # 戰術建議版塊
            # 共同結尾：四格操作摘要（關鍵價位依使用者風格給進出場建議）
            _style_hint = f"（依照使用者操作風格：{custom_p[:60]}{'...' if len(custom_p) > 60 else ''}）" if custom_p else ""
            _closing_fields = f"""
---

**操作方向：** 加碼 / 減碼 / 觀望 / 停損（四擇一，加粗標示）

**理由：** 2–3 句，引用上方數據，不得憑空捏造。

**關鍵價位{_style_hint}：** 支撐位與壓力位（從區間位置與52週高低點推算），並依照使用者的操作風格給出具體進場條件與出場停利/停損建議。

**風險提示：** 此標的在當前警戒等級下，針對上述操作風格最主要的下行風險。"""

            if custom_p:
                tactic_section = f"""## 🎯 {stock.symbol} 當前戰術建議

**警戒等級：{level}**

【風格分析】請先嚴格按照以下使用者指定的分析框架逐項輸出，每項均需引用具體數據：

{custom_p}
{_closing_fields}"""
            else:
                tactic_section = f"""## 🎯 {stock.symbol} 當前戰術建議

**警戒等級：{level}**

**操作方向：** 加碼 / 減碼 / 觀望 / 停損（四擇一，加粗標示）

**理由：** 2–3 句，引用上方數據，不得憑空捏造。

**關鍵價位：** 支撐位與壓力位（從區間位置與52週高低點推算），並給出具體進場條件與出場停利/停損建議。

**風險提示：** 此標的在當前警戒等級下最主要的下行風險。"""

            user_prompt = f"""根據以下數據，生成個股完整分析。

【個股資料】
  代號：{stock.symbol} | 名稱：{stock.name}
  現價：${stock.price:.2f} | 今日漲跌：{stock.change_pct:+.2f}%
  距52週高點：{stock.pct_from_52w_high:.1f}% | 區間位置：{stock.range_position:.0f}%
  量比：{stock.volume_ratio:.1f}x | 估值：{val_info}
  分析師推薦分布（Finnhub）：{rec_summary}

【多年估值預測（FMP + yfinance）】
{val_multi_str}

【市場環境】
  警戒等級：{level}
  觸發規則：
{rules}
  VIX={md_data.vix:.2f} | US10Y={md_data.us10y:.3f}% | DXY={md_data.dxy:.2f}

【近期相關新聞（3日內）】
{news_for_llm}

請輸出以下兩個版塊：

{tactic_section}

---

## 📰 {stock.symbol} 近期焦點新聞分析

針對上方每一則新聞進行分析。若無新聞直接寫「近 3 日內無相關新聞」。

每則格式（嚴格照此，空一行分隔）：

**[來源] [標題](連結URL)**
- 影響：利多 / 利空 / 中性待觀察（三選一）
- 分析：一句話，說明此新聞對 {stock.symbol} 的潛在影響"""

            sys_p_stock = (
                "你是一位謹慎的量化交易副官。"
                "根據提供的數據給出個股操作建議，並分析近期新聞對該標的的影響。"
                "所有判斷必須基於提供的數據，不得憑空捏造任何數字。"
                "使用者已在分析請求中指定輸出格式，請嚴格遵守，逐項完整輸出。"
            )
            multi_res: dict = {}
            for i, mid in enumerate(sel):
                lbl = MODEL_CATALOG.get(mid, {}).get("label", mid)
                pct = 55 + int(i / max(len(sel), 1) * 40)
                _sprog.progress(pct, text=f"🤖 {lbl} 正在分析 {stock.symbol}...")
                res = call_model(mid, sys_p_stock, user_prompt)
                multi_res[mid] = res
            _sprog.progress(100, text="✅ 完成")
            st.session_state[tactic_key] = multi_res
            st.rerun()


# ── 首次訪問：無任何 AI 模型 Key 時彈出設定導引（每個 Session 只顯示一次）──
_has_any_ai_key = any(_get_key(k) for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY"))
if not _has_any_ai_key and not st.session_state.get("setup_done"):
    st.session_state["setup_done"] = True   # 先標記，避免切頁面重複彈出
    _show_onboarding()

# ════════════════════════════════════════════════════════
#  頂部導覽列（取代 Sidebar）
# ════════════════════════════════════════════════════════

# ── 讀取當前頁面（session state 路由）────────────────────
page = st.session_state.get("nav_page", "🏠 戰情室主控台")

# ── PIN 鎖：離開 API 設定頁面時自動上鎖 ──────────────────
_api_page = "📚 教學 & API設定"
_prev_nav = st.session_state.get("_prev_nav_page", "")
if _prev_nav == _api_page and page != _api_page:
    st.session_state["_pin_unlocked"] = False
    st.session_state["_pin_fernet"]   = None
st.session_state["_prev_nav_page"] = page

# ── API key 變數（全域用途）──────────────────────────────
api_key        = _get_key("ANTHROPIC_API_KEY")
openai_key     = _get_key("OPENAI_API_KEY")
google_key     = _get_key("GOOGLE_API_KEY")
marketaux_key  = _get_key("MARKETAUX_API_KEY")
finnhub_key_sb = _get_key("FINNHUB_KEY")
fmp_key_sb     = _get_key("FMP_KEY")


def _render_navbar(back_to=None, back_label="返回主控台"):
    """頂部導覽列：固定 HTML 視覺層 + JS 定位 Streamlit 互動按鈕"""
    import html as _h
    import streamlit.components.v1 as _comp
    _is_d = st.session_state.get("_theme", "light") == "dark"
    _icon_theme = "☀️" if _is_d else "🌙"
    _btn_color  = "#E2E8F0" if _is_d else "#334155"
    _btn_hover  = "rgba(255,255,255,0.14)" if _is_d else "rgba(0,0,0,0.07)"

    # 使用者頭像 HTML
    _pic_html = ""
    if _current_user_pic and isinstance(_current_user_pic, str):
        _purl = str(_current_user_pic)
        if _purl.startswith("https://lh3.googleusercontent.com/") or \
           _purl.startswith("https://googleusercontent.com/"):
            _pic_html = (
                f"<img src='{_h.escape(_purl)}' width='28' height='28' "
                "style='border-radius:50%;border:2px solid rgba(128,128,128,0.4);vertical-align:middle;'>"
            )
    _safe_nm = _h.escape(str(_current_user_name))

    # ── 固定視覺導覽列 ─────────────────────────────────────
    # 右側留出 ~160px 給 JS 定位的 Streamlit 按鈕
    st.markdown(f"""
<div class="war-navbar">
    <div class="nav-brand">
        <div class="nav-logo">⚔️</div>
        <span class="nav-title">美股投資戰情室</span>
    </div>
    <div class="nav-right" style="margin-right:168px">
        <div class="nav-user">
            {_pic_html or "👤"}
            <span>{_safe_nm}</span>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

    # ── 返回按鈕（文件流，子頁面才顯示）─────────────────────
    if back_to:
        if st.button(f"← {back_label}", key="nb_back"):
            st.session_state["nav_page"] = back_to
            st.session_state["selected_stock"] = None
            st.rerun()

    # ── 哨兵 + 真實 Streamlit 動作按鈕 ──────────────────────
    st.markdown('<div class="nav-btn-sentinel"></div>', unsafe_allow_html=True)
    _ba, _bb, _bc = st.columns([1, 1, 1])
    if _ba.button(_icon_theme, key="nb_theme", help="切換深淺色模式"):
        _new_theme = "light" if _is_d else "dark"
        st.session_state["_theme"] = _new_theme
        st.toast("☀️ 已切換至淺色模式" if _new_theme == "light" else "🌙 已切換至深色模式", icon="✅")
        st.rerun()
    if _bb.button("☁️", key="nb_sync", help="同步資料至雲端"):
        try:
            from module_storage import save_user_data
            if save_user_data(_current_user_id):
                st.toast("✅ 已同步至雲端", icon="☁️")
        except Exception as _se:
            st.toast(f"同步失敗：{_se}", icon="⚠️")
    if _bc.button("登出", key="nb_logout"):
        st.session_state.pop("_oauth_user", None)
        st.session_state["user_data_loaded"] = False
        st.rerun()

    # ── JavaScript：從 iframe 存取父視窗 DOM，將按鈕定位至導覽列 ──
    _comp.html(f"""
<script>
(function() {{
    try {{
        var pd = window.parent.document;

        function findHBlock(sentinel) {{
            // 從 sentinel 往上找第一個 data-testid 元素，再找下一個 stHorizontalBlock 兄弟
            var el = sentinel;
            for (var i = 0; i < 5; i++) {{
                el = el.parentElement;
                if (!el) return null;
                if (el.hasAttribute('data-testid')) {{
                    var sib = el.nextElementSibling;
                    var n = 0;
                    while (sib && n++ < 8) {{
                        if (sib.getAttribute('data-testid') === 'stHorizontalBlock') return {{mc: el, hb: sib}};
                        sib = sib.nextElementSibling;
                    }}
                    return null;
                }}
            }}
            return null;
        }}

        function applyNavStyle() {{
            var sentinel = pd.querySelector('.nav-btn-sentinel');
            if (!sentinel) return false;
            var found = findHBlock(sentinel);
            if (!found) return false;
            var mc = found.mc, hb = found.hb;

            // 隱藏哨兵容器
            mc.style.cssText = 'height:0;overflow:hidden;margin:0;padding:0;';

            // 定位按鈕列至導覽列右側
            Object.assign(hb.style, {{
                position:'fixed', top:'10px', right:'28px', left:'auto',
                width:'auto', zIndex:'1002', display:'flex',
                alignItems:'center', gap:'2px', flexWrap:'nowrap',
                margin:'0', padding:'0', background:'transparent'
            }});

            // 縮緊每個 column
            hb.querySelectorAll('[data-testid="stColumn"]').forEach(function(c){{
                Object.assign(c.style, {{flex:'none', minWidth:'0', padding:'0', width:'auto'}});
            }});

            // 美化按鈕
            hb.querySelectorAll('[data-testid="stButton"] button').forEach(function(b, i){{
                Object.assign(b.style, {{
                    background:'transparent',
                    border:'1px solid transparent',
                    color:'{_btn_color}',
                    padding: i===2 ? '4px 10px' : '4px 9px',
                    fontSize: i===2 ? '12px' : '15px',
                    fontWeight: i===2 ? '600' : 'normal',
                    borderRadius:'8px', height:'34px', minHeight:'34px',
                    lineHeight:'1', cursor:'pointer', whiteSpace:'nowrap',
                    boxShadow:'none', transition:'background 0.12s'
                }});
                b.onmouseover = function(){{ this.style.background = '{_btn_hover}'; }};
                b.onmouseout  = function(){{ this.style.background = 'transparent'; }};
            }});
            return true;
        }}

        // 嘗試套用，最多重試 30 次（3 秒）
        var tries = 0;
        function tryApply() {{
            if (applyNavStyle()) return;
            if (++tries < 30) setTimeout(tryApply, 100);
        }}
        tryApply();

        // 監聽 DOM 變化（Streamlit 重渲染時重新套用），防抖 50ms
        var debounceTimer;
        new window.parent.MutationObserver(function() {{
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(applyNavStyle, 50);
        }}).observe(pd.body, {{childList: true, subtree: true}});

    }} catch(e) {{ /* cross-origin 時靜默失敗，CSS :has() 作為備援 */ }}
}})();
</script>
""", height=0)



# ════════════════════════════════════════════════════════
#  頂層路由：個股詳細頁面（優先於所有頁面判斷）
# ════════════════════════════════════════════════════════

_sel = st.session_state.get("selected_stock")

# 若使用者在個股頁面點擊導覽跳頁，優先清除個股狀態
if _sel is not None and page != "📋 自選股管理":
    st.session_state["selected_stock"] = None
    _sel = None

if _sel is not None:
    _render_navbar(back_to="📋 自選股管理", back_label="返回自選股")
    render_stock_detail(_sel["symbol"], _sel["name"])

# ════════════════════════════════════════════════════════
#  Page 1：戰情室主控台
# ════════════════════════════════════════════════════════

elif page == "🏠 戰情室主控台":
    _render_navbar()

    # ── 警戒等級徽章 ──────────────────────────────────────
    assessment = st.session_state.get("assessment")
    _alert_labels = {
        "GREEN":  ("🟢 GREEN  正常分析模式",  "alert-green"),
        "YELLOW": ("🟡 YELLOW 謹慎警戒模式", "alert-yellow"),
        "RED":    ("🔴 RED    風險中斷模式",  "alert-red"),
        "BLACK":  ("⚫ BLACK  黑天鵝防禦",    "alert-black"),
    }
    if assessment:
        lv = assessment.alert_level.value.upper()
        text, cls = _alert_labels.get(lv, (lv, "alert-green"))
        st.markdown(f'<div class="{cls}">{text}</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="alert-green">── 等待首次分析</div>', unsafe_allow_html=True)
    st.markdown("")

    # ── 總經指標（KPI 卡片 3+3）────────────────────────────
    md = st.session_state.get("market_data")
    c1, c2, c3 = st.columns(3)
    c4, c5, c6 = st.columns(3)

    if md:
        sp_chg = round((md.sp500  - md.sp500_prev)  / md.sp500_prev  * 100, 2) if md.sp500_prev  else 0
        nq_chg = round((md.nasdaq - md.nasdaq_prev) / md.nasdaq_prev * 100, 2) if md.nasdaq_prev else 0
        dj_chg = round((md.djia   - md.djia_prev)   / md.djia_prev   * 100, 2) if md.djia_prev   else 0
        c1.metric("VIX 恐慌指數",    f"{md.vix:.2f}")
        c2.metric("US10Y 美債10年",  f"{md.us10y:.3f}%")
        c3.metric("DXY 美元指數",    f"{md.dxy:.2f}")
        c4.metric("S&P 500 標普500", f"{md.sp500:,.0f}",  f"{sp_chg:+.2f}%")
        c5.metric("NASDAQ 納斯達克", f"{md.nasdaq:,.0f}", f"{nq_chg:+.2f}%")
        c6.metric("DJIA 道瓊指數",   f"{md.djia:,.0f}",   f"{dj_chg:+.2f}%")
    else:
        for _m, _mc in [("VIX 恐慌指數",c1),("US10Y 美債10年",c2),("DXY 美元指數",c3),
                         ("S&P 500 標普500",c4),("NASDAQ 納斯達克",c5),("DJIA 道瓊指數",c6)]:
            _mc.metric(_m, "──")

    st.markdown("")

    # ── 啟動分析按鈕 + 功能模組導覽 ──────────────────────
    _is_dk_hp = st.session_state.get("_theme", "light") == "dark"
    _divider_color = "#334155" if _is_dk_hp else "#E2E8F0"
    _muted_color   = "#94A3B8" if _is_dk_hp else "#64748B"
    _txt_color     = "#E2E8F0" if _is_dk_hp else "#334155"
    _card_color    = "#1E293B" if _is_dk_hp else "#FFFFFF"
    _card_border   = "#334155" if _is_dk_hp else "#E2E8F0"

    # 分析啟動區
    _run_col, _hint_col = st.columns([3, 7])
    with _run_col:
        run_disabled = not bool(api_key)
        if st.button("🚀 啟動完整分析", disabled=run_disabled,
                     use_container_width=True, type="primary", key="btn_run_analysis"):
            st.toast("⏳ 分析啟動中，請稍候 30–90 秒…", icon="🔄")
            prog = st.progress(0, text="初始化中...")
            run_full_analysis(prog=prog)
            st.toast("✅ 分析完成！", icon="🎯")
            st.rerun()
    with _hint_col:
        if not api_key:
            st.warning("請先至「📚 教學 & API設定」設定 AI 模型金鑰")
        else:
            last = st.session_state.get("last_run")
            st.caption(f"手動觸發 · 單次執行 · 零自動輪詢" + (f"　|　🕐 上次執行：{last}" if last else ""))

    # ── 觸發規則 ──────────────────────────────────────────
    if assessment and assessment.triggered_rules:
        lv  = assessment.alert_level.value.upper()
        cls = "rule-red" if lv in ("RED","BLACK") else "rule-yell" if lv == "YELLOW" else "rule-blk"
        for rule in assessment.triggered_rules:
            import html as _html_esc
            st.markdown(f'<div class="{cls}">⚡ {_html_esc.escape(str(rule))}</div>', unsafe_allow_html=True)
        st.markdown("")

    if assessment and assessment.fomo_intercept:
        st.error("🚨 **FOMO 攔截訊號觸發** — 請勿在當前市場環境下追高或無支撐接刀")
        for s in assessment.fomo_signals:
            st.warning(f"⚠️ {s}")

    # ── 功能模組導覽卡片 ──────────────────────────────────
    st.markdown(f"""
<div style="display:flex;align-items:center;gap:12px;margin:24px 0 16px;">
    <span style="font-size:15px;font-weight:600;color:{_txt_color};">功能模組</span>
    <div style="height:1px;flex-grow:1;background:{_divider_color};"></div>
</div>
""", unsafe_allow_html=True)

    _MODULES = [
        ("📋", "自選股管理",      "管理關注清單與板塊分類",    "📋 自選股管理"),
        ("⚙️", "模型與投資偏好",  "設定 AI 模型與分析風格",    "⚙️ 模型與投資偏好"),
        ("📚", "教學 & API設定", "金鑰管理、申請指南與教學", "📚 教學 & API設定"),
        ("📝", "版本更新紀錄",    "查看最新功能與修正紀錄",    "📝 版本更新紀錄"),
    ]
    _mod_cols = st.columns(len(_MODULES))
    for _mi, (_icon, _title, _desc, _nav_target) in enumerate(_MODULES):
        with _mod_cols[_mi]:
            st.markdown(f"""
<div style="
    background:{_card_color};border:1px solid {_card_border};
    border-radius:20px;padding:22px 18px 14px;
    box-shadow:{'0 4px 16px rgba(0,0,0,0.3)' if _is_dk_hp else '0 4px 16px rgba(0,0,0,0.05)'};
    margin-bottom:4px;
">
    <div style="font-size:26px;margin-bottom:8px;">{_icon}</div>
    <div style="font-weight:700;font-size:14px;color:{_txt_color};margin-bottom:4px;">{_title}</div>
    <div style="font-size:12px;color:{_muted_color};line-height:1.5;">{_desc}</div>
</div>""", unsafe_allow_html=True)
            if st.button("前往 →", key=f"nav_{_mi}", use_container_width=True):
                st.session_state["nav_page"] = _nav_target
                st.rerun()

    # ── AI 市場分析報告 ──────────────────────────────────
    multi_rpts = st.session_state.get("multi_reports", {})
    if multi_rpts:
        st.divider()
        valid  = {mid: r for mid, r in multi_rpts.items() if not r.get("error")}
        errors = {mid: r for mid, r in multi_rpts.items() if r.get("error")}
        for mid, r in errors.items():
            st.error(f"⚠️ {r.get('label', mid)} 生成失敗：{r['error']}")
        if valid:
            if len(valid) == 1:
                mid, r = next(iter(valid.items()))
                st.caption(
                    f"{r.get('icon','🤖')} **{r.get('label')}** · "
                    f"⏱ {r.get('elapsed_sec')}s · "
                    f"輸入 {r.get('input_tokens',0):,} / 輸出 {r.get('output_tokens',0):,} tokens"
                )
                st.markdown(r.get("report", r.get("text", "")))
            else:
                tab_labels = [f"{r.get('icon','🤖')} {r.get('label', mid)}" for mid, r in valid.items()]
                tabs = st.tabs(tab_labels)
                for tab, (mid, r) in zip(tabs, valid.items()):
                    with tab:
                        c1, c2, c3 = st.columns(3)
                        c1.metric("⏱ 生成時間",    f"{r.get('elapsed_sec','?')} 秒")
                        c2.metric("📥 輸入 Tokens", f"{r.get('input_tokens',0):,}")
                        c3.metric("📤 輸出 Tokens", f"{r.get('output_tokens',0):,}")
                        st.markdown(r.get("report", r.get("text", "")))
    elif st.session_state.get("market_analysis"):
        st.divider()
        st.markdown(st.session_state["market_analysis"])




# ════════════════════════════════════════════════════════
#  Page 2：自選股管理
# ════════════════════════════════════════════════════════

elif page == "📋 自選股管理":
    _render_navbar(back_to="🏠 戰情室主控台")
    st.markdown("## 自選股管理")
    tab_list, tab_add = st.tabs(["📋 我的清單", "➕ 新增股票"])

        # ── 我的清單 ────────────────────────────────────────
    with tab_list:
        _col_refresh, _col_cap = st.columns([1, 5])
        if _col_refresh.button("🔄 重新整理", key="wl_refresh", use_container_width=True):
            st.rerun()
        wl_data = load_wl()
        total   = wl_total(wl_data)
        _col_cap.caption(f"共 {total} 檔股票　（點擊名稱查看詳細頁面）")

        if total == 0:
            st.info("清單為空，請至「新增股票」頁面加入")
        else:
            # 迭代全部板塊（預設 + 自訂 + 舊版 legacy key 如 other）
            _shown_keys = get_all_sector_keys()
            for _lk in wl_data:
                if _lk not in _shown_keys and _lk != "_custom_sectors" and isinstance(wl_data[_lk], dict):
                    _shown_keys.append(_lk)

            for sec_key in _shown_keys:
                stocks_raw = wl_data.get(sec_key, {})
                if not stocks_raw:
                    continue
                label = get_sector_label(sec_key)
                with st.expander(f"【{label}】{len(stocks_raw)} 檔", expanded=True):
                    for sym, name in list(stocks_raw.items()):
                        col_btn, col_rm = st.columns([6, 1])
                        with col_btn:
                            if st.button(f"📊 {name}　`{sym}`", key=f"detail_{sym}",
                                         use_container_width=True):
                                st.session_state["selected_stock"] = {
                                    "symbol": sym, "name": name
                                }
                                st.rerun()
                        if col_rm.button("✕", key=f"rm_{sym}", type="secondary"):
                            msg = wl_remove(sym)
                            st.toast(msg)
                            st.rerun()

    # ── 新增股票 ──────────────────────────────────────────
    with tab_add:
        with st.form("add_form", clear_on_submit=True):
            st.subheader("新增股票")
            col_a, col_b = st.columns(2)
            with col_a:
                new_sym  = st.text_input("股票代號 *", placeholder="例：NVDA").upper().strip()
            with col_b:
                new_name = st.text_input("股票名稱（選填）", placeholder="例：NVIDIA，留空則以代號顯示")

            new_sec = st.selectbox(
                "板塊",
                options      = get_all_sector_keys(),
                format_func  = get_sector_label,
            )

            submitted = st.form_submit_button("➕ 加入清單", type="primary", use_container_width=True)
            if submitted:
                import re as _re_sym
                if not new_sym:
                    st.error("請填入股票代號")
                elif not _re_sym.match(r'^[A-Z0-9.\-\^]{1,12}$', new_sym):
                    st.error("⚠️ 股票代號格式不正確（只允許大寫字母、數字、. - ^，最多 12 字元）")
                elif len(new_name) > 50:
                    st.error("⚠️ 股票名稱過長（最多 50 字元）")
                else:
                    msg = wl_add(new_sym, new_name, new_sec)
                    if msg.startswith("✅"):
                        st.success(msg)
                    else:
                        st.warning(msg)

        # ── 自訂板塊管理 ──────────────────────────────────
        st.divider()
        _custom_now = st.session_state.get("_custom_sectors", {})
        _total_secs = len(SECTOR_LABELS) + len(_custom_now)
        st.markdown(f"**🗂️ 自訂板塊管理**　`{_total_secs}/{MAX_SECTORS}`")
        st.caption("新增專屬板塊分類，最多可建立至合計 20 個板塊。有股票的板塊需先清空才能刪除。")

        # 現有自訂板塊列表（含刪除按鈕）
        if _custom_now:
            for _cs_key, _cs_label in list(_custom_now.items()):
                _wl_now   = load_wl()
                _cs_count = len(_wl_now.get(_cs_key, {}))
                c_lbl, c_cnt, c_del = st.columns([5, 2, 1])
                c_lbl.write(f"**{_cs_label}**")
                c_cnt.caption(f"{_cs_count} 檔" if _cs_count else "空板塊")
                if c_del.button("✕", key=f"delcs_{_cs_key}", type="secondary"):
                    _msg = custom_sector_delete(_cs_key)
                    if _msg.startswith("✅"):
                        st.toast(_msg)
                        st.rerun()
                    else:
                        st.warning(_msg)
        else:
            st.caption("尚無自訂板塊")

        # 新增自訂板塊
        if _total_secs < MAX_SECTORS:
            st.markdown("")
            _nc1, _nc2 = st.columns([4, 1])
            _new_cs_name = _nc1.text_input(
                "新板塊名稱", placeholder="例：台股、生技、REITs",
                label_visibility="collapsed", key="new_cs_input",
            )
            if _nc2.button("＋ 新增", key="add_cs_btn", use_container_width=True):
                _msg = custom_sector_add(_new_cs_name)
                if _msg.startswith("✅"):
                    st.toast(_msg)
                    st.rerun()
                else:
                    st.warning(_msg)
        else:
            st.info(f"已達板塊上限（{MAX_SECTORS} 個）", icon="ℹ️")

        st.divider()
        st.caption("快速新增常見標的")
        presets = [
            ("NVDA","NVIDIA","semiconductor"),
            ("TSM","TSMC","semiconductor"),
            ("AMD","AMD","semiconductor"),
            ("INTC","Intel","semiconductor"),
            ("AAPL","Apple","tech"),
            ("MSFT","Microsoft","tech"),
            ("TSLA","Tesla","tech"),
            ("LMT","Lockheed","defense"),
            ("USO","US Oil ETF","etf"),
            ("GLD","Gold ETF","etf"),
            ("TLT","20Y Bond ETF","etf"),
        ]
        cols = st.columns(4)
        for i, (sym, name, sec) in enumerate(presets):
            wl_now = load_wl()
            already = any(sym in v for v in wl_now.values())
            with cols[i % 4]:
                label = f"{'✓ ' if already else ''}{sym}"
                if st.button(label, key=f"preset_{sym}", disabled=already, use_container_width=True):
                    msg = wl_add(sym, name, sec)
                    st.toast(msg)
                    st.rerun()


# ════════════════════════════════════════════════════════
#  Page 3：模型與投資偏好設定
# ════════════════════════════════════════════════════════

elif page == "⚙️ 模型與投資偏好":
    _render_navbar(back_to="🏠 戰情室主控台")
    st.markdown("## ⚙️ 模型與投資偏好設定")

    from module3_llm_summarizer import MODEL_CATALOG, detect_provider_from_model_id

    # ── 可用模型選擇 ──────────────────────────────────────
    st.subheader("AI 模型選擇")
    st.caption("根據已設定的 API 金鑰，系統自動顯示可用模型。多選時報告將分頁對比顯示。")

    # 各供應商推薦模型清單（最新版 + 前代穩定版分組）
    _PROVIDER_META = {
        "anthropic": {
            "label": "🟠 Anthropic Claude",
            "env":   "ANTHROPIC_API_KEY",
            "latest": [
                ("claude-opus-4-7",  "Claude Opus 4.7",    "🔵", "旗艦，最強推理"),
                ("claude-sonnet-4-6","Claude Sonnet 4.6",  "🟠", "⭐ 推薦，速度/品質最佳平衡"),
                ("claude-haiku-4-5", "Claude Haiku 4.5",   "🟡", "輕量快速，最省費用"),
            ],
            "stable": [
                ("claude-opus-4-5",  "Claude Opus 4.5",    "🔵", "前代旗艦"),
                ("claude-sonnet-4-5","Claude Sonnet 4.5",  "🟠", "前代均衡"),
                ("claude-haiku-3-5", "Claude Haiku 3.5",   "🟡", "前代輕量"),
            ],
        },
        "openai": {
            "label": "🟢 OpenAI GPT",
            "env":   "OPENAI_API_KEY",
            "latest": [
                ("gpt-5.5",     "GPT-5.5",      "🟢", "旗艦，最強智能"),
                ("gpt-5.4",     "GPT-5.4",      "🟢", "⭐ 推薦，均衡性價比"),
                ("gpt-5.4-mini","GPT-5.4 Mini", "🟩", "輕量快速，最省費用"),
            ],
            "stable": [
                ("gpt-4o",      "GPT-4o",       "🟢", "前代旗艦"),
                ("gpt-4o-mini", "GPT-4o Mini",  "🟩", "前代輕量"),
                ("o3",          "o3",           "🔷", "前代推理增強"),
            ],
        },
        "google": {
            "label": "🔴 Google Gemini",
            "env":   "GOOGLE_API_KEY",
            "latest": [
                ("gemini-3.1-pro-preview",  "Gemini 3.1 Pro",       "🔴", "旗艦，最強推理（付費）"),
                ("gemini-3-flash-preview",  "Gemini 3 Flash",        "🔶", "⭐ 推薦，免費方案可用"),
                ("gemini-3.1-flash-lite",   "Gemini 3.1 Flash Lite", "🟡", "最省費用，免費方案可用"),
            ],
            "stable": [
                ("gemini-2.5-pro",        "Gemini 2.5 Pro",       "🔴", "前代旗艦（付費）"),
                ("gemini-2.5-flash",      "Gemini 2.5 Flash",     "🔶", "前代均衡，免費方案可用"),
                ("gemini-2.5-flash-lite", "Gemini 2.5 Flash Lite","🟡", "前代輕量，免費方案可用"),
            ],
        },
    }

    cur_sel = list(st.session_state.get("selected_models", []))
    new_sel = []

    has_any_key = any(_get_key(m["env"]) for m in _PROVIDER_META.values())

    if not has_any_key:
        st.warning("⚠️ 尚未設定任何 AI 模型金鑰，請先至「📚 教學 & API設定」設定 API Key 才能啟用模型。")
    else:
        for prov_id, meta in _PROVIDER_META.items():
            key_val = _get_key(meta["env"])
            if not key_val:
                # 灰色顯示未設定的供應商
                st.markdown(
                    f"<span style='color:#bbb; font-size:13px'>{meta['label']}　——　金鑰未設定，前往「📚 教學 & API設定」輸入</span>",
                    unsafe_allow_html=True,
                )
                st.markdown("")
                continue

            st.markdown(f"**{meta['label']}**")
            col_latest, col_stable = st.columns(2)

            with col_latest:
                st.caption("🆕 最新版")
                for mid, label, icon, note in meta["latest"]:
                    checked = st.checkbox(
                        f"{icon} {label}",
                        value=mid in cur_sel,
                        key=f"chk_{mid}",
                        help=note,
                    )
                    if checked:
                        new_sel.append(mid)

            with col_stable:
                st.caption("🔒 前代穩定版")
                for mid, label, icon, note in meta["stable"]:
                    checked = st.checkbox(
                        f"{icon} {label}",
                        value=mid in cur_sel,
                        key=f"chk_{mid}",
                        help=note,
                    )
                    if checked:
                        new_sel.append(mid)

            st.markdown("")

    st.divider()

    # ── 自訂模型 ID ──────────────────────────────────────
    st.markdown("**🔧 自訂模型 ID（進階）**")
    st.caption("輸入任意模型 ID，可使用最新版本或未列出的模型。系統會從名稱自動判斷供應商（需已設定對應金鑰）。")
    st.caption("範例：`gemini-2.5-pro-preview-06-05`、`claude-opus-4`、`gpt-4-turbo`")

    custom_model_ids: list = list(st.session_state.get("custom_model_ids", []))

    col_ci, col_ca = st.columns([5, 1])
    custom_input = col_ci.text_input(
        "自訂模型 ID",
        placeholder="例：gemini-2.5-pro-preview-06-05",
        label_visibility="collapsed",
        key="custom_model_text_input",
    )
    if col_ca.button("➕ 加入", key="btn_add_custom_model", use_container_width=True):
        import re as _re_mid
        mid_clean = custom_input.strip()
        if not mid_clean:
            pass
        elif not _re_mid.match(r'^[a-zA-Z0-9._\-:/]{1,100}$', mid_clean):
            st.error("⚠️ 模型 ID 格式不正確（只允許英文、數字、. - _ : /，最多 100 字元）")
        elif mid_clean in custom_model_ids:
            st.info(f"「{mid_clean}」已在清單中")
        else:
            custom_model_ids.append(mid_clean)
            st.session_state["custom_model_ids"] = custom_model_ids
            if mid_clean not in cur_sel:
                cur_sel.append(mid_clean)
            st.rerun()

    for cid in custom_model_ids:
        prov   = detect_provider_from_model_id(cid)
        p_icon = {"anthropic": "🟠", "openai": "🟢", "google": "🔴"}.get(prov, "🤖")
        p_key  = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY", "google": "GOOGLE_API_KEY"}.get(prov, "")
        key_ok = bool(_get_key(p_key)) if p_key else False
        ccol1, ccol2 = st.columns([9, 1])
        suffix = "" if key_ok else "　⚠️ 金鑰未設定"
        checked_c = ccol1.checkbox(
            f"{p_icon} {cid}（自訂）{suffix}",
            value=cid in cur_sel,
            disabled=not key_ok,
            key=f"chk_custom_{cid}",
        )
        if ccol2.button("✕", key=f"rm_custom_{cid}", help="移除此自訂模型"):
            custom_model_ids.remove(cid)
            st.session_state["custom_model_ids"] = custom_model_ids
            if cid in cur_sel:
                cur_sel.remove(cid)
            st.rerun()
        if checked_c and key_ok:
            new_sel.append(cid)

    # fallback：至少選一個
    if not new_sel:
        for prov_id, meta in _PROVIDER_META.items():
            if _get_key(meta["env"]):
                new_sel = [meta["models"][0][0]]
                break
        if not new_sel:
            new_sel = ["claude-sonnet-4-5"]

    st.session_state["selected_models"] = new_sel
    sel_labels = [MODEL_CATALOG.get(m, {}).get("label", m) for m in new_sel]
    st.caption(f"✅ 已選擇：{', '.join(sel_labels)}")

    st.divider()

    # ── 投資偏好設定 ──────────────────────────────────────
    st.subheader("📝 投資分析偏好")
    st.caption("以下設定將注入所有模型的 System Prompt，讓報告更貼近你的投資風格。")

    # 快速風格選擇
    st.markdown("**快速套用投資風格**")
    style_presets = {
        "🔍 成長投資":   "我偏向成長型投資，重點關注營收加速、EPS成長率、市場擴張性及競爭護城河。請特別分析各標的的成長動能與未來三年預估增速。",
        "💰 價值投資":   "我偏向價值投資，重點關注 F P/E 相對歷史均值的折溢價、企業自由現金流、ROE及股息。當估值明顯低估時提示。",
        "⚡ 動能交易":   "我以動能交易為主，重點關注量比、52週區間位置、均線排列、MACD及RSI交叉信號。請特別標注放量突破或技術破壞的標的。",
        "🛡️ 防禦配置":  "我偏好防禦型配置，重視股息穩定性、低Beta值、現金流可見度及抗衰退能力。在高風險環境下優先提示避險標的。",
        "🌐 宏觀驅動":   "我以宏觀因素為主要判斷依據，重視Fed政策、殖利率曲線、DXY走向及大宗商品對板塊的連動影響。",
    }
    preset_cols = st.columns(len(style_presets))
    for i, (style_name, style_text) in enumerate(style_presets.items()):
        with preset_cols[i]:
            if st.button(style_name, use_container_width=True, key=f"preset_style_{i}"):
                st.session_state["custom_prompt"] = style_text
                st.rerun()

    custom_text = st.text_area(
        "自訂偏好說明（可在快速套用後手動修改）",
        value       = st.session_state.get("custom_prompt", ""),
        height      = 130,
        placeholder = "例：我重點關注半導體板塊的AI算力需求，特別注意 NVDA、AMD 的出貨量與數據中心營收比例...",
        key         = "custom_prompt_input",
    )
    _MAX_PROMPT_LEN = 500
    col_save, col_clear, _ = st.columns([2, 2, 6])
    st.caption(f"字數：{len(custom_text)} / {_MAX_PROMPT_LEN}")
    if col_save.button("💾 儲存偏好", type="primary"):
        if len(custom_text) > _MAX_PROMPT_LEN:
            st.error(f"⚠️ 偏好說明過長（{len(custom_text)} 字），請精簡至 {_MAX_PROMPT_LEN} 字以內")
        else:
            st.session_state["custom_prompt"] = custom_text
            st.success("✅ 投資偏好已儲存，下次分析將自動套用")
    if col_clear.button("🗑️ 清除", type="secondary"):
        st.session_state["custom_prompt"] = ""
        st.rerun()

    if st.session_state.get("custom_prompt"):
        st.divider()
        st.markdown("**目前套用的偏好：**")
        st.info(st.session_state["custom_prompt"])


# ════════════════════════════════════════════════════════
#  Page 4：教學指南
# ════════════════════════════════════════════════════════

elif page == "📚 教學 & API設定":
    _render_navbar(back_to="🏠 戰情室主控台")
    st.markdown("## 📚 教學指南 & API 設定")

    tab_keys, tab_ai, tab_data = st.tabs([
        "🔑 API 金鑰管理",
        "🤖 AI 模型申請",
        "📊 財經資料 API",
    ])

    # ── Tab 1：API 金鑰管理 ──────────────────────────────
    with tab_keys:
        st.subheader("API 金鑰管理")

        # ── PIN 碼保護區（僅雲端）────────────────────────
        _pin_show_keys = True   # 是否顯示金鑰管理內容
        if _is_cloud():
            _uid_pin   = st.session_state.get("_current_user_id_cache", "")
            _has_pin   = st.session_state.get("_user_has_pin", False)
            _unlocked  = st.session_state.get("_pin_unlocked", False)

            if not _has_pin:
                # ── 未設 PIN：說明 + 設定入口 ──────────
                st.info(
                    "🔐 **PIN 碼保護（密碼鎖）**\n\n"
                    "設定 PIN 碼後，您的 API 金鑰將使用僅您知道的密碼加密儲存，"
                    "**任何人（包括管理員）都無法查詢您的金鑰**（零知識加密）。\n\n"
                    "💡 建議先填寫所有 AI 模型與財經資料 API 金鑰，再設定 PIN 碼，操作更方便。"
                )
                with st.expander("🔒 設定 PIN 碼保護", expanded=False):
                    _pc1, _pc2 = st.columns(2)
                    _setup_pin  = _pc1.text_input("新 PIN 碼（4–8 位數字）", type="password",
                                                   placeholder="••••", key="setup_pin_input")
                    _setup_pin2 = _pc2.text_input("確認 PIN 碼", type="password",
                                                   placeholder="••••", key="setup_pin_confirm")
                    if st.button("🔒 設定 PIN 碼", type="primary", key="btn_set_pin"):
                        if not _setup_pin or not _setup_pin2:
                            st.error("請填寫 PIN 碼與確認 PIN 碼")
                        elif _setup_pin != _setup_pin2:
                            st.error("兩次輸入的 PIN 碼不一致")
                        elif not _setup_pin.isdigit() or not (4 <= len(_setup_pin) <= 8):
                            st.error("PIN 碼須為 4–8 位純數字")
                        elif _uid_pin:
                            from module_storage import set_pin_code
                            if set_pin_code(_uid_pin, _setup_pin):
                                st.success("✅ PIN 碼設定成功！API 金鑰已加密保護。")
                                st.rerun()
                            else:
                                st.error("PIN 碼設定失敗，請稍後重試")

            elif not _unlocked:
                # ── PIN 已設但未解鎖：顯示輸入框 ────────
                st.warning("🔒 **API 金鑰受 PIN 碼保護**　請輸入 PIN 碼以管理金鑰")
                _col_pi, _col_pb = st.columns([3, 1])
                _entered_pin = _col_pi.text_input(
                    "PIN 碼", type="password", placeholder="請輸入 PIN 碼",
                    key="unlock_pin_input", label_visibility="collapsed",
                )
                if _col_pb.button("🔓 解鎖", type="primary", key="btn_unlock_pin"):
                    if _entered_pin and _uid_pin:
                        from module_storage import verify_pin, load_api_keys_pin
                        _ok, _fernet = verify_pin(_uid_pin, _entered_pin)
                        if _ok:
                            st.session_state["_pin_fernet"]   = _fernet
                            st.session_state["_pin_unlocked"] = True
                            load_api_keys_pin(_uid_pin, _fernet)
                            st.rerun()
                        else:
                            st.error("❌ PIN 碼錯誤")
                    else:
                        st.warning("請輸入 PIN 碼")

                with st.expander("🔑 重設 PIN 碼（需輸入現有 PIN 碼）", expanded=False):
                    _rp_old  = st.text_input("現有 PIN 碼", type="password",
                                              placeholder="••••", key="reset_old_pin")
                    _rp_new  = st.text_input("新 PIN 碼（4–8 位數字）", type="password",
                                              placeholder="••••", key="reset_new_pin")
                    _rp_new2 = st.text_input("確認新 PIN 碼", type="password",
                                              placeholder="••••", key="reset_new_pin2")
                    if st.button("🔄 重設 PIN 碼", key="btn_reset_pin_locked"):
                        if not _rp_old or not _rp_new or not _rp_new2:
                            st.error("請填寫所有欄位")
                        elif _rp_new != _rp_new2:
                            st.error("新 PIN 碼兩次輸入不一致")
                        elif not _rp_new.isdigit() or not (4 <= len(_rp_new) <= 8):
                            st.error("新 PIN 碼須為 4–8 位純數字")
                        elif _uid_pin:
                            from module_storage import reset_pin_code
                            _ok, _err = reset_pin_code(_uid_pin, _rp_old, _rp_new)
                            if _ok:
                                st.success("✅ PIN 碼已重設！")
                                st.rerun()
                            else:
                                st.error(f"❌ {_err}")

                _pin_show_keys = False   # 鎖定狀態：隱藏金鑰管理

            else:
                # ── 已解鎖 ───────────────────────────────
                _lk_col, _ = st.columns([2, 8])
                _lk_col.success("🔓 PIN 已解鎖　本次頁面有效")
                if _lk_col.button("🔒 重新上鎖", key="btn_relock"):
                    st.session_state["_pin_unlocked"] = False
                    st.session_state["_pin_fernet"]   = None
                    st.rerun()

                with st.expander("🔑 重設 PIN 碼", expanded=False):
                    _ru_old  = st.text_input("現有 PIN 碼", type="password",
                                              placeholder="••••", key="reset_old_pin_unlocked")
                    _ru_new  = st.text_input("新 PIN 碼（4–8 位數字）", type="password",
                                              placeholder="••••", key="reset_new_pin_unlocked")
                    _ru_new2 = st.text_input("確認新 PIN 碼", type="password",
                                              placeholder="••••", key="reset_new_pin2_unlocked")
                    if st.button("🔄 重設 PIN 碼", key="btn_reset_pin_unlocked"):
                        if not _ru_old or not _ru_new or not _ru_new2:
                            st.error("請填寫所有欄位")
                        elif _ru_new != _ru_new2:
                            st.error("新 PIN 碼兩次輸入不一致")
                        elif not _ru_new.isdigit() or not (4 <= len(_ru_new) <= 8):
                            st.error("新 PIN 碼須為 4–8 位純數字")
                        elif _uid_pin:
                            from module_storage import reset_pin_code
                            _ok, _err = reset_pin_code(_uid_pin, _ru_old, _ru_new)
                            if _ok:
                                st.success("✅ PIN 碼已重設！")
                            else:
                                st.error(f"❌ {_err}")

        else:
            st.caption("在此輸入各服務的 API Key，系統將寫入 .env 並立即生效，無需重啟。")

        if _pin_show_keys:

            from module3_llm_summarizer import detect_provider_from_key

            # ── AI 模型金鑰（智慧單欄輸入）────────────────────
            st.markdown("### 🤖 AI 模型金鑰")
            st.caption("貼上任一家 AI 模型的 API Key，系統自動識別供應商並儲存到對應欄位。")

            _AI_PROVIDER_INFO = {
                "anthropic": {"label": "🟠 Anthropic（Claude）",  "env": "ANTHROPIC_API_KEY", "note": "⭐ 推薦 — 報告品質最佳"},
                "openai":    {"label": "🟢 OpenAI（GPT-4o）",     "env": "OPENAI_API_KEY",    "note": "可與 Claude 交叉驗證"},
                "google":    {"label": "🔴 Google（Gemini）",      "env": "GOOGLE_API_KEY",    "note": "Gemini 2.0 Flash 有免費方案"},
            }

            # 目前已設定狀態
            _set_ai = []
            for _pid, _pinfo in _AI_PROVIDER_INFO.items():
                _k = _get_key(_pinfo["env"])
                if _k:
                    _set_ai.append(f"{_pinfo['label']} `...{_k[-6:]}`")
            if _set_ai:
                st.success("✅ 已設定：" + "　　".join(_set_ai))
            else:
                st.warning("⚠️ 尚未設定任何 AI 模型金鑰。")

            smart_key_input = st.text_input(
                "貼上 AI API Key（自動識別供應商）",
                value="",
                type="password",
                placeholder="sk-ant-...  /  sk-proj-...  /  AIza...",
                key="smart_api_key_input",
            )

            # 即時偵測提示 + 模型選擇器
            _SMART_MODEL_LIST = {
                "anthropic": {
                    "latest": [
                        ("claude-opus-4-7",  "🔵 Claude Opus 4.7",    "旗艦，最強推理"),
                        ("claude-sonnet-4-6","🟠 Claude Sonnet 4.6 ⭐","推薦，速度/品質最佳平衡"),
                        ("claude-haiku-4-5", "🟡 Claude Haiku 4.5",   "輕量快速，最省費用"),
                    ],
                    "stable": [
                        ("claude-opus-4-5",  "🔵 Claude Opus 4.5",    "前代旗艦"),
                        ("claude-sonnet-4-5","🟠 Claude Sonnet 4.5",  "前代均衡"),
                        ("claude-haiku-3-5", "🟡 Claude Haiku 3.5",   "前代輕量"),
                    ],
                },
                "openai": {
                    "latest": [
                        ("gpt-5.5",      "🟢 GPT-5.5",       "旗艦，最強智能"),
                        ("gpt-5.4",      "🟢 GPT-5.4 ⭐",    "推薦，均衡性價比"),
                        ("gpt-5.4-mini", "🟩 GPT-5.4 Mini",  "輕量快速，最省費用"),
                    ],
                    "stable": [
                        ("gpt-4o",       "🟢 GPT-4o",        "前代旗艦"),
                        ("gpt-4o-mini",  "🟩 GPT-4o Mini",   "前代輕量"),
                        ("o3",           "🔷 o3",            "前代推理增強"),
                    ],
                },
                "google": {
                    "latest": [
                        ("gemini-3.1-pro-preview", "🔴 Gemini 3.1 Pro",       "旗艦（付費）"),
                        ("gemini-3-flash-preview",  "🔶 Gemini 3 Flash ⭐",   "推薦，免費方案可用"),
                        ("gemini-3.1-flash-lite",   "🟡 Gemini 3.1 Flash Lite","最省費用，免費方案可用"),
                    ],
                    "stable": [
                        ("gemini-2.5-pro",        "🔴 Gemini 2.5 Pro",        "前代旗艦（付費）"),
                        ("gemini-2.5-flash",      "🔶 Gemini 2.5 Flash",      "前代均衡，免費方案可用"),
                        ("gemini-2.5-flash-lite", "🟡 Gemini 2.5 Flash Lite", "前代輕量，免費方案可用"),
                    ],
                },
            }

            if smart_key_input.strip():
                _sprov, _senv = detect_provider_from_key(smart_key_input.strip())
                if _sprov:
                    _sinfo = _AI_PROVIDER_INFO[_sprov]
                    st.success(f"✅ 偵測到：{_sinfo['label']}　　{_sinfo['note']}")

                    # 偵測到供應商後，直接顯示該供應商的模型選擇
                    st.markdown(f"**選擇要使用的模型（{_sinfo['label']}）**")
                    _cur_sel_smart = list(st.session_state.get("selected_models", []))
                    _new_sel_smart = [m for m in _cur_sel_smart]  # copy

                    _sm_data = _SMART_MODEL_LIST.get(_sprov, {})
                    _sc1, _sc2 = st.columns(2)
                    with _sc1:
                        st.caption("🆕 最新版")
                        for _smid, _slabel, _snote in _sm_data.get("latest", []):
                            _sch = st.checkbox(
                                _slabel, value=_smid in _cur_sel_smart,
                                key=f"smart_chk_{_smid}", help=_snote,
                            )
                            if _sch:
                                if _smid not in _new_sel_smart:
                                    _new_sel_smart.append(_smid)
                            else:
                                if _smid in _new_sel_smart:
                                    _new_sel_smart.remove(_smid)
                    with _sc2:
                        st.caption("🔒 前代穩定版")
                        for _smid, _slabel, _snote in _sm_data.get("stable", []):
                            _sch = st.checkbox(
                                _slabel, value=_smid in _cur_sel_smart,
                                key=f"smart_chk_{_smid}", help=_snote,
                            )
                            if _sch:
                                if _smid not in _new_sel_smart:
                                    _new_sel_smart.append(_smid)
                            else:
                                if _smid in _new_sel_smart:
                                    _new_sel_smart.remove(_smid)

                    st.session_state["selected_models"] = _new_sel_smart if _new_sel_smart else _cur_sel_smart

                else:
                    st.warning("⚠️ 無法識別供應商，請確認 Key 格式（支援：`sk-ant-`、`sk-proj-`、`sk-`、`AIza`）")

            _col_save_ai, _ = st.columns([2, 8])
            if _col_save_ai.button("💾 驗證並儲存 AI 金鑰", type="primary", key="save_smart_key"):
                _k = smart_key_input.strip()
                if _k:
                    _sprov, _senv = detect_provider_from_key(_k)
                    if _sprov:
                        with st.spinner(f"驗證 {_AI_PROVIDER_INFO[_sprov]['label']} 金鑰中…"):
                            _ok, _vmsg = _validate_api_key(_senv, _k)
                        if _ok:
                            _save_api_key(_senv, _k)
                            st.success(_vmsg + "　金鑰已儲存並生效！")
                            st.rerun()
                        else:
                            st.error(_vmsg)
                    else:
                        st.error("❌ 無法識別供應商，請確認 Key 格式正確")
                else:
                    st.warning("請先輸入 API Key")

            # ── 已設定的 AI 金鑰刪除區 ────────────────────────
            _has_any_ai = any(_get_key(i["env"]) for i in _AI_PROVIDER_INFO.values())
            if _has_any_ai:
                st.markdown("**已設定的 AI 金鑰：**")
                _dcols = st.columns(len(_AI_PROVIDER_INFO))
                for _di, (_dpid, _dpinfo) in enumerate(_AI_PROVIDER_INFO.items()):
                    _dk = _get_key(_dpinfo["env"])
                    if _dk:
                        with _dcols[_di]:
                            st.caption(f"{_dpinfo['label']}　`...{_dk[-6:]}`")
                            if st.button(f"🗑️ 刪除", key=f"del_ai_{_dpid}", use_container_width=True):
                                _delete_api_key(_dpinfo["env"])
                                st.success(f"✅ {_dpinfo['label']} 金鑰已刪除")
                                st.rerun()

            with st.expander("🔧 進階：手動逐一設定各供應商金鑰", expanded=False):
                for _env_var, _label, _placeholder, _note in [
                    ("ANTHROPIC_API_KEY", "🟠 Anthropic（Claude）",  "sk-ant-...",  "⭐ 推薦 — 報告品質最佳"),
                    ("OPENAI_API_KEY",    "🟢 OpenAI（GPT-4o）",     "sk-proj-...", "可與 Claude 交叉驗證"),
                    ("GOOGLE_API_KEY",    "🔴 Google（Gemini）",      "AIza...",     "Gemini 2.0 Flash 有免費方案"),
                ]:
                    _cur = _get_key(_env_var)
                    _masked = f"...{_cur[-8:]}" if len(_cur) > 8 else ("已設定" if _cur else "")
                    _adv_set = bool(_cur)
                    st.caption(f"**{_label}** — {_note}")
                    _ac1, _ac2, _ac3 = st.columns([5, 1, 1])
                    _anv = _ac1.text_input(
                        f"_{_env_var}_adv",
                        value="", placeholder=_masked if _masked else _placeholder,
                        type="password", label_visibility="collapsed",
                        key=f"adv_inp_{_env_var}",
                    )
                    if _ac2.button("💾", key=f"adv_save_{_env_var}", help="驗證並儲存", use_container_width=True):
                        if _anv.strip():
                            with st.spinner(f"驗證 {_label} 金鑰中…"):
                                _ok, _vmsg = _validate_api_key(_env_var, _anv.strip())
                            if _ok:
                                _save_api_key(_env_var, _anv.strip())
                                st.success(_vmsg + "　已儲存")
                                st.rerun()
                            else:
                                st.error(_vmsg)
                        else:
                            st.warning("請輸入有效的 Key")
                    if _adv_set and _ac3.button("🗑️", key=f"adv_del_{_env_var}", help="刪除此金鑰", use_container_width=True):
                        _delete_api_key(_env_var)
                        st.success(f"✅ {_label} 金鑰已刪除")
                        st.rerun()
                    st.markdown("")

            st.divider()

            # ── 財經資料 API（各自獨立）──────────────────────
            st.markdown("### 📊 財經資料 API（選填）")
            st.caption("以下為增強型資料源，不設定也可正常使用 Yahoo Finance 基礎數據。")

            for env_var, label, placeholder, note in [
                ("MARKETAUX_API_KEY", "📰 Marketaux（財經新聞）",    "xxx...xxx", "高品質財經新聞（100次/天）"),
                ("FINNHUB_KEY",       "📊 Finnhub（個股數據/新聞）", "xxx...xxx", "個股新聞、推薦評等、財務指標"),
                ("FMP_KEY",           "🏦 FMP（多年估值預測）",       "xxx...xxx", "3年 EPS、F P/E、成長率預估"),
                ("ALPHA_VANTAGE_KEY", "📈 Alpha Vantage（備援）",     "xxx...xxx", "ForwardPE 備援（25次/天）"),
            ]:
                cur_val = _get_key(env_var)
                masked  = f"...{cur_val[-8:]}" if len(cur_val) > 8 else ("已設定" if cur_val else "")
                _is_set = bool(cur_val)

                st.markdown(f"**{label}** 🔵 選填")
                st.caption(note)

                col_inp, col_save, col_del = st.columns([5, 1, 1])
                new_val = col_inp.text_input(
                    f"_{env_var}",
                    value            = "",
                    placeholder      = masked if masked else placeholder,
                    type             = "password",
                    label_visibility = "collapsed",
                    key              = f"inp_{env_var}",
                )
                if col_save.button("💾", key=f"save_{env_var}", type="secondary", help="驗證並儲存", use_container_width=True):
                    if new_val.strip():
                        with st.spinner(f"驗證 {label} 金鑰中…"):
                            _ok, _msg = _validate_api_key(env_var, new_val.strip())
                        if _ok:
                            _save_api_key(env_var, new_val.strip())
                            st.success(_msg)
                            st.rerun()
                        else:
                            st.error(_msg)
                    else:
                        st.warning("請先輸入 Key 值")
                if _is_set and col_del.button("🗑️", key=f"del_{env_var}", type="secondary", help="刪除此金鑰", use_container_width=True):
                    _delete_api_key(env_var)
                    st.success(f"✅ {label} 金鑰已刪除")
                    st.rerun()
                st.markdown("")

    # ── Tab 2（已移除：雲端部署） ─────────────────────────
    if False:
        st.subheader("☁️ 部署到 Streamlit Community Cloud")
        st.markdown("免費取得永久網址，讓所有人點擊即可使用，無需安裝任何軟體。")

        st.divider()
        st.markdown("### 📋 部署前準備")
        st.info("""
**需要的帳號（皆免費）**
- 🐙 [GitHub](https://github.com) — 存放程式碼
- ☁️ [Streamlit Community Cloud](https://share.streamlit.io) — 免費雲端執行環境
        """)

        st.divider()
        st.markdown("### 🚀 部署步驟（約 10 分鐘）")

        with st.expander("步驟 1：建立 GitHub Repo 並上傳檔案", expanded=True):
            st.markdown("""
1. 登入 [github.com](https://github.com)，點右上角 **＋ → New repository**
2. 名稱填 `stock-war-room`（或任意名稱），選 **Private**（私有庫更安全）
3. 建好後，點 **uploading an existing file**，上傳以下檔案：

```
app.py
requirements.txt
.streamlit/config.toml
module1_data_fetcher.py
module1_news_engine.py
module1_watchlist.py
module2_discipline_warning.py
module3_llm_summarizer.py
module_stock_chart.py
```

> ⚠️ **不要上傳** `.env` 和 `watchlist.json`（含有你的 API 金鑰）
            """)

        with st.expander("步驟 2：連結 Streamlit Cloud", expanded=True):
            st.markdown("""
1. 前往 [share.streamlit.io](https://share.streamlit.io)，用 GitHub 帳號登入
2. 點 **New app**
3. 選你的 Repository → Branch: `main` → Main file path: `app.py`
4. 點 **Deploy！**

等待約 1–3 分鐘，完成後系統會給你一個永久網址：
```
https://你的帳號-stock-war-room-app-xxxx.streamlit.app
```
            """)

        with st.expander("步驟 3（選填）：設定預設 API 金鑰", expanded=False):
            st.markdown("""
若你想讓使用者進來就能直接用（不需要自己輸入 Key），可以在 Streamlit Cloud 設定 Secrets：

1. 在 Streamlit Cloud 應用頁面，點 **⋮ → Settings → Secrets**
2. 貼入以下格式（填入你自己的金鑰）：

```toml
ANTHROPIC_API_KEY = "sk-ant-你的金鑰"
FINNHUB_KEY       = "你的Finnhub金鑰"
FMP_KEY           = "你的FMP金鑰"
MARKETAUX_API_KEY = "你的金鑰"
```

> 💡 不設定也沒關係，使用者進入時會看到引導彈窗，自行輸入自己的金鑰。
            """)

        st.divider()
        st.markdown("### 📤 分享網址給其他人")
        st.success("""
部署完成後，複製 Streamlit 給你的網址，直接傳給其他人即可。

**使用者流程：**
1. 點擊你分享的連結
2. 看到歡迎彈窗 → 點「前往 API 金鑰設定」
3. 輸入自己的 Anthropic API Key（[免費申請](https://console.anthropic.com)）
4. 即可使用完整功能
        """)

        st.divider()
        st.markdown("### 🔄 更新程式")
        st.markdown("""
日後修改 `app.py` 後，只需在 GitHub 網頁上傳新版檔案，
Streamlit Cloud 會**自動偵測並重新部署**，網址不會改變。
        """)

    # ── Tab 2：AI 模型申請指南 ───────────────────────────
    with tab_ai:
        st.subheader("🤖 AI 模型 API 申請指南")
        st.markdown("""
> 💡 **建議策略**：以 Claude Sonnet 作為主報告模型，加上 Gemini 2.0 Flash（免費）作為交叉驗證。
        """)
        st.html("""
<div style="overflow-x:auto; -webkit-overflow-scrolling:touch;">
<table style="border-collapse:collapse; min-width:520px; font-size:13px; width:100%;">
<thead><tr style="background:#f0f2f6;">
  <th style="padding:8px 10px; text-align:left; border:1px solid #ddd;">模型</th>
  <th style="padding:8px 10px; text-align:left; border:1px solid #ddd;">申請網址</th>
  <th style="padding:8px 10px; text-align:left; border:1px solid #ddd;">免費額度</th>
  <th style="padding:8px 10px; text-align:left; border:1px solid #ddd;">付費方案</th>
  <th style="padding:8px 10px; text-align:left; border:1px solid #ddd;">特點</th>
</tr></thead>
<tbody>
<tr><td style="padding:7px 10px; border:1px solid #eee;"><b>Claude Sonnet 4.5</b> 🟠</td>
    <td style="padding:7px 10px; border:1px solid #eee;"><a href="https://console.anthropic.com" target="_blank">console.anthropic.com</a></td>
    <td style="padding:7px 10px; border:1px solid #eee;">新帳號試用額度</td>
    <td style="padding:7px 10px; border:1px solid #eee;">依 token 計費</td>
    <td style="padding:7px 10px; border:1px solid #eee;">品質最高，推薦首選</td></tr>
<tr style="background:#fafafa;"><td style="padding:7px 10px; border:1px solid #eee;"><b>Claude Haiku 3.5</b> 🟡</td>
    <td style="padding:7px 10px; border:1px solid #eee;">同上</td>
    <td style="padding:7px 10px; border:1px solid #eee;">同上</td>
    <td style="padding:7px 10px; border:1px solid #eee;">最低成本</td>
    <td style="padding:7px 10px; border:1px solid #eee;">速度快，適合摘要</td></tr>
<tr><td style="padding:7px 10px; border:1px solid #eee;"><b>GPT-4o</b> 🟢</td>
    <td style="padding:7px 10px; border:1px solid #eee;"><a href="https://platform.openai.com" target="_blank">platform.openai.com</a></td>
    <td style="padding:7px 10px; border:1px solid #eee;">試用額度 $5</td>
    <td style="padding:7px 10px; border:1px solid #eee;">依 token 計費</td>
    <td style="padding:7px 10px; border:1px solid #eee;">跨語言強，可交叉驗證</td></tr>
<tr style="background:#fafafa;"><td style="padding:7px 10px; border:1px solid #eee;"><b>Gemini 2.0 Flash</b> 🔴</td>
    <td style="padding:7px 10px; border:1px solid #eee;"><a href="https://aistudio.google.com" target="_blank">aistudio.google.com</a></td>
    <td style="padding:7px 10px; border:1px solid #eee;"><b>每天 1500 次免費</b></td>
    <td style="padding:7px 10px; border:1px solid #eee;">付費更高頻</td>
    <td style="padding:7px 10px; border:1px solid #eee;">完全免費可測試</td></tr>
</tbody></table>
</div>
""")

        st.divider()
        st.markdown("**如何選擇模型組合？**")
        st.info("""
- **單一報告（預設）**：選 Claude Sonnet 4.5，品質穩定、上下文理解強
- **雙模型對比**：加選 Gemini 2.0 Flash（免費），交叉驗證報告可信度
- **三模型全比較**：再加選 GPT-4o，三方視角最完整但成本較高
        """)

    # ── Tab 3：財經資料 API 推薦 ────────────────────────
    with tab_data:
        st.subheader("📊 財經資料 API 推薦")
        st.markdown("### 資料來源優先順序設計")
        st.html("""
<div style="overflow-x:auto; -webkit-overflow-scrolling:touch;">
<table style="border-collapse:collapse; min-width:480px; font-size:13px; width:100%;">
<thead><tr style="background:#f0f2f6;">
  <th style="padding:8px 10px; border:1px solid #ddd;">優先級</th>
  <th style="padding:8px 10px; border:1px solid #ddd;">來源</th>
  <th style="padding:8px 10px; border:1px solid #ddd;">用途</th>
  <th style="padding:8px 10px; border:1px solid #ddd;">免費額度</th>
  <th style="padding:8px 10px; border:1px solid #ddd;">申請</th>
</tr></thead>
<tbody>
<tr><td style="padding:7px 10px; border:1px solid #eee; text-align:center;"><b>P1</b></td>
    <td style="padding:7px 10px; border:1px solid #eee;"><b>FMP</b></td>
    <td style="padding:7px 10px; border:1px solid #eee;">多年 F P/E、EPS 預估、分析師目標價（最完整）</td>
    <td style="padding:7px 10px; border:1px solid #eee;">250次/天</td>
    <td style="padding:7px 10px; border:1px solid #eee;"><a href="https://financialmodelingprep.com" target="_blank">financialmodelingprep.com</a></td></tr>
<tr style="background:#fafafa;"><td style="padding:7px 10px; border:1px solid #eee; text-align:center;"><b>P2</b></td>
    <td style="padding:7px 10px; border:1px solid #eee;"><b>yfinance</b></td>
    <td style="padding:7px 10px; border:1px solid #eee;">個股報價、OHLC、52週高低、歷史均線</td>
    <td style="padding:7px 10px; border:1px solid #eee;">∞ 免費</td>
    <td style="padding:7px 10px; border:1px solid #eee;">無需申請</td></tr>
<tr><td style="padding:7px 10px; border:1px solid #eee; text-align:center;"><b>P2</b></td>
    <td style="padding:7px 10px; border:1px solid #eee;"><b>Finnhub</b></td>
    <td style="padding:7px 10px; border:1px solid #eee;">個股新聞、分析師評等、財務指標</td>
    <td style="padding:7px 10px; border:1px solid #eee;">60次/分鐘</td>
    <td style="padding:7px 10px; border:1px solid #eee;"><a href="https://finnhub.io" target="_blank">finnhub.io</a></td></tr>
<tr style="background:#fafafa;"><td style="padding:7px 10px; border:1px solid #eee; text-align:center;"><b>P3</b></td>
    <td style="padding:7px 10px; border:1px solid #eee;"><b>Marketaux</b></td>
    <td style="padding:7px 10px; border:1px solid #eee;">三大類別財經新聞（附股票代號標注）</td>
    <td style="padding:7px 10px; border:1px solid #eee;">100次/天</td>
    <td style="padding:7px 10px; border:1px solid #eee;"><a href="https://marketaux.com" target="_blank">marketaux.com</a></td></tr>
<tr><td style="padding:7px 10px; border:1px solid #eee; text-align:center;"><b>P4</b></td>
    <td style="padding:7px 10px; border:1px solid #eee;"><b>Alpha Vantage</b></td>
    <td style="padding:7px 10px; border:1px solid #eee;">ForwardPE 備援、總覽資料</td>
    <td style="padding:7px 10px; border:1px solid #eee;"><b>25次/天</b></td>
    <td style="padding:7px 10px; border:1px solid #eee;"><a href="https://alphavantage.co" target="_blank">alphavantage.co</a></td></tr>
<tr style="background:#fafafa;"><td style="padding:7px 10px; border:1px solid #eee; text-align:center;"><b>保底</b></td>
    <td style="padding:7px 10px; border:1px solid #eee;"><b>RSS 免費源</b></td>
    <td style="padding:7px 10px; border:1px solid #eee;">Reuters / BBC / TechCrunch 等</td>
    <td style="padding:7px 10px; border:1px solid #eee;">∞ 免費</td>
    <td style="padding:7px 10px; border:1px solid #eee;">無需申請</td></tr>
</tbody></table>
</div>
""")
        st.markdown("""
---

### 各來源強項說明

**✅ FMP（Financial Modeling Prep）** — 估值數據首選
- 三年 EPS 預估（2026/2027/2028）
- 分析師目標價（最低/中位/平均/最高）
- 多年 F P/E、F P/S、營收成長率
- 注意：部分外國 ADR 股票（如 TSM）的 EPS 為原始幣別，系統已自動過濾

**✅ Finnhub** — 個股情報首選
- 公司新聞（按股票代號精準抓取，7天內）
- 分析師評等（強買/買/持有/賣/強賣人數分布）
- 133 項財務指標（Beta、毛利率、成長率等）
- 免費方案無日限制（60次/分鐘）

**✅ yfinance（Yahoo Finance）** — 免費基礎數據
- 股價、OHLC、成交量、52週高低
- 2026/2027 EPS 與營收預估（yfinance Tier 2）
- 無需 API Key，完全免費

**⚠️ Alpha Vantage** — 備援使用
- 每天僅 25 次請求，緊急備援
- 提供 ForwardPE、AnalystTargetPrice
        """)

    # ── Tab 3：財經資料 API（已是 tab_data，無需變動）────
    # （系統資訊 Tab 已移除，使用者不需要看到）


# ════════════════════════════════════════════════════════
#  Page 5：版本更新紀錄
# ════════════════════════════════════════════════════════

elif page == "📝 版本更新紀錄":
    _render_navbar(back_to="🏠 戰情室主控台")
    st.markdown("## 📝 版本更新紀錄")
    st.caption("記錄每次迭代的新增功能、修正與調整，由最新版本往前排列。")
    st.divider()

    _CHANGELOG = [
        ("v1.31", "精品 UI/UX 全面改版", [
            ("新增", [
                "無側邊欄設計：移除傳統 Sidebar，改為固定頂部導覽列（毛玻璃效果），頁面切換改用首頁卡片入口 + 子頁面返回按鈕，操作更直覺。",
                "深淺色模式切換：頂部導覽列新增 🌙/☀️ 切換按鈕，CSS 變數驅動全站主題，深色模式採深邃藍黑色調 (#0F172A)，淺色模式保持潔白質感。",
                "精品登入頁：Google OAuth 登入頁改為全版置中卡片設計，帶毛玻璃漸層背景與金色 Logo，視覺大幅升級。",
                "首頁功能模組卡片：總經指標下方新增 4 格功能模組導覽卡片（自選股管理、模型設定、API設定、版本紀錄），取代側欄導覽。",
                "個股頁面大標題設計：股票代號與價格改用 HTML 精排，收盤價以 38px 等寬字體配合漲跌顏色顯示，視覺層次感更強。",
            ]),
            ("調整", [
                "KPI 指標卡片升級：六大總經指標卡片改用圓角 18px 設計，加入柔和陰影與等寬字體報價。",
                "深淺色模式主題色板：淺色 (#F8F9FA 背景 / #FFFFFF 卡片) 與深色 (#0F172A 背景 / #1E293B 卡片) 完整切換，文字、邊框、陰影全數隨主題調整。",
            ]),
        ]),
        ("v1.30", "PIN 碼零知識 API 金鑰保護", [
            ("安全新增", [
                "PIN 碼密碼鎖：使用者可在「API 金鑰管理」頁面設定 4–8 位數字 PIN，API 金鑰以 PBKDF2-HMAC-SHA256（26 萬次迭代）衍生的 Fernet 金鑰加密存入 Supabase，任何人（包括管理員）都無法查詢（零知識架構）。",
                "PIN 保護機制：設定 PIN 後，新增、刪除、儲存、檢視金鑰皆需先解鎖；同一頁面訪問解鎖一次即可操作所有功能；切換頁面或重整後自動重新上鎖。",
                "PIN 重設：鎖定狀態與解鎖狀態皆可重設 PIN，前提須先輸入現有 PIN 正確驗證；重設後所有金鑰以新 PIN 重新加密。",
                "向後相容：未設定 PIN 的用戶保持原有行為（伺服器端 ENCRYPTION_KEY 加密），不影響現有使用。",
            ]),
        ]),
        ("v1.29", "公開測試前全面安全強化", [
            ("安全修正", [
                "OAuth email_verified 驗證：Google 登入流程新增 verified_email 欄位檢查，未驗證信箱的帳號將被拒絕登入。",
                "XSS 防護強化：使用者名稱、頭像 URL、警戒規則文字、模型標籤等所有動態注入 HTML 的內容一律經 html.escape() 處理；頭像限縮為 Google 官方域名白名單，拒絕任意外部 URL。",
                "API Key 多用戶隔離修正：module1_data_fetcher 與 module1_news_engine 的 Finnhub / FMP / Marketaux Key 原從 os.environ 讀取（雲端跨 session 共用），改為優先讀取 session_keys，與其他模組架構一致，確保各用戶 Key 完全隔離。",
                "加密金鑰 Fallback 移除：module_storage.py 移除硬寫死的預設 ENCRYPTION_KEY，未設定時直接拒絕操作並顯示明確錯誤，不再靜默使用已知弱金鑰。",
                "錯誤訊息資訊洩漏修正：run_full_analysis() 與 save_user_data() 例外處理改為只顯示通用提示，完整 traceback 改寫至 server log，防止 API 路徑、資料庫連線字串等敏感細節外洩。",
                "股票代號格式驗證：新增股票時對代號進行正規表達式檢查（大寫字母 / 數字 / . - ^，最長 12 字元），防止任意字串傳入 yfinance。",
                "自訂模型 ID 格式驗證：自訂模型 ID 輸入框新增格式驗證（英數字及 . - _ : /，最長 100 字元）。",
                "custom_prompt 長度限制：投資偏好說明新增 500 字上限，UI 層即時顯示字數，DB 層同步 CHECK constraint 雙重保護。",
                "feedparser 無 Timeout 修正：RSS 新聞抓取改以 requests.get(timeout=8) 先取得內容再交由 feedparser 解析，避免網路異常無限等待。",
                "Supabase 錯誤訊息清理：雲端同步失敗時不再將原始例外訊息（含資料庫 URL）顯示於 UI。",
            ]),
            ("新增", [
                "API 金鑰刪除鍵：AI 模型金鑰（Anthropic / OpenAI / Google）與財經資料 API 金鑰（Marketaux / Finnhub / FMP / Alpha Vantage）各自新增「🗑️」刪除按鈕，一鍵清除並同步 Supabase。",
                "API 金鑰驗證機制：儲存前自動對各服務發起最小化測試請求確認金鑰有效且填入正確欄位，驗證失敗時顯示明確錯誤訊息，驗證通過才寫入儲存。",
            ]),
            ("調整", [
                "selected_models 預設值改為空陣列：新用戶登入後不預設任何 AI 模型，引導自行設定，避免誤以為系統內建特定模型。",
            ]),
        ]),
        ("v1.28", "個股 AI 戰術建議格式優化", [
            ("調整", [
                "自訂投資風格提示詞（custom_prompt）現在直接驅動 AI 輸出格式：使用者設定的分析框架會完整出現在 user_prompt 中，AI 依序逐項輸出，不再被系統 prompt 預設格式覆蓋。",
                "四欄位結尾結構強制附加：無論使用者是否設有自訂 prompt，AI 回覆結尾一律附上「操作方向 → 理由 → 關鍵價位 → 風險提示」四個標準欄位，確保每次建議都有完整的可操作結論。",
                "關鍵價位欄位依風格動態標注：有自訂 prompt 時，「關鍵價位」後方附加風格摘要說明，提醒 AI 依照使用者操作風格給出具體進出場條件。",
                "system_prompt 精簡化：移除舊有將 custom_prompt 注入系統提示詞的邏輯，改由 user_prompt 統一管理格式指令，避免格式衝突。",
            ]),
        ]),
        ("v1.27", "Yahoo Finance 限速修正 & 清單重整鍵", [
            ("修正", [
                "個股詳細頁面顯示「無法取得數據」：根本原因為 _fetch_ticker_data() 先呼叫 t.info，Yahoo Finance 限速（YFRateLimitError）觸發外層 except 直接返回 None；修正為先呼叫 t.history()（限速較寬鬆），再獨立 try/except 呼叫 t.info，限速時降級使用 t.fast_info（基於內部快取，不發 HTTP 請求）。",
                "fetch_stock_quick 快取 None 問題：@st.cache_data 會快取 None 回傳值，導致限速解除後仍持續顯示錯誤長達 5 分鐘；改為限速時拋出 RuntimeError，@st.cache_data 不快取例外，讓下次呼叫可重新嘗試。",
                "個股頁面錯誤訊息優化：限速時顯示明確說明（Yahoo Finance 目前限速，請稍等 1–2 分鐘後重試），不再顯示通用錯誤。",
            ]),
            ("新增", [
                "我的清單「🔄 重新整理」按鈕：新增股票或更新數據後，點擊即可立即重載清單，不需切換頁面再回來。",
            ]),
        ]),
        ("v1.25", "OAuth 安全強化", [
            ("新增", [
                "state 參數（CSRF 防護）：每次建立 Google 授權 URL 時產生隨機 state，存入 Session；callback 進來時比對 state，不符即拒絕，防止跨站請求偽造攻擊。",
                "state 用完即清除：登入成功後自動從 Session 移除 state，避免重複使用。",
            ]),
            ("說明", [
                "Google OAuth 專案檢查中的「採用安全的流程」警告，根本原因為缺少 state 參數；本版修正後符合 Google 對 Web 應用程式的安全規範，警告預計 1–3 天內自動消除。",
                "PKCE（程式碼交換驗證金鑰）經評估不適用：Streamlit WebSocket 重連機制導致 code_verifier 在 OAuth redirect 後遺失，造成登入失敗；考量本系統為具備 client_secret 的伺服器端 Web 應用，state + client_secret 已達 Google 要求的安全等級，故不實作 PKCE。",
            ]),
        ]),
        ("v1.24", "使用者體驗優化", [
            ("新增", [
                "個股頁面資料來源標籤：技術分析圖表、技術分析面、估值分析面、分析師目標價各區塊標題下方加入灰色小字，標示數據引用來源（Yahoo Finance / FMP）。",
                "分析等待時間提示：主控台「啟動完整分析」與個股「生成完整分析」按鈕點擊後，進度條上方顯示預計等待時間（主控台 30–90 秒、個股 20–45 秒），避免使用者誤以為當機。",
            ]),
            ("修正", [
                "主控台進度條假進度問題：原本所有進度值在 run_full_analysis() 執行前一次性設完，視覺上無意義；改為將 prog 物件傳入函式，在數據抓取（5%）、紀律評估（65%）、各模型呼叫（72–95%）等實際步驟中即時更新，進度條現在反映真實執行狀態。",
                "個股分析進度條：原本只有 spinner 無進度顯示；改為新聞搜尋（0%）→ 完成（40%）→ AI 呼叫（55–95%）→ 完成（100%）的真實進度更新。",
            ]),
        ]),
        ("v1.23", "LINE 外部瀏覽器相容", [
            ("修正", [
                "LINE / 社群 App 內建瀏覽器 Google 登入被封鎖：Google OAuth 拒絕從 LINE、Facebook、Instagram 等 App 內建瀏覽器發起的授權請求，本版整合進登入按鈕本身，無需額外說明。",
            ]),
            ("調整", [
                "登入按鈕流程重設計：按鈕目標 URL 改為 app?openExternalBrowser=1，利用 LINE 官方參數讓 LINE App 自動以外部瀏覽器（Safari / Chrome）重開頁面；外部瀏覽器載入後透過中繼頁自動跳轉至 Google OAuth。",
                "智慧瀏覽器偵測：JS 自動判斷是否為 LINE/FB 等內建瀏覽器；一般瀏覽器（電腦、手機外部瀏覽器）直接走 Google OAuth，不經過中繼頁，流程無感。",
                "備援機制：若瀏覽器環境限制 JavaScript 自動跳轉，中繼頁顯示提示框與手動按鈕確保流程不中斷。",
                "移除提示框：刪除前版登入頁下方的 LINE 用戶提示區塊，版面更簡潔。",
            ]),
        ]),
        ("v1.22", "介面優化 & 總經指標強化", [
            ("修正", [
                "自選股按鈕排版：個股名稱按鈕與刪除（✕）按鈕現在固定同行顯示，行動裝置不再換行。",
                "登入按鈕置中：以更高特異性的 CSS 選擇器修正 st.link_button 在手機上偏左的問題。",
                "US10Y 數據遺失：原用 period=\"1d\", interval=\"5m\" 在非交易時段（債券市場休市、週末）回傳空值；改為 period=\"5d\" 優先、period=\"1mo\" 保底的雙層備援機制，確保永遠取得最後一筆有效收盤價。",
                "Expander 內欄位換行：對 Expander 內的水平 Block 加入 flex-wrap: nowrap CSS，防止行動裝置上欄位意外折行。",
            ]),
            ("新增功能", [
                "道瓊工業指數（DJIA）：戰情室主控台指標卡片由 5 格擴充為滿版 6 格，新增道瓊指數即時報價與漲跌幅。",
                "指標中文標籤：六個風險指標卡片全數附上中文說明（恐慌指數、美債10年、美元指數、標普500、納斯達克、道瓊指數）。",
            ]),
            ("調整", [
                "側欄導覽標籤：「📚 教學指南」改為「📚 教學 & API設定」，去除換行問題；「🤖 模型與偏好」改為「⚙️ 模型與投資偏好」，統一圖示視覺大小，修正對齊錯位。",
            ]),
        ]),
        ("v1.21", "使用者帳號系統", [
            ("新增功能", [
                "Google 帳號登入：首頁新增 Google OAuth 登入入口，授權後自動識別使用者身份。",
                "雲端資料同步：自選股清單、AI 模型偏好、投資策略偏好設定自動存入 Supabase 雲端資料庫，跨裝置、跨瀏覽器皆可讀取。",
                "API 金鑰加密儲存：使用者的各平台 API 金鑰以 Fernet 對稱加密後存入資料庫，僅本人可解密讀取，不以明文保存。",
                "登出功能：側欄新增登出按鈕，清除本地 Session 資料。",
                "手動同步按鈕：側欄新增「☁️ 同步」按鈕，可隨時手動將當前設定推送至雲端。",
                "新用戶自動建檔：首次登入自動在 Supabase 建立空白使用者記錄，無需手動初始化。",
                "跨 Session API 金鑰隔離：修正雲端環境中多用戶共用同一 process 導致 API 金鑰互相污染的安全問題，每位使用者的金鑰完全隔離於各自的 Session State。",
            ]),
        ]),
        ("v1.16 – v1.20", "雲端部署 & 多用戶架構", [
            ("新增功能", [
                "v1.16：純網頁架構重構，手機響應式 CSS（768px 斷點），首次訪問導引彈窗。",
                "v1.17：多使用者雲端隔離架構，API 金鑰改存 session_keys，隱藏右上角工具列。",
                "v1.18：動態供應商偵測（detect_provider_from_key），單一智慧金鑰輸入欄。",
                "v1.19：最新模型清單更新，模型選擇 UI 重構為最新版 / 前代穩定版兩欄。",
                "v1.20：跨 Session API 金鑰隔離安全修復，移除 os.environ 寫入，確保金鑰物理隔離。",
            ]),
        ]),
        ("v1.11 – v1.15", "個股分析強化", [
            ("新增功能", [
                "v1.11：個股頁面獨立化，快取機制與重新整理按鈕。",
                "v1.12：技術分析面板，OHLC、Beta、成交量、52週區間雙欄表格。",
                "v1.13：接入 FMP 多年預估（2026/2027/2028 EPS / F P/E / F P/S），幣別合理性檢查。",
                "v1.14：接入 Finnhub 分析師推薦分布、目標價、個股新聞精準搜尋。",
                "v1.15：K 線圖優化，Categorical x 軸跳過週末空缺，y 軸可拖拽縮放。",
            ]),
        ]),
        ("v1.1 – v1.10", "核心模組建構", [
            ("新增功能", [
                "v1.1：數據抓取引擎（yfinance），三大指數 / VIX / US10Y / DXY / 個股，新聞引擎。",
                "v1.2：LLM 戰情摘要（module3），System Prompt 警戒等級 Persona 切換。",
                "v1.3：自選股系統（watchlist.json），八板塊分類，CLI 管理介面。",
                "v1.4：Streamlit UI 主控台，三頁面架構，警戒徽章，進度條。",
                "v1.5：Windows 啟動腳本（WarRoom_Launch.bat）。",
                "v1.6：估值指標（F P/E / P/S / 3年均值），新聞標題可點擊連結。",
                "v1.7：個股詳細頁面，Plotly 五子圖（K線 / 成交量 / MACD / KDJ / RSI）。",
                "v1.8：Marketaux 財經新聞 API 接入，三層保障來源。",
                "v1.9：版面大改版，報告結構重整。",
                "v1.10：個股新聞分析整合，生成完整分析一次輸出戰術建議 + 新聞影響。",
            ]),
        ]),
        ("v1.0", "架構設計與核心三模組", [
            ("奠基", [
                "確立「手動觸發、單次執行、嚴禁自動輪詢」核心原則。",
                "建立三模組職責分離架構：數據抓取 / 硬邏輯判斷 / LLM 語意彙整。",
                "設計資料流架構（Manual Trigger → M1 → M2 → M3）。",
                "實作 module2_discipline_warning.py：VIX / US10Y / CTA 硬邏輯閾值、FOMO 攔截、AlertLevel 四級警戒。",
            ]),
        ]),
    ]

    for ver, title, sections in _CHANGELOG:
        with st.expander(f"**{ver}　{title}**", expanded=(ver == "v1.31")):
            for sec_title, items in sections:
                st.markdown(f"**{sec_title}**")
                for item in items:
                    st.markdown(f"- {item}")
                st.markdown("")
