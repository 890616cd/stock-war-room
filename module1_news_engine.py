"""
module1_news_engine.py
新聞情報引擎 ── 全新設計

設計哲學轉變：
  舊版：「我預設關注 Intel / Lip-Bu Tan / 半導體」→ 每次都看到一樣的人
  新版：「世界發生什麼事，系統發現它，再告訴我影響哪些標的」→ 有機探索

三大情報類別：
  1. 國際情勢  ── 地緣衝突、大宗商品連動、民生消費影響
  2. 政策動向  ── 聯準會、利率、財政政策、通膨
  3. 產業動態  ── 科技、半導體、企業公告、CEO 言論（誰在風口自然浮現）

標的標注邏輯：
  由硬邏輯規則（Regex）完成，不依賴 LLM
  → 發現「中東衝突」自動標注 [USO] [GLD] [LMT]
  → 發現「黃仁勳」自動標注 [NVDA] [SMH]
  → 發現「Fed 降息」自動標注 [TLT] [^TNX] [XLF]
"""

import re
import os
import requests
import feedparser
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


def _get_key(env_var: str) -> str:
    """
    安全讀取 API Key：
      1. session_keys（各用戶完全隔離，雲端主路徑）
      2. st.secrets（部署者預設值）
      3. os.environ（僅本機 CLI 執行時的 fallback）
    """
    try:
        import streamlit as st
        val = st.session_state.get("session_keys", {}).get(env_var, "")
        if val:
            return val
        try:
            if env_var in st.secrets:
                return str(st.secrets[env_var])
        except Exception:
            pass
    except Exception:
        pass
    return os.getenv(env_var, "")


# ══════════════════════════════════════════════
#  新聞類別定義
# ══════════════════════════════════════════════

class NewsCategory(Enum):
    GEOPOLITICS = "🌍 國際情勢"
    POLICY      = "🏛️ 政策動向"
    INDUSTRY    = "⚡ 產業動態"


# ══════════════════════════════════════════════
#  標的標注規則（硬邏輯，Regex 驅動）
#  格式：r"匹配關鍵字" → ["標的代號", ...]
#  設計原則：新聞內容決定標的，不是反過來
# ══════════════════════════════════════════════

TICKER_ANNOTATION_RULES: list[tuple[str, list[str]]] = [

    # ── 能源 / 大宗商品 ─────────────────────────────
    (r"\bWTI\b|West Texas|Brent crude|oil price",
        ["CL=F", "BZ=F", "USO", "BNO"]),

    (r"\boil\b|\bcrude\b|petroleum|OPEC|barrel|refin",
        ["USO", "XOM", "CVX", "COP", "MPC"]),

    (r"natural gas|LNG|pipeline",
        ["UNG", "LNG", "CQP"]),

    (r"\bgold\b|precious metal|safe.?haven",
        ["GLD", "IAU", "GDX"]),

    (r"\bsilver\b",
        ["SLV", "PSLV"]),

    (r"\bcopper\b|industrial metal",
        ["CPER", "FCX", "SCCO"]),

    (r"wheat|grain|crop|agriculture|food price",
        ["WEAT", "CORN", "ADM", "BG"]),

    (r"shipping|freight|container|supply chain disruption",
        ["ZIM", "MATX", "SBLK", "^BDI"]),

    # ── 地緣政治 ────────────────────────────────────
    (r"Middle East|Israel|Iran|Gaza|Lebanon|Hezbollah|Houthi|Red Sea",
        ["USO", "GLD", "LMT", "RTX", "HII"]),

    (r"Russia|Ukraine|war|NATO|sanction",
        ["USO", "GLD", "LMT", "RTX", "NOC", "WEAT"]),

    (r"China|Taiwan|strait|PLA|cross.?strait|CCP",
        ["TSM", "NVDA", "AMAT", "LRCX", "SMH", "EWJ"]),

    (r"North Korea|Korean peninsula",
        ["LMT", "RTX", "GLD"]),

    (r"India|Modi|South Asia",
        ["INDY", "EPI", "SMIN"]),

    (r"tariff|trade war|trade barrier|export ban|import duty",
        ["SMH", "SPY", "EEM", "FXI"]),

    # ── 美國政策 / 聯準會 ────────────────────────────
    (r"Federal Reserve|Fed Reserve|\bFed\b|FOMC|Powell|Waller|Bowman",
        ["TLT", "IEF", "^TNX", "GLD", "^GSPC"]),

    (r"interest rate|rate hike|rate cut|rate decision|basis point",
        ["TLT", "XLF", "KRE", "^TNX"]),

    (r"\bCPI\b|consumer price index|inflation|deflation|PCE",
        ["TIP", "GLD", "^TNX", "XLP"]),

    (r"dot plot|economic projection|rate forecast|terminal rate",
        ["TLT", "^TNX", "^GSPC"]),

    (r"US Treasury|bond yield|yield curve|10.?year|T-bill",
        ["TLT", "IEF", "SHY", "^TNX"]),

    (r"fiscal policy|government spending|debt ceiling|budget",
        ["TLT", "GLD", "^GSPC"]),

    (r"recession|economic slowdown|GDP|soft landing",
        ["GLD", "TLT", "XLP", "XLU"]),

    (r"job|unemployment|payroll|nonfarm|labor market",
        ["XLY", "XLP", "^GSPC", "SPY"]),

    (r"CHIPS Act|chip subsidy|semiconductor policy|export control",
        ["SMH", "INTC", "TSM", "AMAT", "LRCX"]),

    # ── 半導體 / AI ──────────────────────────────────
    (r"NVIDIA|Jensen Huang|Blackwell|H100|B200|NIM|CUDA",
        ["NVDA", "SMH", "SOXX"]),

    (r"\bAMD\b|Lisa Su|MI300|EPYC|Ryzen",
        ["AMD", "SMH"]),

    (r"TSMC|Taiwan Semiconductor|A16|N2|CoWoS",
        ["TSM", "SMH", "AMAT"]),

    (r"\bIntel\b|Lip.?Bu Tan|Gaudi|Lunar Lake|Intel Foundry|IFS|18A",
        ["INTC", "SMH"]),

    (r"\bASML\b|EUV|lithography|High.?NA",
        ["ASML", "SMH", "AMAT"]),

    (r"\bMicron\b|HBM|DRAM|NAND|memory chip",
        ["MU", "SMH", "WDC", "STX"]),

    (r"Broadcom|Qualcomm|MediaTek|custom chip|ASIC",
        ["AVGO", "QCOM", "SMH"]),

    (r"\bARM\b|ARM Holdings|CPU architecture",
        ["ARM", "NVDA", "QCOM"]),

    (r"semiconductor|chip shortage|wafer|foundry|fab",
        ["SMH", "SOXX", "AMAT", "LRCX"]),

    (r"artificial intelligence|AI model|large language|LLM|generative AI",
        ["NVDA", "AMD", "MSFT", "GOOGL", "META", "PLTR"]),

    (r"data center|hyperscaler|cloud computing|GPU cluster",
        ["NVDA", "AMD", "SMCI", "DELL", "AMZ"]),

    # ── 大型科技 ─────────────────────────────────────
    (r"\bApple\b|Tim Cook|iPhone|Mac|Vision Pro|AAPL",
        ["AAPL", "QQQ", "AVGO", "QCOM"]),

    (r"\bMicrosoft\b|Satya Nadella|Azure|Copilot|MSFT",
        ["MSFT", "QQQ", "NVDA"]),

    (r"\bTesla\b|Elon Musk|Cybertruck|FSD|Optimus|TSLA",
        ["TSLA", "RIVN", "NIO", "ALB"]),

    (r"\bMeta\b|Zuckerberg|Instagram|WhatsApp|Llama|Ray.?Ban",
        ["META", "QQQ"]),

    (r"\bAmazon\b|AWS|Jeff Bezos|Andy Jassy|AMZN",
        ["AMZN", "QQQ", "NVDA"]),

    (r"\bGoogle\b|Alphabet|Gemini|Waymo|DeepMind|GOOGL",
        ["GOOGL", "GOOG", "QQQ"]),

    (r"SpaceX|Starlink|rocket|launch|satellite internet",
        ["TSLA", "IRDM", "MAXR"]),

    # ── 金融 / 銀行 ──────────────────────────────────
    (r"bank|banking|JPMorgan|Goldman|Morgan Stanley|financial crisis",
        ["XLF", "KBE", "JPM", "GS", "MS"]),

    (r"crypto|Bitcoin|Ethereum|stablecoin|blockchain",
        ["IBIT", "FBTC", "COIN", "MSTR"]),

    # ── 汽車 / 電動車 ────────────────────────────────
    (r"EV|electric vehicle|BYD|Toyota|GM|Ford|automotive",
        ["TSLA", "LIT", "ALB", "GM", "F", "BYD"]),

    (r"lithium|battery|cathode|anode|solid.?state",
        ["ALB", "SQM", "LAC", "LIT"]),

    # ── 國防 / 航太 ──────────────────────────────────
    (r"defense|military|Pentagon|army|navy|weapon|missile|F-35",
        ["LMT", "RTX", "NOC", "GD", "HII"]),

    (r"aerospace|Boeing|Airbus|airline|aircraft",
        ["BA", "AIR", "UAL", "DAL"]),

    # ── 消費 / 民生 ──────────────────────────────────
    (r"consumer confidence|retail sales|spending|consumer price",
        ["XLY", "XLP", "AMZN", "WMT", "TGT"]),

    (r"housing|real estate|mortgage|Fed rate.+home",
        ["ITB", "XHB", "DHI", "LEN", "RDFN"]),
]


# ══════════════════════════════════════════════
#  分類搜尋查詢（廣泛動態，不指定人名）
#  讓新聞自然浮現誰在做什麼，而非預設誰重要
# ══════════════════════════════════════════════

CATEGORY_QUERIES = {
    NewsCategory.GEOPOLITICS: [
        "Middle East conflict oil market",
        "Russia Ukraine war commodity",
        "China Taiwan tension trade",
        "global sanctions trade impact",
        "geopolitical risk energy supply",
        "oil price OPEC production",
        "war inflation commodity price",
    ],
    NewsCategory.POLICY: [
        "Federal Reserve interest rate decision",
        "FOMC meeting inflation outlook",
        "Fed dot plot rate forecast",
        "US Treasury yield bond market",
        "inflation CPI PCE data",
        "US government policy economy",
        "tariff trade policy impact",
        "fiscal spending debt ceiling",
    ],
    NewsCategory.INDUSTRY: [
        "semiconductor technology announcement deal",
        "AI chip company partnership order",
        "tech CEO statement earnings",
        "product launch technology breakthrough",
        "merger acquisition technology company",
        "chip export restriction supply chain",
        "electric vehicle battery technology",
        "big tech earnings quarterly results",
    ],
}

# ══════════════════════════════════════════════
#  Finnhub 新聞類別分配關鍵詞
# ══════════════════════════════════════════════

_CATEGORY_PATTERNS = {
    NewsCategory.GEOPOLITICS: re.compile(
        r'\boil\b|\bcrude\b|\bwar\b|sanction|opec|russia|ukraine|china|taiwan|'
        r'iran|israel|middle.?east|conflict|geopolit|military|nato|'
        r'commodity|barrel|energy supply',
        re.IGNORECASE
    ),
    NewsCategory.POLICY: re.compile(
        r'federal reserve|\bfed\b|\bfomc\b|inflation|\binterest rate\b|'
        r'\byield\b|treasury|\bcpi\b|\bpce\b|tariff|fiscal|powell|'
        r'rate hike|rate cut|monetary policy|dot plot|debt ceiling',
        re.IGNORECASE
    ),
    NewsCategory.INDUSTRY: re.compile(
        r'semiconductor|chip|\bartificial intelligence\b|\bai\b|technology|'
        r'earnings|acquisition|merger|nvidia|tsmc|apple|microsoft|google|'
        r'tesla|quarterly results|revenue guidance|tech company|data center|'
        r'product launch|startup|venture',
        re.IGNORECASE
    ),
}


def _assign_category(text: str) -> Optional[NewsCategory]:
    """根據文字內容指派新聞類別（優先順序：地緣 → 政策 → 產業）"""
    for cat in [NewsCategory.GEOPOLITICS, NewsCategory.POLICY, NewsCategory.INDUSTRY]:
        if _CATEGORY_PATTERNS[cat].search(text):
            return cat
    return None


# RSS 源（按類別分組）
CATEGORY_RSS = {
    NewsCategory.GEOPOLITICS: [
        ("Reuters World",    "https://feeds.reuters.com/reuters/worldNews"),
        ("BBC World",        "https://feeds.bbci.co.uk/news/world/rss.xml"),
        ("AP World",         "https://rsshub.app/apnews/topics/world-news"),
        ("Reuters Commodities","https://feeds.reuters.com/reuters/commoditiesNews"),
    ],
    NewsCategory.POLICY: [
        ("Reuters Business", "https://feeds.reuters.com/reuters/businessNews"),
        ("Reuters Finance",  "https://feeds.reuters.com/news/economy"),
        ("MarketWatch",      "https://feeds.content.dowjones.io/public/rss/mw_topstories"),
        ("Barrons",          "https://feeds.barrons.com/barrons/home"),
    ],
    NewsCategory.INDUSTRY: [
        ("Reuters Tech",     "https://feeds.reuters.com/reuters/technologyNews"),
        ("Seeking Alpha",    "https://seekingalpha.com/market_currents.xml"),
        ("TechCrunch",       "https://techcrunch.com/feed/"),
        ("The Verge",        "https://www.theverge.com/rss/index.xml"),
    ],
}


# ══════════════════════════════════════════════
#  資料結構
# ══════════════════════════════════════════════

@dataclass
class EnrichedNewsItem:
    """
    每則新聞除了基本資訊外，
    額外包含：類別標籤 + 自動標注的相關標的
    """
    title:           str
    source:          str
    url:             str
    published_at:    str
    summary:         str
    category:        NewsCategory
    related_tickers: list[str]   # 硬邏輯自動標注，非 LLM 輸出
    matched_rules:   list[str]   # 命中的匹配規則（除錯用）


# ══════════════════════════════════════════════
#  標的自動標注引擎（硬邏輯）
# ══════════════════════════════════════════════

class TickerAnnotator:
    """
    以 Regex 規則將新聞文字映射到相關標的代號。
    不使用 LLM，確保一致性與零額外成本。
    """

    def annotate(self, text: str) -> tuple[list[str], list[str]]:
        """
        返回 (去重後的標的列表, 命中的規則描述列表)
        """
        text_combined = text.lower()
        tickers_seen  = {}   # 用 dict 保持順序且去重
        matched_rules = []

        for pattern, tickers in TICKER_ANNOTATION_RULES:
            if re.search(pattern, text, re.IGNORECASE):
                for t in tickers:
                    if t not in tickers_seen:
                        tickers_seen[t] = True
                matched_rules.append(pattern[:30])   # 截短，供除錯

        return list(tickers_seen.keys()), matched_rules


# ══════════════════════════════════════════════
#  新聞抓取（按類別）
# ══════════════════════════════════════════════

def _fetch_rss_for_category(
    category: NewsCategory,
    annotator: TickerAnnotator,
    max_per_feed: int = 15,
) -> list[EnrichedNewsItem]:
    """透過 RSS 抓取特定類別的新聞並標注標的"""
    items = []
    feeds = CATEGORY_RSS.get(category, [])

    for source_name, url in feeds:
        try:
            # 手動用 requests 抓取後再 parse，確保有 timeout 控制
            _rss_resp = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
            feed = feedparser.parse(_rss_resp.text)
            for entry in feed.entries[:max_per_feed]:
                title   = getattr(entry, "title",   "") or ""
                summary = getattr(entry, "summary", "") or ""
                combined = f"{title}. {summary}"

                tickers, rules = annotator.annotate(combined)

                items.append(EnrichedNewsItem(
                    title           = title,
                    source          = source_name,
                    url             = getattr(entry, "link",      ""),
                    published_at    = getattr(entry, "published", ""),
                    summary         = summary[:280],
                    category        = category,
                    related_tickers = tickers,
                    matched_rules   = rules,
                ))
        except Exception as e:
            print(f"    [RSS 警告] {source_name}：{e}")

    return items


def _fetch_marketaux_for_category(
    api_key:   str,
    category:  NewsCategory,
    annotator: TickerAnnotator,
    max_items: int = 10,
) -> list[EnrichedNewsItem]:
    """
    透過 Marketaux API 抓取財經新聞。
    Marketaux 專為股票新聞設計，直接支援按股票代號過濾。
    免費方案：100 次請求 / 天，無需信用卡。
    申請：https://www.marketaux.com/
    """
    # 每個類別對應不同的搜尋關鍵字
    CATEGORY_SEARCH = {
        NewsCategory.GEOPOLITICS: "oil,war,sanction,conflict,OPEC,Middle East,China,Taiwan",
        NewsCategory.POLICY:      "Federal Reserve,Fed,inflation,interest rate,CPI,Treasury,tariff",
        NewsCategory.INDUSTRY:    "semiconductor,AI,chip,earnings,acquisition,technology,NVIDIA,TSMC",
    }

    search_term = CATEGORY_SEARCH.get(category, "")
    if not search_term:
        return []

    params = {
        "api_token":  api_key,
        "search":     search_term,
        "language":   "en",
        "limit":      min(max_items * 2, 50),
        "sort":       "published_at",
        "filter_entities": "true",
    }

    try:
        resp = requests.get(
            "https://api.marketaux.com/v1/news/all",
            params  = params,
            timeout = 12,
        )
        resp.raise_for_status()
        data     = resp.json()
        articles = data.get("data", [])
        items    = []

        for a in articles:
            title    = a.get("title",       "") or ""
            desc     = a.get("description", "") or ""
            combined = f"{title}. {desc}"

            # Marketaux 自帶 entity（股票代號），直接用
            entity_tickers = []
            for ent in a.get("entities", []):
                sym = ent.get("symbol", "")
                if sym and len(sym) <= 6:   # 過濾掉太長的非股票代號
                    entity_tickers.append(sym.upper())

            # 再跑 Regex 補充（避免 entity 漏抓）
            regex_tickers, rules = annotator.annotate(combined)
            all_tickers = list(dict.fromkeys(entity_tickers + regex_tickers))  # 去重保序

            items.append(EnrichedNewsItem(
                title           = title,
                source          = a.get("source", "") or "Marketaux",
                url             = a.get("url",          ""),
                published_at    = a.get("published_at", ""),
                summary         = desc[:280],
                category        = category,
                related_tickers = all_tickers[:8],   # 最多顯示 8 個標的
                matched_rules   = rules,
            ))

        return items[:max_items]

    except Exception as e:
        print(f"    [Marketaux 警告] {category.value}：{e}")
        return []


def _fetch_finnhub_news(
    finnhub_key: str,
    annotator:   TickerAnnotator,
    max_per_cat: int = 8,
) -> dict[NewsCategory, list["EnrichedNewsItem"]]:
    """
    Finnhub /news?category=general → 一次抓取，按關鍵詞分配到三大類別。
    免費方案：60次/分鐘，無日限制。
    """
    result: dict[NewsCategory, list] = {
        NewsCategory.GEOPOLITICS: [],
        NewsCategory.POLICY:      [],
        NewsCategory.INDUSTRY:    [],
    }
    try:
        resp = requests.get(
            "https://finnhub.io/api/v1/news",
            params  = {"category": "general", "token": finnhub_key},
            timeout = 10,
        )
        if resp.status_code != 200:
            return result

        articles = resp.json()
        if not isinstance(articles, list):
            return result

        for a in articles[:120]:
            headline = (a.get("headline") or "").strip()
            summary  = (a.get("summary")  or "").strip()
            if not headline:
                continue

            combined = f"{headline}. {summary}"
            cat = _assign_category(combined)
            if cat is None:
                continue
            if len(result[cat]) >= max_per_cat:
                continue

            tickers, rules = annotator.annotate(combined)

            ts = a.get("datetime", 0)
            try:
                pub_str = datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M")
            except Exception:
                pub_str = ""

            result[cat].append(EnrichedNewsItem(
                title           = headline,
                source          = (a.get("source") or "Finnhub").strip(),
                url             = a.get("url",  "") or "",
                published_at    = pub_str,
                summary         = summary[:280],
                category        = cat,
                related_tickers = tickers,
                matched_rules   = rules,
            ))

    except Exception as e:
        print(f"    [Finnhub News 警告] {e}")

    return result


def _fetch_newsapi_for_category(
    api_key:  str,
    category: NewsCategory,
    annotator: TickerAnnotator,
    max_items: int = 10,
) -> list[EnrichedNewsItem]:
    """透過 NewsAPI.org 抓取新聞（備援方案）"""
    queries    = CATEGORY_QUERIES.get(category, [])
    if not queries:
        return []

    combined_q = " OR ".join(f'"{q}"' for q in queries[:3])
    params = {
        "q":        combined_q,
        "language": "en",
        "sortBy":   "publishedAt",
        "pageSize": max_items * 2,
        "apiKey":   api_key,
        "from":     (datetime.now() - timedelta(hours=20)).strftime("%Y-%m-%dT%H:%M:%S"),
    }

    try:
        resp = requests.get(
            "https://newsapi.org/v2/everything",
            params  = params,
            timeout = 10,
        )
        resp.raise_for_status()
        articles = resp.json().get("articles", [])
        items = []
        for a in articles:
            title    = a.get("title",       "") or ""
            desc     = a.get("description", "") or ""
            combined = f"{title}. {desc}"
            tickers, rules = annotator.annotate(combined)
            items.append(EnrichedNewsItem(
                title           = title,
                source          = a.get("source", {}).get("name", "Unknown"),
                url             = a.get("url",          ""),
                published_at    = a.get("publishedAt",  ""),
                summary         = desc[:280],
                category        = category,
                related_tickers = tickers,
                matched_rules   = rules,
            ))
        return items[:max_items]
    except Exception as e:
        print(f"    [NewsAPI 警告] {category.value}：{e}")
        return []


# ══════════════════════════════════════════════
#  排序與去重
# ══════════════════════════════════════════════

def _deduplicate(items: list[EnrichedNewsItem]) -> list[EnrichedNewsItem]:
    """以標題前 40 個字元去重（避免同則新聞多個 RSS 都出現）"""
    seen   = set()
    result = []
    for item in items:
        key = item.title[:40].lower().strip()
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def _rank_items(items: list[EnrichedNewsItem]) -> list[EnrichedNewsItem]:
    """
    排序邏輯：
    1. 有標的標注的優先（代表與市場連動性高）
    2. 標的越多越靠前（衝擊面越廣）
    """
    return sorted(items, key=lambda x: len(x.related_tickers), reverse=True)


# ══════════════════════════════════════════════
#  格式化輸出（供模組三 LLM 閱讀）
# ══════════════════════════════════════════════

def format_news_for_llm(news_by_category: dict[NewsCategory, list[EnrichedNewsItem]]) -> str:
    """
    將分類新聞格式化為 LLM 可閱讀的文字。
    每則新聞包含 URL，供 LLM 在報告中產生 Markdown 連結。
    """
    sections = []

    for category in NewsCategory:
        items = news_by_category.get(category, [])
        if not items:
            continue

        lines = [f"\n{'─' * 50}", f"  {category.value}", f"{'─' * 50}"]

        for i, item in enumerate(items, 1):
            ticker_str = (
                "  相關標的：" + "  ".join(f"[{t}]" for t in item.related_tickers)
                if item.related_tickers
                else "  相關標的：待評估"
            )
            # 預先組好 Markdown 超連結格式，模型直接複製即可，避免 Gemini 2.5 Flash
            # 等模型無法可靠地從分開的標題/URL 欄位自行組合成 [title](url)
            if item.url:
                title_link = f"[{item.title}]({item.url})"
                url_str    = f"  原文連結（請直接複製此格式）：{title_link}"
            else:
                title_link = item.title
                url_str    = ""
            lines.append(
                f"\n  {i}. [{item.source}]\n"
                f"     標題：{title_link}\n"
                f"{ticker_str}\n"
                f"{url_str}"
            )

        sections.append("\n".join(lines))

    return "\n".join(sections)


def get_news_url_map(news_by_category: dict[NewsCategory, list[EnrichedNewsItem]]) -> dict[str, str]:
    """
    返回 {新聞標題前40字 → URL} 的對照表，
    供 app.py 在渲染時插入點擊連結。
    """
    result = {}
    for items in news_by_category.values():
        for item in items:
            if item.url:
                key = item.title[:60].strip()
                result[key] = (item.url, item.source)
    return result


# ══════════════════════════════════════════════
#  主入口
# ══════════════════════════════════════════════

def fetch_categorized_news(
    api_key:            str = "",
    newsapi_key:        str = "",
    items_per_category: int = 5,
    min_per_category:   int = 3,   # ← 保底：每類別至少這麼多則
) -> dict[NewsCategory, list[EnrichedNewsItem]]:
    """
    主入口：抓取三大類新聞並自動標注相關標的。

    保底邏輯：每個類別至少保證 min_per_category 則。
    若主要 API 不足，自動補抓 RSS 湊滿數量。

    優先順序：
      1. Marketaux API（MARKETAUX_API_KEY）── 財經專用，最推薦
      2. NewsAPI.org  （NEWS_API_KEY）      ── 廣泛新聞，備援
      3. 免費 RSS                           ── 無 Key 或數量不足時補充
    """
    annotator = TickerAnnotator()
    result: dict[NewsCategory, list[EnrichedNewsItem]] = {}

    # ── 預抓 Finnhub 通用新聞（一次 API 呼叫，分配到三類別）──
    finnhub_key = _get_key("FINNHUB_KEY")
    finnhub_cache: dict[NewsCategory, list] = {}
    if finnhub_key:
        print("  [Finnhub] 預抓通用市場新聞（分配至三類別）...")
        finnhub_cache = _fetch_finnhub_news(finnhub_key, annotator, max_per_cat=8)
        total_fh = sum(len(v) for v in finnhub_cache.values())
        print(f"    → 共 {total_fh} 則")

    for category in NewsCategory:
        print(f"  正在抓取：{category.value}...")
        items: list[EnrichedNewsItem] = []

        # ── 第一層：Marketaux ──────────────────────────
        if api_key:
            fetched = _fetch_marketaux_for_category(
                api_key, category, annotator, max(items_per_category * 3, 15)
            )
            items.extend(fetched)
            print(f"    [Marketaux] {len(fetched)} 則")

        # ── 第二層：Finnhub 通用新聞補充 ───────────────
        fh_items = finnhub_cache.get(category, [])
        if fh_items:
            items.extend(fh_items)
            print(f"    [Finnhub] {len(fh_items)} 則")

        # ── 第三層：NewsAPI 補充（仍不足時啟動）────────
        if newsapi_key and len(items) < min_per_category:
            fetched = _fetch_newsapi_for_category(
                newsapi_key, category, annotator, items_per_category * 2
            )
            items.extend(fetched)
            print(f"    [NewsAPI 補充] {len(fetched)} 則")

        # ── 第四層：RSS 保底（任何情況下數量不足就補）──
        if len(items) < min_per_category:
            rss_items = _fetch_rss_for_category(category, annotator, max_per_feed=20)
            items.extend(rss_items)
            print(f"    [RSS 保底] 補充 {len(rss_items)} 則")

        # ── 去重、排序、截取 ──────────────────────────
        items = _deduplicate(items)
        items = _rank_items(items)

        # 確保至少 min_per_category 則（若真的抓不到就全留）
        final_count = max(min_per_category, items_per_category)
        items = items[:final_count]

        result[category] = items
        tickers_found = set(t for item in items for t in item.related_tickers)
        print(f"    → 最終 {len(items)} 則，標的：{tickers_found or '（無）'}")

    return result


# ══════════════════════════════════════════════
#  快速測試
# ══════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("  新聞情報引擎測試")
    print("=" * 60)

    marketaux_key = _get_key("MARKETAUX_API_KEY")
    newsapi_key   = _get_key("NEWS_API_KEY")

    news = fetch_categorized_news(
        api_key            = marketaux_key,
        newsapi_key        = newsapi_key,
        items_per_category = 4,
    )

    for category, items in news.items():
        print(f"\n{category.value}")
        print("─" * 50)
        for item in items:
            ticker_str = " ".join(f"[{t}]" for t in item.related_tickers) or "[無標的]"
            print(f"  • {item.title[:70]}...")
            print(f"    {ticker_str}")
