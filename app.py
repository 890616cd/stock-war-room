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
    initial_sidebar_state = "expanded",
)

# ── 全域 CSS ─────────────────────────────────────────────
st.markdown("""
<style>
/* ── Sidebar ───────────────────────── */
[data-testid="stSidebar"] { min-width: 220px; max-width: 220px; }
[data-testid="stSidebar"] .block-container { padding: 1rem 0.75rem; }

/* ── 警戒等級徽章 ───────────────────── */
.alert-green  { color: #0a5c47; background: #d4f5e9; padding: 5px 18px; border-radius: 20px; font-weight: 700; font-size: 13px; display: inline-flex; align-items: center; gap: 6px; border: 1px solid #a8e6d3; }
.alert-yellow { color: #7a4500; background: #fef3cd; padding: 5px 18px; border-radius: 20px; font-weight: 700; font-size: 13px; display: inline-flex; align-items: center; gap: 6px; border: 1px solid #fddfa0; }
.alert-red    { color: #8b1a1a; background: #fde8e8; padding: 5px 18px; border-radius: 20px; font-weight: 700; font-size: 13px; display: inline-flex; align-items: center; gap: 6px; border: 1px solid #f5b7b7; }
.alert-black  { color: #e8e8e8; background: #2c2c2c; padding: 5px 18px; border-radius: 20px; font-weight: 700; font-size: 13px; display: inline-flex; align-items: center; gap: 6px; border: 1px solid #555; }

/* ── 觸發規則卡片 ───────────────────── */
.rule-red  { border-left: 3px solid #e24b4a; padding: 8px 14px; margin: 5px 0; background: #fff5f5; border-radius: 0 8px 8px 0; font-size: 13px; line-height: 1.5; }
.rule-yell { border-left: 3px solid #f0a500; padding: 8px 14px; margin: 5px 0; background: #fffbf0; border-radius: 0 8px 8px 0; font-size: 13px; line-height: 1.5; }
.rule-blk  { border-left: 3px solid #555;    padding: 8px 14px; margin: 5px 0; background: #f5f5f5; border-radius: 0 8px 8px 0; font-size: 13px; line-height: 1.5; }

/* ── 指標卡片 ───────────────────────── */
[data-testid="stMetric"] {
    background: var(--background-color, #f9f9fb);
    border: 1px solid rgba(0,0,0,0.07);
    border-radius: 10px;
    padding: 10px 14px !important;
}
[data-testid="stMetricLabel"]  { font-size: 11px !important; font-weight: 600; letter-spacing: .5px; text-transform: uppercase; opacity: .65; }
[data-testid="stMetricValue"]  { font-size: 22px !important; font-weight: 700; }
[data-testid="stMetricDelta"]  { font-size: 12px !important; }

/* ── 分隔線細化 ─────────────────────── */
hr { margin: 12px 0 !important; opacity: .25; }

/* ── 報告 Markdown 優化 ──────────────── */
.stMarkdown h2 { font-size: 17px !important; margin-top: 18px !important; padding-bottom: 4px; border-bottom: 1px solid rgba(0,0,0,0.1); }
.stMarkdown h3 { font-size: 15px !important; margin-top: 14px !important; }
.stMarkdown p  { font-size: 14px; line-height: 1.7; }
.stMarkdown li { font-size: 14px; line-height: 1.6; }
.stMarkdown blockquote { border-left: 3px solid #4A90E2; padding-left: 12px; color: #555; font-size: 13px; }

/* ── 手機響應式優化（768px 以下）────── */
@media (max-width: 768px) {
    .block-container { padding: 0.5rem 0.8rem 2rem !important; }
    [data-testid="stSidebar"] { min-width: 80vw !important; max-width: 88vw !important; }
    [data-testid="stMetricValue"] { font-size: 17px !important; }
    [data-testid="stMetricLabel"] { font-size: 9px !important; }
    .stMarkdown p, .stMarkdown li { font-size: 13px !important; }
    .stTabs [data-baseweb="tab"] { font-size: 12px !important; padding: 6px 8px !important; }
    .stButton > button { min-height: 44px; font-size: 14px !important; }
}
/* 表格在小螢幕可橫向滾動 */
[data-testid="stDataFrame"] { overflow-x: auto !important; }
</style>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════
#  Session state 初始化
# ════════════════════════════════════════════════════════

def _init_state():
    defaults = {
        "market_data":    None,
        "assessment":     None,
        "market_analysis": None,   # 市場情緒儀表板 + 風險指標
        "last_run":       None,
        "running":        False,
        "run_step":       "",
        "selected_stock": None,   # {"symbol": str, "name": str}，None = 無選取
        "selected_models":     ["claude-sonnet-4-5"],
        "custom_prompt":       "",
        "multi_reports":       {},
        "stock_multi_reports": {},
        # 多使用者：每個 session 各自持有金鑰，不互相干擾
        "session_keys":        {},
        # 首次使用導引：已完成 → True，不再彈窗
        "setup_done":          False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()


# ════════════════════════════════════════════════════════
#  個股輕量報價抓取（yfinance 免費，TTL 5 分鐘快取）
# ════════════════════════════════════════════════════════

@st.cache_data(ttl=300, show_spinner=False)
def fetch_stock_quick(symbol: str, name: str):
    """從 yfinance 抓取個股報價＋估值，不依賴主分析流程。"""
    from module1_data_fetcher import _fetch_ticker_data
    return _fetch_ticker_data(symbol, name)


def _is_cloud() -> bool:
    """偵測是否在 Streamlit Community Cloud 執行"""
    return bool(
        os.getenv("STREAMLIT_SHARING_MODE")
        or "/mount/src/" in str(Path(__file__).resolve())
    )


def _get_key(env_var: str) -> str:
    """
    讀取 API 金鑰，優先順序：
      1. 本 session 使用者輸入（各使用者隔離）
      2. Streamlit Cloud Secrets（部署者選填，可作為預設）
      3. .env / 系統環境變數（本機執行）
    """
    session_val = st.session_state.get("session_keys", {}).get(env_var, "")
    if session_val:
        return session_val
    try:
        if env_var in st.secrets:
            return str(st.secrets[env_var])
    except Exception:
        pass
    return os.getenv(env_var, "")


def _save_api_key(env_var: str, value: str):
    """
    儲存 API Key：
      1. session_keys（本次 session 立即生效，各使用者隔離）
      2. os.environ（供模組 os.getenv 讀取，當次程序內有效）
      3. .env 檔（僅本機執行時持久化；雲端環境略過，避免污染共用容器）
    """
    # 1. Session state
    if "session_keys" not in st.session_state:
        st.session_state["session_keys"] = {}
    st.session_state["session_keys"][env_var] = value
    # 2. 當次程序
    os.environ[env_var] = value
    # 3. 持久化 .env（本機限定）
    if not _is_cloud():
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


# ════════════════════════════════════════════════════════
#  首次使用導引彈窗
# ════════════════════════════════════════════════════════

@st.dialog("👋 歡迎使用美股投資戰情室")
def _show_onboarding():
    st.markdown("""
系統需要 **AI 模型 API 金鑰**，才能生成市場分析與個股戰術報告。

#### 必填
🟠 **Anthropic Claude** — 核心 AI 分析引擎

#### 選填（多模型交叉驗證）
🟢 **OpenAI GPT-4o** · 🔴 **Google Gemini 2.0 Flash**（免費方案可用）

---

財經數據方面，系統已內建 **Yahoo Finance 免費源**，不需要任何金鑰即可抓取報價。
其他財經 API（FMP、Finnhub、Marketaux）為選填擴充。

> 💡 點擊「前往設定」可在教學指南頁面直接輸入金鑰，儲存後立即生效，無需重啟。
    """)
    st.divider()
    c1, c2 = st.columns(2)
    if c1.button("🔑 前往 API 金鑰設定", type="primary", use_container_width=True):
        st.session_state["setup_done"] = True
        st.session_state["nav_page"]   = "📚 教學指南"
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
    "other":         "其他",
}

def load_wl() -> dict:
    """
    讀取自選股清單。
    - 本機：從 watchlist.json 讀取，並同步到 session state
    - 雲端：每個使用者的 session state 即為其個人清單
    """
    # 優先使用 session state（雲端每人獨立；本機也作快取）
    if "_wl_data" in st.session_state:
        data = st.session_state["_wl_data"]
        for s in SECTOR_LABELS:
            data.setdefault(s, {})
        return data
    # 本機：從檔案載入
    if WATCHLIST_FILE.exists():
        try:
            with open(WATCHLIST_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            for s in SECTOR_LABELS:
                data.setdefault(s, {})
            st.session_state["_wl_data"] = data
            return data
        except Exception:
            pass
    # 預設空清單
    empty = {s: {} for s in SECTOR_LABELS}
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

def wl_add(symbol: str, name: str, sector: str) -> str:
    data = load_wl()
    sym  = symbol.upper().strip()
    # 如果已存在其他板塊，先移除
    for sec in data:
        if sym in data[sec]:
            if sec == sector:
                return f"⚠️ {sym} 已在「{SECTOR_LABELS[sec]}」板塊中"
            del data[sec][sym]
            break
    data[sector][sym] = name.strip()
    save_wl(data)
    return f"✅ {sym}（{name}）已加入【{SECTOR_LABELS[sector]}】"

def wl_remove(symbol: str) -> str:
    data = load_wl()
    sym  = symbol.upper().strip()
    for sec, stocks in data.items():
        if sym in stocks:
            name = stocks.pop(sym)
            save_wl(data)
            return f"✅ 已移除 {sym}（{name}）"
    return f"⚠️ {sym} 不在清單中"

def wl_total(data: dict) -> int:
    return sum(len(v) for v in data.values())


# ════════════════════════════════════════════════════════
#  分析執行（串接五個模組）
# ════════════════════════════════════════════════════════

def run_full_analysis():
    """
    依序執行模組一 → 模組二 → 模組三。
    進度更新寫入 session_state.run_step。
    """
    try:
        from module1_data_fetcher import run_data_fetcher
        from module2_discipline_warning import (
            DisciplineWarningProtocol, MarketSnapshot,
            format_emergency_output,
        )
        from module3_llm_summarizer import run_llm_summarizer

        # ── Module 1 ──
        st.session_state["run_step"] = "📡 正在抓取大盤指數 / VIX / US10Y / DXY..."
        market_data = run_data_fetcher()
        st.session_state["market_data"] = market_data

        # ── Module 2 ──
        st.session_state["run_step"] = "🔒 執行紀律警告協議（硬邏輯評估中）..."
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
            sel_models = st.session_state.get("selected_models", ["claude-sonnet-4-5"])
            sys_p  = build_system_prompt(assessment, market_data, custom_p)
            user_p = build_user_prompt(market_data)
            multi: dict = {}
            for mid in sel_models:
                lbl = MODEL_CATALOG.get(mid, {}).get("label", mid)
                st.session_state["run_step"] = f"🤖 {lbl} 生成市場情緒分析..."
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
        st.session_state["run_step"] = "✅ 分析完成"

    except Exception as e:
        st.session_state["run_step"] = f"❌ 執行失敗：{e}"
        st.session_state["report"]   = f"**系統錯誤**\n\n```\n{e}\n```\n\n請確認環境變數與模組檔案是否齊全。"



# ════════════════════════════════════════════════════════
#  個股詳細頁面
# ════════════════════════════════════════════════════════

def render_stock_detail(symbol: str, name: str):
    """個股詳細頁面：K線圖 + 估值指標 + 近期新聞（獨立於主分析運行）"""
    from module_stock_chart import fetch_chart_data, build_stock_chart

    # ── 返回 / 重新整理按鈕 ────────────────────────────────
    btn_back, btn_refresh, _ = st.columns([2, 2, 6])
    if btn_back.button("← 返回自選股管理", type="secondary"):
        st.session_state["selected_stock"] = None
        st.rerun()
    if btn_refresh.button("🔄 重新整理數據", type="secondary"):
        fetch_stock_quick.clear()          # 清除 yfinance 快取，強制重新抓取
        st.rerun()

    st.divider()

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
            stock = fetch_stock_quick(symbol, name)

    if stock is None:
        st.error(f"無法取得 {symbol} 數據，請確認代號正確或稍後重試。")
        return

    # ── 標題列 ────────────────────────────────────────────
    col_title, col_chg = st.columns([3, 2])
    with col_title:
        st.markdown(f"## {stock.symbol} &nbsp; {stock.name}")
    with col_chg:
        color  = "normal" if stock.change_pct >= 0 else "inverse"
        sign   = "+" if stock.change_pct >= 0 else ""
        st.metric(
            label = "最新收盤",
            value = f"${stock.price:,.2f}",
            delta = f"{sign}{stock.change_pct:.2f}%",
        )

    import pandas as pd

    # ── K 線圖（標題 + 股價之後即呈現）──────────────────────
    st.markdown("#### 📈 技術分析圖表（近一年日K）")
    with st.spinner(f"正在載入 {stock.symbol} 圖表數據..."):
        df  = fetch_chart_data(stock.symbol, period="1y")
        fig = build_stock_chart(df, stock.symbol, stock.name)
    st.plotly_chart(fig, use_container_width=True, config={
        "scrollZoom":     True,
        "displayModeBar": True,
        "modeBarButtonsToRemove": ["lasso2d", "select2d"],
        "modeBarButtonsToAdd":    ["toggleSpikelines"],
        "toImageButtonOptions": {
            "format": "png",
            "filename": f"{stock.symbol}_chart",
            "height": 780, "width": 1400, "scale": 2,
        },
    })
    st.caption("💡 拖拽右側刻度可縮放 y 軸區間；滾輪縮放時間區間；雙擊還原視圖。")

    st.divider()

    # ════════════════════════════════════════════════════
    #  技術分析面
    # ════════════════════════════════════════════════════
    st.markdown("#### 📊 技術分析面")

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
        st.dataframe(
            pd.DataFrame({
                "指標": ["開盤價", "最高價", "最低價", "收盤價", "Beta（相對大盤波動）",
                         _cur_val_label, _hist_val_label],
                "數值": [
                    f"${stock.open_price:,.2f}"  if stock.open_price  else "N/A",
                    f"${stock.high_price:,.2f}"  if stock.high_price  else "N/A",
                    f"${stock.low_price:,.2f}"   if stock.low_price   else "N/A",
                    f"${stock.price:,.2f}",
                    f"{stock.beta:.2f}"          if stock.beta        else "N/A",
                    _cur_val,
                    _hist_val,
                ],
            }),
            hide_index=True, use_container_width=True,
        )
    with col_t2:
        st.caption("成交量 / 52週區間")
        st.dataframe(
            pd.DataFrame({
                "指標": ["成交量", "均量（10日）", "量比", "52週高點", "52週低點", "距52週高", "52週區間位置"],
                "數值": [
                    _fmt_vol(stock.volume),
                    _fmt_vol(stock.avg_volume),
                    f"{stock.volume_ratio:.2f} 倍",
                    f"${stock.week52_high:,.2f}",
                    f"${stock.week52_low:,.2f}",
                    f"{stock.pct_from_52w_high:.1f}%",
                    f"{stock.range_position:.0f}%",
                ],
            }),
            hide_index=True, use_container_width=True,
        )

    st.divider()

    # ════════════════════════════════════════════════════
    #  估值分析面
    # ════════════════════════════════════════════════════
    st.markdown("#### 💹 估值分析面")

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

    st.dataframe(
        pd.DataFrame({
            "財年":          ["2026", "2027", "2028（通常無數據）"],
            "預估 EPS":      [_fmt_eps(stock.eps_est_2026),
                              _fmt_eps(stock.eps_est_2027),
                              _fmt_eps(stock.eps_est_2028)],
            pe_label:        pe_disp,
            "年營收成長率":   [_fmt_pct(stock.rev_growth_2026),
                              _fmt_pct(stock.rev_growth_2027),
                              _fmt_pct(stock.rev_growth_2028)],
            "EPS 年成長率":  [_fmt_pct(stock.eps_growth_2026),
                              _fmt_pct(stock.eps_growth_2027),
                              _fmt_pct(stock.eps_growth_2028)],
        }),
        hide_index=True, use_container_width=True,
    )

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

## 🎯 {stock.symbol} 當前戰術建議

**警戒等級：{level}**

**操作方向：** 加碼 / 減碼 / 觀望 / 停損（四擇一，加粗標示）

**理由：** 2–3 句，引用上方數據，不得憑空捏造。

**關鍵價位：** 支撐位與壓力位（從區間位置與52週高低點推算）。

**風險提示：** 此標的在當前警戒等級下最主要的下行風險。

---

## 📰 {stock.symbol} 近期焦點新聞分析

針對上方每一則新聞進行分析。若無新聞直接寫「近 3 日內無相關新聞」。

每則格式（嚴格照此，空一行分隔）：

**[來源] [標題](連結URL)**
- 影響：利多 / 利空 / 中性待觀察（三選一）
- 分析：一句話，說明此新聞對 {stock.symbol} 的潛在影響"""

            # ── Step 3：多模型呼叫 ────────────────────────
            from module3_llm_summarizer import call_model, MODEL_CATALOG
            sel = st.session_state.get("selected_models", ["claude-sonnet-4-5"])
            custom_p = st.session_state.get("custom_prompt", "")
            sys_p_stock = (
                "你是一位謹慎的量化交易副官。"
                "根據提供的數據給出個股操作建議，並分析近期新聞對該標的的影響。"
                "所有判斷必須基於提供的數據，不得憑空捏造任何數字。"
                + (f"\n\n[使用者偏好]\n{custom_p}" if custom_p.strip() else "")
            )
            multi_res: dict = {}
            for mid in sel:
                lbl = MODEL_CATALOG.get(mid, {}).get("label", mid)
                with st.spinner(f"🤖 {lbl} 正在分析 {stock.symbol}..."):
                    res = call_model(mid, sys_p_stock, user_prompt)
                    multi_res[mid] = res
            st.session_state[tactic_key] = multi_res
            st.rerun()


# ── 首次訪問：無 API Key 時彈出設定導引 ──────────────────
if not _get_key("ANTHROPIC_API_KEY") and not st.session_state.get("setup_done"):
    _show_onboarding()

with st.sidebar:
    st.markdown("### ⚔️ 美股投資戰情室")
    st.caption("AI 副官系統 · 手動觸發架構")
    st.divider()

    page = st.radio(
        "導覽",
        ["🏠 戰情室主控台", "📋 自選股管理", "🤖 模型與偏好", "📚 教學指南"],
        label_visibility = "collapsed",
        key = "nav_page",
    )

    st.divider()

    # ── 系統狀態（簡潔版）────────────────────────────────
    api_key        = _get_key("ANTHROPIC_API_KEY")
    openai_key     = _get_key("OPENAI_API_KEY")
    google_key     = _get_key("GOOGLE_API_KEY")
    marketaux_key  = _get_key("MARKETAUX_API_KEY")
    finnhub_key_sb = _get_key("FINNHUB_KEY")
    fmp_key_sb     = _get_key("FMP_KEY")

    # ── AI 模型 ──────────────────────────────────────────
    st.caption("🤖 AI 分析模型")
    from module3_llm_summarizer import MODEL_CATALOG
    sel_models_sb = st.session_state.get("selected_models", ["claude-sonnet-4-5"])
    _key_map = {
        "anthropic": api_key,
        "openai":    openai_key,
        "google":    google_key,
    }
    for mid in sel_models_sb:
        cat = MODEL_CATALOG.get(mid, {})
        prov = cat.get("provider", "")
        has_key = bool(_key_map.get(prov, ""))
        if has_key:
            st.markdown(
                f"<span style='font-size:12px'>{cat.get('icon','🤖')} {cat.get('label', mid)}</span>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"<span style='font-size:12px; color:#aaa'>{cat.get('icon','🤖')} {cat.get('label', mid)}　<em>金鑰未設定</em></span>",
                unsafe_allow_html=True,
            )

    st.divider()

    # ── 財經資料來源 ─────────────────────────────────────
    st.caption("📡 財經資料來源")
    _sources = [
        ("yfinance",   "Yahoo Finance",  True,              "報價 / 基本面"),
        ("fmp",        "FMP",            bool(fmp_key_sb),  "多年估值預測"),
        ("finnhub",    "Finnhub",        bool(finnhub_key_sb), "個股新聞 / 評等"),
        ("marketaux",  "Marketaux",      bool(marketaux_key),  "三類財經新聞"),
    ]
    for key, name, active, note in _sources:
        if active:
            st.markdown(
                f"<span style='font-size:12px'>🟢 <b>{name}</b> <span style='color:#888'>— {note}</span></span>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"<span style='font-size:12px; color:#aaa'>⚪ {name} <span style='color:#bbb'>— {note}</span></span>",
                unsafe_allow_html=True,
            )

    st.divider()
    if st.session_state["last_run"]:
        st.caption(f"🕐 上次執行：{st.session_state['last_run']}")
    else:
        st.caption("尚未執行分析")



# ════════════════════════════════════════════════════════
#  頂層路由：個股詳細頁面（優先於所有頁面判斷）
# ════════════════════════════════════════════════════════

_sel = st.session_state.get("selected_stock")
if _sel is not None:
    render_stock_detail(_sel["symbol"], _sel["name"])

# ════════════════════════════════════════════════════════
#  Page 1：戰情室主控台
# ════════════════════════════════════════════════════════

elif page == "🏠 戰情室主控台":
    st.header("戰情室主控台")

    # ── 警戒等級徽章 ──────────────────────────────────────
    assessment = st.session_state.get("assessment")
    if assessment:
        lv = assessment.alert_level.value.upper()
        labels = {
            "GREEN":  ("🟢 GREEN  正常分析模式",  "alert-green"),
            "YELLOW": ("🟡 YELLOW 謹慎警戒模式", "alert-yellow"),
            "RED":    ("🔴 RED    風險中斷模式",  "alert-red"),
            "BLACK":  ("⚫ BLACK  黑天鵝防禦",    "alert-black"),
        }
        text, cls = labels.get(lv, (lv, "alert-green"))
        st.markdown(f'<div class="{cls}">{text}</div>', unsafe_allow_html=True)
        st.markdown("")
    else:
        st.markdown('<div class="alert-green">── 等待首次分析</div>', unsafe_allow_html=True)
        st.markdown("")

    # ── 總經指標 ──────────────────────────────────────────
    md = st.session_state.get("market_data")
    c1, c2, c3, c4, c5 = st.columns(5)

    def _mc(col, label, val, delta=None, color=None):
        col.metric(label=label, value=val, delta=delta)

    if md:
        sp_chg = round((md.sp500 - md.sp500_prev) / md.sp500_prev * 100, 2) if md.sp500_prev else 0
        nq_chg = round((md.nasdaq - md.nasdaq_prev) / md.nasdaq_prev * 100, 2) if md.nasdaq_prev else 0
        c1.metric("VIX",    f"{md.vix:.2f}")
        c2.metric("US10Y",  f"{md.us10y:.3f}%")
        c3.metric("DXY",    f"{md.dxy:.2f}")
        c4.metric("S&P 500", f"{md.sp500:,.0f}", f"{sp_chg:+.2f}%")
        c5.metric("NASDAQ",  f"{md.nasdaq:,.0f}", f"{nq_chg:+.2f}%")
    else:
        c1.metric("VIX",    "──")
        c2.metric("US10Y",  "──")
        c3.metric("DXY",    "──")
        c4.metric("S&P 500","──")
        c5.metric("NASDAQ", "──")

    st.divider()

    # ── 啟動按鈕 ─────────────────────────────────────────
    col_btn, col_hint = st.columns([2, 5])
    with col_btn:
        run_disabled = not bool(api_key)
        if st.button(
            "🚀 啟動完整分析",
            disabled  = run_disabled,
            use_container_width = True,
            type      = "primary",
        ):
            with st.spinner("正在執行…"):
                prog = st.progress(0, text="初始化...")
                steps = [
                    (20, "📡 抓取大盤 / VIX / 總經指標..."),
                    (48, "📰 抓取三大類別新聞（保底各 3 則）..."),
                    (68, "🔒 紀律警告協議（硬邏輯評估）..."),
                    (88, "🤖 Claude 生成市場情緒分析..."),
                ]
                for pct, txt in steps:
                    prog.progress(pct, text=txt)
                run_full_analysis()
                prog.progress(100, text="✅ 完成")
            st.rerun()

    with col_hint:
        if not api_key:
            st.warning("請先確認 ANTHROPIC_API_KEY 已在 .env 設定")
        else:
            st.caption("手動觸發 · 單次執行 · 零自動輪詢")

    # ── 觸發規則區塊 ─────────────────────────────────────
    if assessment and assessment.triggered_rules:
        st.divider()
        lv  = assessment.alert_level.value.upper()
        cls = "rule-red" if lv in ("RED","BLACK") else "rule-yell" if lv == "YELLOW" else "rule-blk"
        for rule in assessment.triggered_rules:
            st.markdown(f'<div class="{cls}">⚡ {rule}</div>', unsafe_allow_html=True)
        st.markdown("")

    if assessment and assessment.fomo_intercept:
        st.error("🚨 **FOMO 攔截訊號觸發** — 請勿在當前市場環境下追高或無支撐接刀")
        for s in assessment.fomo_signals:
            st.warning(f"⚠️ {s}")

    # ── 市場情緒儀表板：多模型報告 ────────────────────────────────
    multi_rpts = st.session_state.get("multi_reports", {})
    if multi_rpts:
        st.divider()
        valid = {mid: r for mid, r in multi_rpts.items() if not r.get("error")}
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
                        c1.metric("⏱ 生成時間",    f"{r.get('elapsed_sec', '?')} 秒")
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
    st.header("自選股管理")
    tab_list, tab_add = st.tabs(["📋 我的清單", "➕ 新增股票"])

        # ── 我的清單 ────────────────────────────────────────
    with tab_list:
        wl_data = load_wl()
        total   = wl_total(wl_data)
        st.caption(f"共 {total} 檔股票　（點擊名稱查看詳細頁面）")

        if total == 0:
            st.info("清單為空，請至「新增股票」頁面加入")
        else:
            md = st.session_state.get("market_data")
            stock_obj_map = {}
            if md and md.watchlist:
                for sector_stocks in md.watchlist.values():
                    for s in sector_stocks:
                        stock_obj_map[s.symbol] = s

            for sec_key, label in SECTOR_LABELS.items():
                stocks_raw = wl_data.get(sec_key, {})
                if not stocks_raw:
                    continue
                with st.expander(f"【{label}】{len(stocks_raw)} 檔", expanded=True):
                    for sym, name in list(stocks_raw.items()):
                        s_obj = stock_obj_map.get(sym)
                        col_btn, col_sym, col_price, col_chg, col_val, col_rm = \
                            st.columns([2.5, 1.2, 1.5, 1.2, 2.5, 1])
                        with col_btn:
                            if st.button(f"📊 {name}", key=f"detail_{sym}",
                                         use_container_width=True):
                                st.session_state["selected_stock"] = {
                                    "symbol": sym, "name": name
                                }
                                st.rerun()
                        col_sym.markdown(f"`{sym}`")
                        if s_obj:
                            col_price.markdown(f"${s_obj.price:,.2f}")
                            sign = "+" if s_obj.change_pct >= 0 else ""
                            col_chg.markdown(f"{sign}{s_obj.change_pct:.2f}%")
                            if s_obj.is_profitable:
                                fpe = f"{s_obj.forward_pe:.1f}x" if s_obj.forward_pe else "N/A"
                                col_val.caption(f"F P/E: {fpe}")
                            else:
                                fps = f"{s_obj.forward_ps:.2f}x" if s_obj.forward_ps else "N/A"
                                col_val.caption(f"F P/S: {fps}")
                        else:
                            col_price.markdown("──")
                            col_chg.markdown("──")
                            col_val.markdown("──")
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
                new_sym  = st.text_input("股票代號", placeholder="例：NVDA").upper().strip()
            with col_b:
                new_name = st.text_input("股票名稱", placeholder="例：NVIDIA")

            new_sec = st.selectbox(
                "板塊",
                options = list(SECTOR_LABELS.keys()),
                format_func = lambda x: SECTOR_LABELS[x],
            )

            submitted = st.form_submit_button("➕ 加入清單", type="primary", use_container_width=True)
            if submitted:
                if not new_sym or not new_name:
                    st.error("請填入代號與名稱")
                else:
                    msg = wl_add(new_sym, new_name, new_sec)
                    if msg.startswith("✅"):
                        st.success(msg)
                    else:
                        st.warning(msg)

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
#  Page 3：模型與偏好設定
# ════════════════════════════════════════════════════════

elif page == "🤖 模型與偏好":
    st.header("🤖 模型與偏好設定")

    from module3_llm_summarizer import MODEL_CATALOG

    # ── 可用模型選擇 ──────────────────────────────────────
    st.subheader("AI 模型選擇")
    st.caption("勾選執行分析時要使用的模型。多選時報告將分頁對比顯示，並附上各模型生成時間。")

    _env_keys = {
        "ANTHROPIC_API_KEY": _get_key("ANTHROPIC_API_KEY"),
        "OPENAI_API_KEY":    _get_key("OPENAI_API_KEY"),
        "GOOGLE_API_KEY":    _get_key("GOOGLE_API_KEY"),
    }
    cur_sel = st.session_state.get("selected_models", ["claude-sonnet-4-5"])
    new_sel = []

    col_m1, col_m2 = st.columns(2)
    providers_order = [
        ("anthropic", "🟠 Anthropic Claude"),
        ("openai",    "🟢 OpenAI GPT"),
        ("google",    "🔴 Google Gemini"),
    ]
    col_idx = 0
    for prov, prov_label in providers_order:
        models_in_prov = [(mid, cat) for mid, cat in MODEL_CATALOG.items() if cat["provider"] == prov]
        col = col_m1 if col_idx % 2 == 0 else col_m2
        col_idx += 1
        with col:
            st.markdown(f"**{prov_label}**")
            key_available = bool(_env_keys.get(models_in_prov[0][1]["env_key"], "")) if models_in_prov else False
            if not key_available:
                st.caption(f"⚠️ {models_in_prov[0][1]['env_key']} 未設定，請至教學指南設定")
            for mid, cat in models_in_prov:
                checked = st.checkbox(
                    f"{cat['icon']} {cat['label']}",
                    value     = mid in cur_sel,
                    disabled  = not key_available,
                    key       = f"chk_{mid}",
                )
                if checked and key_available:
                    new_sel.append(mid)

    if not new_sel:
        new_sel = ["claude-sonnet-4-5"]
    st.session_state["selected_models"] = new_sel
    st.caption(f"✅ 已選擇：{', '.join(MODEL_CATALOG.get(m,{}).get('label',m) for m in new_sel)}")

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
    col_save, col_clear, _ = st.columns([2, 2, 6])
    if col_save.button("💾 儲存偏好", type="primary"):
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

elif page == "📚 教學指南":
    st.header("📚 教學指南 & API 設定")

    tab_keys, tab_deploy, tab_ai, tab_data, tab_sys = st.tabs([
        "🔑 API 金鑰管理",
        "☁️ 雲端部署",
        "🤖 AI 模型申請",
        "📊 財經資料 API",
        "⚙️ 系統資訊",
    ])

    # ── Tab 1：API 金鑰管理 ──────────────────────────────
    with tab_keys:
        st.subheader("API 金鑰管理")
        if _is_cloud():
            st.info("☁️ **雲端模式**：金鑰僅儲存在本次 Session，離開後需重新輸入。每位使用者各自獨立，互不影響。")
        else:
            st.caption("在此輸入各服務的 API Key，系統將寫入 .env 並立即生效，無需重啟。")

        key_defs = [
            ("ANTHROPIC_API_KEY", "🟠 Anthropic（Claude）",       "sk-ant-...",    True,  "必填 — Claude 模型所需"),
            ("OPENAI_API_KEY",    "🟢 OpenAI（GPT-4o）",          "sk-proj-...",   False, "選填 — 啟用 GPT 系列模型"),
            ("GOOGLE_API_KEY",    "🔴 Google（Gemini）",           "AIza...",       False, "選填 — 啟用 Gemini 系列模型"),
            ("MARKETAUX_API_KEY", "📰 Marketaux（財經新聞）",     "xxx...xxx",     False, "選填 — 高品質財經新聞（100次/天）"),
            ("FINNHUB_KEY",       "📊 Finnhub（個股數據/新聞）",  "xxx...xxx",     False, "選填 — 個股新聞、推薦評等、財務指標"),
            ("FMP_KEY",           "🏦 FMP（多年估值預測）",        "xxx...xxx",     False, "選填 — 3年 EPS、F P/E、成長率預估"),
            ("ALPHA_VANTAGE_KEY", "📈 Alpha Vantage（備援）",      "xxx...xxx",     False, "選填 — ForwardPE 備援（25次/天）"),
        ]
        for env_var, label, placeholder, required, note in key_defs:
            cur_val = _get_key(env_var)
            masked  = f"...{cur_val[-8:]}" if len(cur_val) > 8 else ("已設定" if cur_val else "")
            st.markdown(f"**{label}** {'🔴 必填' if required else '🔵 選填'}")
            st.caption(note)
            col_inp, col_btn = st.columns([5, 1])
            new_val = col_inp.text_input(
                f"_{env_var}",
                value       = "",
                placeholder = masked if masked else placeholder,
                type        = "password",
                label_visibility = "collapsed",
                key         = f"inp_{env_var}",
            )
            if col_btn.button("儲存", key=f"save_{env_var}", type="primary" if required else "secondary"):
                if new_val.strip():
                    _save_api_key(env_var, new_val.strip())
                    st.success(f"✅ {label} 已儲存並生效")
                    st.rerun()
                else:
                    st.warning("請輸入有效的 Key 值")
            st.markdown("")

    # ── Tab 2：雲端部署指南 ───────────────────────────────
    with tab_deploy:
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

    # ── Tab 3：AI 模型申請指南 ───────────────────────────
    with tab_ai:
        st.subheader("🤖 AI 模型 API 申請指南")
        st.markdown("""
| 模型 | 申請網址 | 免費額度 | 付費方案 | 特點 |
|---|---|---|---|---|
| **Claude Sonnet 4.5** 🟠 | [console.anthropic.com](https://console.anthropic.com) | 新帳號有試用額度 | 依 token 計費 | 分析報告品質最高，推薦首選 |
| **Claude Haiku 3.5** 🟡 | 同上 | 同上 | 最低成本選項 | 速度快，適合快速摘要 |
| **GPT-4o** 🟢 | [platform.openai.com](https://platform.openai.com) | 試用額度 $5 | 依 token 計費 | 跨語言理解強，可交叉驗證 |
| **Gemini 2.0 Flash** 🔴 | [aistudio.google.com](https://aistudio.google.com) | **免費方案** 每天 1500 次 | 付費方案更高頻 | 完全免費可用於測試 |

> 💡 **建議策略**：以 Claude Sonnet 作為主報告模型，加上 Gemini 2.0 Flash（免費）作為交叉驗證。
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
        st.markdown("""
### 資料來源優先順序設計

| 優先級 | 來源 | 用途 | 免費額度 | 申請 |
|---|---|---|---|---|
| **P1** | **FMP** | 多年 F P/E、EPS 預估、分析師目標價（最完整） | 250次/天 | [financialmodelingprep.com](https://financialmodelingprep.com) |
| **P2** | **yfinance** | 個股報價、OHLC、52週高低、歷史均線（完全免費） | ∞ 免費 | 無需申請（Yahoo Finance） |
| **P2** | **Finnhub** | 個股新聞、分析師買/持/賣推薦、財務指標 | 60次/分鐘 | [finnhub.io](https://finnhub.io) |
| **P3** | **Marketaux** | 三大類別財經新聞（附股票代號標注） | 100次/天 | [marketaux.com](https://marketaux.com) |
| **P4** | **Alpha Vantage** | ForwardPE 備援、總覽資料 | **25次/天** | [alphavantage.co](https://alphavantage.co) |
| **保底** | **RSS 免費源** | Reuters / BBC / TechCrunch 等，無需 Key | ∞ 免費 | 無需申請 |

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

    # ── Tab 4：系統資訊 ─────────────────────────────────
    with tab_sys:
        st.subheader("📁 系統資訊")
        st.markdown("**快速啟動**")
        st.code("""
# 1. 安裝依賴
pip install streamlit yfinance anthropic requests feedparser \\
            python-dotenv plotly pandas numpy

# 選裝（啟用其他 AI 模型）
pip install openai                  # GPT-4o 系列
pip install google-generativeai     # Gemini 系列

# 2. 建立 .env（或在教學指南 > API 金鑰管理 頁面設定）
ANTHROPIC_API_KEY=sk-ant-你的金鑰
FINNHUB_KEY=你的Finnhub金鑰        # 推薦，免費申請
FMP_KEY=你的FMP金鑰                # 推薦，多年估值數據
MARKETAUX_API_KEY=你的金鑰          # 選填
OPENAI_API_KEY=sk-proj-...          # 選填，啟用 GPT
GOOGLE_API_KEY=AIza...              # 選填，啟用 Gemini（免費方案）

# 3. 啟動
streamlit run app.py
        """, language="bash")

        st.divider()
        st.subheader("系統模組")
        files_info = [
            ("app.py",                       "Streamlit UI 主程式"),
            ("module1_data_fetcher.py",       "模組一：多來源報價抓取（FMP+yfinance+Finnhub）"),
            ("module1_news_engine.py",        "模組一子模組：三類別新聞情報（Marketaux+Finnhub+RSS）"),
            ("module1_watchlist.py",          "模組一子模組：自選股清單管理"),
            ("module2_discipline_warning.py", "模組二：紀律警告協議（硬邏輯核心）"),
            ("module3_llm_summarizer.py",     "模組三：多模型 LLM 戰情摘要（Claude/GPT/Gemini）"),
            ("module_stock_chart.py",         "K線技術分析圖（Plotly）"),
            ("watchlist.json",                "自選股清單"),
            (".env",                          "API 金鑰（請勿分享或上傳至 Git）"),
        ]
        for fname, desc in files_info:
            exists = Path(fname).exists()
            st.markdown(f"{'✅' if exists else '❌'} `{fname}` — {desc}")

        st.divider()
        st.subheader("⚠️ 紀律警告閾值（模組二）")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("**VIX 恐慌指數**")
            st.markdown("🟡 黃燈：≥ 20.0\n🔴 紅燈：≥ 30.0\n⚫ 黑色：≥ 40.0")
        with c2:
            st.markdown("**US10Y 殖利率**")
            st.markdown("🟡 黃燈：≥ 4.30%\n🔴 紅燈：≥ 4.70%\n⚫ 黑色：≥ 5.20%")
        with c3:
            st.markdown("**S&P500 日跌幅**")
            st.markdown("🔴 紅燈：≤ -2.0%\n⚫ 黑天鵝熔斷：≤ -7.0%")
