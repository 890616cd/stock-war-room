"""
module3_llm_summarizer.py
模組三：LLM 戰情摘要生成器

職責分離原則：
  - 此模組只負責「語意彙整」與「報告格式化」
  - 所有數值比較與紅綠燈判斷已由模組二完成
  - LLM 收到的是預處理訊號，不是原始數字
"""

import os
import time
import anthropic
from datetime import datetime
from module2_discipline_warning import RiskAssessment, AlertLevel
from module1_data_fetcher import FullMarketData, StockData


# ══════════════════════════════════════════════
#  LLM 設定
# ══════════════════════════════════════════════

MODEL      = "claude-sonnet-4-5"
MAX_TOKENS = 2800

# ══════════════════════════════════════════════
#  多模型支援目錄
# ══════════════════════════════════════════════

MODEL_CATALOG: dict[str, dict] = {
    # ══ Anthropic Claude ══════════════════════════════════════════
    # 最新世代（2026）
    "claude-opus-4-7":    {"provider": "anthropic", "label": "Claude Opus 4.7",   "icon": "🔵", "env_key": "ANTHROPIC_API_KEY", "max_tokens": 4096},
    "claude-sonnet-4-6":  {"provider": "anthropic", "label": "Claude Sonnet 4.6", "icon": "🟠", "env_key": "ANTHROPIC_API_KEY", "max_tokens": 4096},
    "claude-haiku-4-5":   {"provider": "anthropic", "label": "Claude Haiku 4.5",  "icon": "🟡", "env_key": "ANTHROPIC_API_KEY", "max_tokens": 4096},
    # 前代穩定版（2025）
    "claude-opus-4-5":    {"provider": "anthropic", "label": "Claude Opus 4.5",   "icon": "🔵", "env_key": "ANTHROPIC_API_KEY", "max_tokens": 2800},
    "claude-sonnet-4-5":  {"provider": "anthropic", "label": "Claude Sonnet 4.5", "icon": "🟠", "env_key": "ANTHROPIC_API_KEY", "max_tokens": 2800},
    "claude-haiku-3-5":   {"provider": "anthropic", "label": "Claude Haiku 3.5",  "icon": "🟡", "env_key": "ANTHROPIC_API_KEY", "max_tokens": 2800},
    # ══ OpenAI ════════════════════════════════════════════════════
    # 最新世代（2026）
    "gpt-5.5":            {"provider": "openai",    "label": "GPT-5.5",           "icon": "🟢", "env_key": "OPENAI_API_KEY",     "max_tokens": 4096},
    "gpt-5.4":            {"provider": "openai",    "label": "GPT-5.4",           "icon": "🟢", "env_key": "OPENAI_API_KEY",     "max_tokens": 4096},
    "gpt-5.4-mini":       {"provider": "openai",    "label": "GPT-5.4 Mini",      "icon": "🟩", "env_key": "OPENAI_API_KEY",     "max_tokens": 4096},
    # 前代穩定版（2025）
    "gpt-4o":             {"provider": "openai",    "label": "GPT-4o",            "icon": "🟢", "env_key": "OPENAI_API_KEY",     "max_tokens": 2800},
    "gpt-4o-mini":        {"provider": "openai",    "label": "GPT-4o Mini",       "icon": "🟩", "env_key": "OPENAI_API_KEY",     "max_tokens": 2800},
    "o3":                 {"provider": "openai",    "label": "o3（推理增強）",     "icon": "🔷", "env_key": "OPENAI_API_KEY",     "max_tokens": 2800},
    # ══ Google Gemini ═════════════════════════════════════════════
    # 最新世代（2026）
    "gemini-3.1-pro-preview":  {"provider": "google", "label": "Gemini 3.1 Pro",      "icon": "🔴", "env_key": "GOOGLE_API_KEY", "max_tokens": 4096},
    "gemini-3-flash-preview":  {"provider": "google", "label": "Gemini 3 Flash",       "icon": "🔶", "env_key": "GOOGLE_API_KEY", "max_tokens": 4096},
    "gemini-3.1-flash-lite":   {"provider": "google", "label": "Gemini 3.1 Flash Lite","icon": "🟡", "env_key": "GOOGLE_API_KEY", "max_tokens": 4096},
    # 前代穩定版（2025）
    "gemini-2.5-pro":          {"provider": "google", "label": "Gemini 2.5 Pro",       "icon": "🔴", "env_key": "GOOGLE_API_KEY", "max_tokens": 2800},
    "gemini-2.5-flash":        {"provider": "google", "label": "Gemini 2.5 Flash",     "icon": "🔶", "env_key": "GOOGLE_API_KEY", "max_tokens": 2800},
    "gemini-2.5-flash-lite":   {"provider": "google", "label": "Gemini 2.5 Flash Lite","icon": "🟡", "env_key": "GOOGLE_API_KEY", "max_tokens": 2800},
}

# ══════════════════════════════════════════════
#  動態 Provider 偵測
# ══════════════════════════════════════════════

def detect_provider_from_key(key: str) -> tuple:
    """
    從 API Key 前綴自動偵測供應商。
    返回 (provider, env_var) 或 (None, None)。
    """
    k = key.strip()
    if k.startswith("sk-ant-"):
        return "anthropic", "ANTHROPIC_API_KEY"
    if k.startswith("sk-proj-") or (k.startswith("sk-") and not k.startswith("sk-ant-")):
        return "openai", "OPENAI_API_KEY"
    if k.startswith("AIza"):
        return "google", "GOOGLE_API_KEY"
    return None, None


def detect_provider_from_model_id(model_id: str) -> str:
    """
    從模型 ID 名稱推斷供應商。
    支援 MODEL_CATALOG 以外的任意自訂版本（如 gemini-2.5-pro、claude-opus-4）。
    """
    m = model_id.lower()
    if "claude" in m:
        return "anthropic"
    if any(x in m for x in ["gpt-", "o1-", "o3-", "o4-", "chatgpt", "o1", "o3", "o4"]):
        return "openai"
    if "gemini" in m:
        return "google"
    return "unknown"


# 警戒等級 → LLM 角色人設
# 透過 Persona 控制語氣偏向，避免高風險時 LLM 給出樂觀偏差
ALERT_PERSONA = {
    AlertLevel.GREEN:  (
        "資深量化分析師。語氣專業、冷靜、客觀。"
        "可以正常討論機會與風險。"
    ),
    AlertLevel.YELLOW: (
        "謹慎的風控顧問。語氣帶有明確的警惕感。"
        "強調風險優先於機會。每個建議都要搭配風險提示。"
    ),
    AlertLevel.RED: (
        "嚴格的戰術副官，處於風險中斷模式。"
        "語氣堅定、不妥協。明確拒絕任何形式的樂觀偏差。"
        "所有個股戰術建議都必須偏向防禦。"
        "若使用者有接刀或追高的跡象，必須直接點名警告。"
    ),
    AlertLevel.BLACK: (
        "危機處理指揮官，處於黑天鵝防禦模式。"
        "第一原則是保存資本，其次才是機會。"
        "不討論任何新的進場機會。"
        "所有建議圍繞在『如何減少損失』和『如何提高現金比例』。"
    ),
}

# 警戒等級 → 儀表板標題顯示
LEVEL_DISPLAY = {
    AlertLevel.GREEN:  "🟢 GREEN  ── 正常分析模式",
    AlertLevel.YELLOW: "🟡 YELLOW ── 謹慎警戒模式",
    AlertLevel.RED:    "🔴 RED    ── 風險中斷模式",
    AlertLevel.BLACK:  "⚫ BLACK  ── 黑天鵝防禦模式",
}


# ══════════════════════════════════════════════
#  System Prompt 建構器
# ══════════════════════════════════════════════

def _format_watchlist_table(watchlist: dict) -> str:
    """
    格式化自選股板塊表格，供 LLM 讀取。
    按板塊分組顯示，空板塊不顯示。
    """
    from module1_watchlist import SECTOR_LABELS, WatchlistSector
    if not watchlist:
        return "  （自選股清單為空）"

    sections = []
    for sector, stocks in watchlist.items():
        if not stocks:
            continue
        label = SECTOR_LABELS[sector]
        lines = [f"  [{label}]"]
        for s in stocks:
            vol_flag  = "  ★放量" if s.volume_ratio > 1.5 else ""
            near_high = "  (近高點)" if s.range_position > 80 else ""
            near_low  = "  (近低點)" if s.range_position < 20 else ""
            # 推薦彙整（有數據才顯示）
            rec_txt = ""
            if any(v is not None for v in [s.rec_strong_buy, s.rec_buy,
                                            s.rec_hold, s.rec_sell,
                                            s.rec_strong_sell]):
                b = (s.rec_strong_buy or 0) + (s.rec_buy or 0)
                h =  s.rec_hold or 0
                sl = (s.rec_sell or 0) + (s.rec_strong_sell or 0)
                rec_txt = f"  推薦：買{b}/持{h}/賣{sl}"

            lines.append(
                f"    {s.name:<12} ({s.symbol:<6}) ${s.price:>8.2f}"
                f"  今日 {s.change_pct:+.2f}%"
                f"  量比 {s.volume_ratio:.1f}x{vol_flag}"
                f"  距年高 {s.pct_from_52w_high:.1f}%"
                f"  區間 {s.range_position:.0f}%{near_high}{near_low}{rec_txt}"
            )
        sections.append("\n".join(lines))
    return "\n".join(sections)


def _format_index_table(indices: dict[str, StockData]) -> str:
    """格式化大盤指數表格"""
    lines = []
    for name, s in indices.items():
        lines.append(
            f"  {name:<14}  {s.price:>10,.2f}  ({s.change_pct:+.2f}%)"
        )
    return "\n".join(lines)


def build_system_prompt(assessment: RiskAssessment, market_data: FullMarketData, custom_preferences: str = "") -> str:
    """
    組合 System Prompt。
    核心設計：LLM 收到的是「已判斷完成的訊號」，不是「需要它去判斷的原始數字」。
    """
    alert_level  = assessment.alert_level
    persona      = ALERT_PERSONA[alert_level]
    level_label  = LEVEL_DISPLAY[alert_level]

    # 已觸發規則（由模組二硬邏輯輸出）
    rules_block = (
        "\n".join(f"  ▸ {r}" for r in assessment.triggered_rules)
        or "  （無規則觸發，市場正常）"
    )

    # FOMO 訊號區塊
    fomo_block = ""
    if assessment.fomo_intercept:
        fomo_lines = "\n".join(f"  ⚠ {s}" for s in assessment.fomo_signals)
        fomo_block = (
            "\n[FOMO 攔截訊號 ── 你必須在「持股戰術」版塊中明確強調以下警告，不得淡化]\n"
            f"{fomo_lines}\n"
        )

    # 最壞劇本（由模組二推演完成，LLM 直接引用，不得改寫數字）
    worst_case_block = ""
    if assessment.worst_case_scenario:
        worst_case_block = (
            "\n[最壞下殺劇本（由硬邏輯系統推演完成，請在「風險指標現況」版塊中完整呈現，"
            "不得刪減或軟化語氣）]\n"
            f"{assessment.worst_case_scenario}\n"
        )

    system_prompt = f"""你是一位擁有 15 年華爾街量化交易經驗的 AI 副官。
當前扮演角色：{persona}

════════════════════════════════════════════════════
當前警戒等級（由硬邏輯引擎判定，你不得質疑或自行修改）
  {level_label}
════════════════════════════════════════════════════

[模組二硬邏輯觸發規則]
{rules_block}
{fomo_block}{worst_case_block}
[市場數據快照 ── {market_data.timestamp}]

大盤指數：
{_format_index_table(market_data.indices)}

總經指標（API 精確值）：
  VIX     = {market_data.vix:.2f}
  US10Y   = {market_data.us10y:.3f}%
  DXY     = {market_data.dxy:.2f}

自選股監控（按板塊分類）：
{_format_watchlist_table(market_data.watchlist)}

════════════════════════════════════════════════════
你的行為準則（必須嚴格遵守）
════════════════════════════════════════════════════
1. 你只負責「語意彙整」、「情境解讀」與「報告格式化」。
   所有數值比較、指標觸發判斷已由模組二完成，你不得質疑。

2. 你不得自行創造任何數字、百分比預測或價格目標。
   只能引用上方已提供的數據，並加上語意脈絡。

3. 當警戒等級為 RED 或 BLACK 時：
   - 報告語氣必須明確偏向保守防禦
   - 不得在任何地方暗示「這是買入機會」
   - 不得使用「逢低布局」「長期看好」等語句（除非明確加上強烈警語）

4. 若系統注入了 FOMO 攔截訊號，
   你必須在「風險指標現況」版塊中以粗體明確標出，不得忽略。

5. 報告必須嚴格按照指定的三版塊 Markdown 格式輸出，
   不得增加、刪除或合併任何版塊。
   每個版塊控制在 150–250 字，言簡意賅。"""

    if custom_preferences.strip():
        system_prompt += f"""

════════════════════════════════════════════════════
使用者自定義分析偏好（請在報告中融入以下偏好與指標重點）
════════════════════════════════════════════════════
{custom_preferences.strip()}"""

    return system_prompt


# ══════════════════════════════════════════════
#  User Prompt 建構器（個股戰術專用）
# ══════════════════════════════════════════════

def build_stock_tactics_prompt(stock_data, assessment, market_data, custom_preferences: str = "") -> str:
    """
    為個股詳細頁面生成：
    1. 戰術建議（操作方向 / 理由 / 關鍵價位 / 風險提示）
    2. 近期焦點新聞分析（影響 + 分析，同 關鍵情報摘要 格式）
    """
    from module1_news_engine import NewsCategory

    level    = assessment.alert_level.value.upper()
    rules    = "\n".join(f"  - {r}" for r in assessment.triggered_rules) or "  （無觸發規則）"
    fomo_blk = ""
    if assessment.fomo_intercept:
        fomo_blk = "\n[FOMO 訊號已觸發，必須在建議中以粗體強調]\n" + \
                   "\n".join(f"  - {s}" for s in assessment.fomo_signals)

    val_info = ""
    if stock_data.is_profitable:
        fpe  = f"{stock_data.forward_pe:.1f}x"  if stock_data.forward_pe  else "N/A"
        hist = f"{stock_data.pe_3y_avg:.1f}x"   if stock_data.pe_3y_avg   else \
               (f"{stock_data.trailing_pe:.1f}x" if stock_data.trailing_pe else "N/A")
        val_info = f"F P/E = {fpe}，3年歷史均值 = {hist}"
    else:
        fps  = f"{stock_data.forward_ps:.2f}x"  if stock_data.forward_ps  else "N/A"
        hps  = f"{stock_data.trailing_ps:.2f}x" if stock_data.trailing_ps else "N/A"
        val_info = f"F P/S = {fps}，Trailing P/S = {hps}（尚未獲利）"

    # 多年估值快照
    multi_yr_lines = []
    for yr, eps, fpe_v, fps_v, rg, eg in [
        (2026, stock_data.eps_est_2026, stock_data.fpe_2026, stock_data.fps_2026,
               stock_data.rev_growth_2026, stock_data.eps_growth_2026),
        (2027, stock_data.eps_est_2027, stock_data.fpe_2027, stock_data.fps_2027,
               stock_data.rev_growth_2027, stock_data.eps_growth_2027),
        (2028, stock_data.eps_est_2028, stock_data.fpe_2028, stock_data.fps_2028,
               stock_data.rev_growth_2028, stock_data.eps_growth_2028),
    ]:
        if not any([eps, fpe_v, fps_v, rg, eg]):
            continue
        pe_ps = (f"F P/E={fpe_v:.1f}x" if fpe_v else
                 f"F P/S={fps_v:.2f}x" if fps_v else "")
        line = f"  {yr}：EPS=${eps:.2f}" if eps else f"  {yr}："
        if pe_ps:       line += f"  {pe_ps}"
        if rg is not None: line += f"  營收成長={rg:+.1f}%"
        if eg is not None: line += f"  EPS成長={eg:+.1f}%"
        multi_yr_lines.append(line)
    multi_yr_str = "\n".join(multi_yr_lines) if multi_yr_lines else "  （無多年預估數據）"

    # Finnhub 分析師推薦
    if any(v is not None for v in [stock_data.rec_strong_buy, stock_data.rec_buy,
                                    stock_data.rec_hold, stock_data.rec_sell,
                                    stock_data.rec_strong_sell]):
        b  = (stock_data.rec_strong_buy or 0) + (stock_data.rec_buy or 0)
        h  =  stock_data.rec_hold or 0
        sl = (stock_data.rec_sell or 0) + (stock_data.rec_strong_sell or 0)
        rec_str = (
            f"強買{stock_data.rec_strong_buy or 0} 買{stock_data.rec_buy or 0} "
            f"持{h} 賣{stock_data.rec_sell or 0} 強賣{stock_data.rec_strong_sell or 0}"
            f"（買入合計 {b}，賣出合計 {sl}）"
        )
    else:
        rec_str = "N/A"

    # 收集與此個股相關的近期新聞
    stock_news = []
    if market_data and market_data.news_by_category:
        for cat, items in market_data.news_by_category.items():
            for item in items:
                if stock_data.symbol in item.related_tickers:
                    url_md = f"[{item.title}]({item.url})" if item.url else item.title
                    stock_news.append(
                        f"  - [{item.source}] {url_md}"
                    )

    news_section = "\n".join(stock_news) if stock_news else "  （快取中無此標的相關新聞）"

    return f"""你是一位謹慎的量化交易副官。請根據提供的數據生成兩個版塊：個股戰術建議 + 近期新聞分析。

當前市場警戒等級：{level}
觸發規則：
{rules}
{fomo_blk}

個股資料：
  代號：{stock_data.symbol}
  名稱：{stock_data.name}
  現價：${stock_data.price:.2f}
  今日漲跌：{stock_data.change_pct:+.2f}%
  距52週高點：{stock_data.pct_from_52w_high:.1f}%
  52週區間位置：{stock_data.range_position:.0f}%（0%=年低，100%=年高）
  成交量比：{stock_data.volume_ratio:.1f}x（>1.5為放量）
  估值概覽：{val_info}
  分析師推薦分布（Finnhub）：{rec_str}
  市場環境：VIX={market_data.vix:.2f}  US10Y={market_data.us10y:.3f}%

多年估值預測（FMP + yfinance）：
{multi_yr_str}

與此標的相關的近期新聞：
{news_section}

請輸出以下兩個版塊：

## 🎯 {stock_data.symbol} 當前戰術建議

**警戒等級：{level}**

**操作方向：** 加碼 / 減碼 / 觀望 / 停損（四擇一，加粗標示）

**理由：** 2–3 句，引用上方數據，不得憑空捏造。

**關鍵價位：** 支撐位與壓力位（從區間位置與52週高低點推算）。

**風險提示：** 此標的在當前警戒等級下最主要的下行風險。

---

## 📰 {stock_data.symbol} 近期焦點新聞分析

針對上方每一則相關新聞進行分析。若無新聞直接寫「近期無相關新聞」。

每則格式（嚴格照此，空一行分隔）：

**[來源] [標題](原文連結URL)**
- 影響：利多 / 利空 / 中性待觀察（三選一）
- 分析：一句話，說明此新聞對 {stock_data.symbol} 的潛在影響

若有 FOMO 訊號，必須在操作方向後用粗體加注 ⚠️ FOMO 警告。
不得憑空捏造數字，所有判斷必須基於提供的數據。"""  + (
        f"""

════════════════════════════════════════════════════
使用者自定義分析偏好（請在報告中融入以下偏好與指標重點）
════════════════════════════════════════════════════
{custom_preferences.strip()}""" if custom_preferences.strip() else ""
    )


# ══════════════════════════════════════════════
#  User Prompt 建構器（戰情室報告）
# ══════════════════════════════════════════════

def build_user_prompt(market_data: FullMarketData) -> str:
    """
    注入三大類別財經情報（每類最多 3 則），生成戰情室報告。
    關鍵情報摘要涵蓋所有新聞，每則有標題連結、相關標的、影響、分析。
    """
    from module1_news_engine import format_news_for_llm
    news_block = format_news_for_llm(market_data.news_by_category)

    if not news_block.strip():
        news_block = "  （本次無新聞情報）"

    return f"""請根據系統指令與以下財經情報，生成今日戰情室報告。

[三大類別財經情報（每類最多 3 則，已自動標注相關標的，含原文連結）]
{news_block}

請嚴格按照以下 Markdown 格式輸出兩個固定版塊 + 一個新聞版塊：

## 📊 市場情緒儀表板

每個論點獨立一行，3–4 句：

- 大盤今日表現：...
- 板塊輪動：...
- 整體警戒判斷：...

## ⚠️ 風險指標現況

每個規則獨立一行。若有最壞劇本，完整列出各項推演。若有 FOMO 訊號以粗體標出。

## 📰 關鍵情報摘要

列出上方所有新聞，按三大類別分組。若某類別無新聞直接寫「本次無相關新聞」。

每則嚴格照以下格式（空一行分隔）：

**[來源] [標題](原文連結URL)**
- 相關標的：[代號1] [代號2]（無標的填「待評估」）
- 影響：利多 / 利空 / 中性待觀察（三選一）
- 分析：一句話，說明對市場或相關標的的潛在影響

類別標題格式：
### 🌍 國際情勢
### 🏛️ 政策動向
### ⚡ 產業動態"""


# ══════════════════════════════════════════════
#  多模型呼叫介面
# ══════════════════════════════════════════════

def _get_api_key(env_var: str) -> str:
    """
    讀取 API Key（Session 優先，避免雲端跨用戶污染）：
      1. Streamlit session_state（各使用者完全隔離）
      2. st.secrets（部署者設定的預設值）
      3. os.environ（本機執行 / .env 載入）
    """
    try:
        import streamlit as st
        session_val = st.session_state.get("session_keys", {}).get(env_var, "")
        if session_val:
            return session_val
        try:
            if env_var in st.secrets:
                return str(st.secrets[env_var])
        except Exception:
            pass
    except Exception:
        pass
    return os.getenv(env_var, "")


def _call_anthropic(model_id: str, system_prompt: str, user_prompt: str, max_tokens: int = 2800) -> dict:
    api_key = _get_api_key("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY 未設定")
    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model      = model_id,
        max_tokens = max_tokens,
        system     = system_prompt,
        messages   = [{"role": "user", "content": user_prompt}],
    )
    return {
        "text":          msg.content[0].text,
        "input_tokens":  msg.usage.input_tokens,
        "output_tokens": msg.usage.output_tokens,
    }


def _call_openai(model_id: str, system_prompt: str, user_prompt: str, max_tokens: int = 2800) -> dict:
    api_key = _get_api_key("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError("OPENAI_API_KEY 未設定")
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError("請安裝 openai 套件：pip install openai")
    client = OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model      = model_id,
        max_tokens = max_tokens,
        messages   = [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
    )
    u = resp.usage
    return {
        "text":          resp.choices[0].message.content,
        "input_tokens":  u.prompt_tokens     if u else 0,
        "output_tokens": u.completion_tokens if u else 0,
    }


def _call_gemini(model_id: str, system_prompt: str, user_prompt: str, max_tokens: int = 2800) -> dict:
    api_key = _get_api_key("GOOGLE_API_KEY")
    if not api_key:
        raise EnvironmentError("GOOGLE_API_KEY 未設定")
    try:
        import google.generativeai as genai
    except ImportError:
        raise ImportError("請安裝 google-generativeai 套件：pip install google-generativeai")
    genai.configure(api_key=api_key)
    m    = genai.GenerativeModel(model_name=model_id, system_instruction=system_prompt)
    resp = m.generate_content(user_prompt, generation_config={"max_output_tokens": max_tokens})
    try:
        it = resp.usage_metadata.prompt_token_count
        ot = resp.usage_metadata.candidates_token_count
    except Exception:
        it = ot = 0
    return {"text": resp.text, "input_tokens": it, "output_tokens": ot}


def call_model(model_id: str, system_prompt: str, user_prompt: str) -> dict:
    """
    統一多模型呼叫介面。支援 MODEL_CATALOG 已知型號及任意自訂模型 ID。
    返回：{text, elapsed_sec, input_tokens, output_tokens, provider, model_id, label, icon, error}
    """
    cat      = MODEL_CATALOG.get(model_id, {})
    # 優先從目錄取得 provider；若不在目錄（自訂版本），則由名稱推斷
    provider = cat.get("provider") or detect_provider_from_model_id(model_id)
    t0       = time.time()
    try:
        mx = cat.get("max_tokens", 2800)
        if   provider == "anthropic": res = _call_anthropic(model_id, system_prompt, user_prompt, mx)
        elif provider == "openai":    res = _call_openai(model_id, system_prompt, user_prompt, mx)
        elif provider == "google":    res = _call_gemini(model_id, system_prompt, user_prompt, mx)
        else: raise ValueError(f"無法識別模型供應商（{model_id}）。請確認模型 ID 包含 'claude' / 'gpt' / 'gemini' 等關鍵字。")
        res["error"] = None
    except Exception as e:
        res = {"text": "", "input_tokens": 0, "output_tokens": 0, "error": str(e)}

    res.update({
        "elapsed_sec": round(time.time() - t0, 1),
        "provider":    provider,
        "model_id":    model_id,
        "label":       cat.get("label", model_id),   # 自訂 ID 直接顯示 model_id
        "icon":        cat.get("icon",  "🤖"),
    })
    return res


# ══════════════════════════════════════════════
#  LLM 呼叫
# ══════════════════════════════════════════════

def call_llm(system_prompt: str, user_prompt: str) -> str:
    """向後相容介面（使用預設 Claude 模型）。新代碼請改用 call_model()。"""
    result = call_model(MODEL, system_prompt, user_prompt)
    if result.get("error"):
        raise RuntimeError(result["error"])
    print(
        f"  [{result['label']}] 完成 | "
        f"{result['elapsed_sec']}s | "
        f"Input: {result['input_tokens']} tokens | "
        f"Output: {result['output_tokens']} tokens"
    )
    return result["text"]


# ══════════════════════════════════════════════
#  報告格式化
# ══════════════════════════════════════════════

def format_final_report(
    llm_output:  str,
    assessment:  RiskAssessment,
    market_data: FullMarketData,
) -> str:
    """
    在 LLM 報告外層加上 Markdown 標頭與免責聲明。
    使用乾淨的 Markdown 語法，確保在 Streamlit 中正確渲染。
    """
    level_banner = {
        AlertLevel.GREEN:  "🟢 GREEN — 正常分析模式",
        AlertLevel.YELLOW: "🟡 YELLOW — 謹慎警戒模式",
        AlertLevel.RED:    "🔴 RED — 風險中斷模式",
        AlertLevel.BLACK:  "⚫ BLACK — 黑天鵝防禦模式",
    }[assessment.alert_level]

    # 觸發規則（Markdown 清單格式）
    rules_md = ""
    if assessment.triggered_rules:
        rule_lines = "\n".join(f"> - {r}" for r in assessment.triggered_rules)
        rules_md = f"\n{rule_lines}\n"

    header = (
        f"> **美股投資戰情室 — AI 副官戰情報告**\n"
        f"> {market_data.timestamp} ｜ {level_banner}\n"
        f"{rules_md}\n"
        f"---\n\n"
    )

    footer = (
        f"\n\n---\n"
        f"> ⚙ 硬邏輯引擎（模組二）負責所有數值判斷　"
        f"⚙ LLM（模組三）負責語意彙整　"
        f"⚙ 本報告不構成買賣建議，投資決策責任歸屬個人\n"
    )

    return header + llm_output + footer


# ══════════════════════════════════════════════
#  模組三主入口
# ══════════════════════════════════════════════

def run_llm_summarizer(
    assessment:  RiskAssessment,
    market_data: FullMarketData,
) -> str:
    """
    模組三主入口。
    接收模組二的風險評估 + 模組一的完整市場數據，生成戰情報告。
    """
    print("=" * 62)
    print("  模組三：LLM 戰情摘要生成  ──  開始執行")
    print("=" * 62)

    system_prompt = build_system_prompt(assessment, market_data)
    user_prompt   = build_user_prompt(market_data)

    raw_output   = call_llm(system_prompt, user_prompt)
    final_report = format_final_report(raw_output, assessment, market_data)

    return final_report


if __name__ == "__main__":
    # 快速單元測試（使用模擬綠燈數據）
    print("[模組三單元測試] 使用模擬綠燈市場數據...")
    print("請確認已設定 ANTHROPIC_API_KEY 環境變數。")
