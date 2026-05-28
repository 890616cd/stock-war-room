"""
module1_data_fetcher.py
模組一：數據抓取引擎
手動觸發，單次執行，嚴禁自動輪詢

子模組：
  module1_news_engine.py   ── 三類別新聞情報 + Regex 標的標注
  module1_watchlist.py     ── 自選股清單管理（板塊分類，CLI 新增/刪除）
"""

import os
import requests
import yfinance as yf
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional

from module1_news_engine import (
    fetch_categorized_news,
    format_news_for_llm,
    NewsCategory,
    EnrichedNewsItem,
)
from module1_watchlist import (
    fetch_watchlist_data,
    format_watchlist_for_llm,
    WatchlistSector,
    SECTOR_LABELS,
)


# ══════════════════════════════════════════════
#  大盤指數 & 總經指標（固定，不受 watchlist 影響）
# ══════════════════════════════════════════════

MAJOR_INDICES = {
    "S&P500":      "^GSPC",
    "NASDAQ":      "^IXIC",
    "DJIA":        "^DJI",
    "Russell2000": "^RUT",
}

MACRO_INDICATORS = {
    "VIX":   "^VIX",
    "US10Y": "^TNX",
    "DXY":   "DX-Y.NYB",
}

# 自選股設定已移至 watchlist.json（透過 module1_watchlist.py 管理）
# 新增：python module1_watchlist.py add NVDA NVIDIA semiconductor
# 刪除：python module1_watchlist.py remove NVDA
# 列表：python module1_watchlist.py list


# ══════════════════════════════════════════════
#  資料結構
# ══════════════════════════════════════════════

@dataclass
class StockData:
    symbol:      str
    name:        str
    price:       float
    prev_close:  float
    change_pct:  float
    volume:      int
    avg_volume:  int
    week52_high: float
    week52_low:  float
    # 估值欄位
    forward_pe:   Optional[float] = None   # 預估本益比
    trailing_pe:  Optional[float] = None   # 過去12月本益比
    pe_3y_avg:    Optional[float] = None   # 3年平均本益比（歷史均值）
    forward_ps:   Optional[float] = None   # 預估P/S（不獲利時使用）
    trailing_ps:  Optional[float] = None   # 過去12月P/S
    is_profitable: bool = True             # 是否獲利，決定顯示PE或PS

    # ── OHLC（最新交易日）────────────────────────────────
    open_price:  Optional[float] = None
    high_price:  Optional[float] = None
    low_price:   Optional[float] = None
    beta:        Optional[float] = None

    # ── 分析師目標價 ──────────────────────────────────────
    target_low:    Optional[float] = None
    target_mean:   Optional[float] = None
    target_median: Optional[float] = None
    target_high:   Optional[float] = None
    analyst_count: Optional[int]   = None

    # ── 預估 EPS（分析師共識均值）────────────────────────
    eps_est_2026: Optional[float] = None
    eps_est_2027: Optional[float] = None
    eps_est_2028: Optional[float] = None   # 通常無數據，顯示 N/A

    # ── Forward P/E（現價 / 預估EPS，is_profitable=True 時使用）─
    fpe_2026: Optional[float] = None
    fpe_2027: Optional[float] = None
    fpe_2028: Optional[float] = None   # 通常無數據，顯示 N/A

    # ── Forward P/S（市值 / 預估營收，不獲利時使用）────────
    fps_2026: Optional[float] = None
    fps_2027: Optional[float] = None
    fps_2028: Optional[float] = None   # 通常無數據，顯示 N/A

    # ── 年營收成長率預估（YoY %）─────────────────────────
    rev_growth_2026: Optional[float] = None
    rev_growth_2027: Optional[float] = None
    rev_growth_2028: Optional[float] = None

    # ── EPS 年成長率預估（YoY %）─────────────────────────
    eps_growth_2026: Optional[float] = None
    eps_growth_2027: Optional[float] = None
    eps_growth_2028: Optional[float] = None

    # ── Finnhub 分析師推薦（最新一期）──────────────────────
    rec_strong_buy:  Optional[int] = None
    rec_buy:         Optional[int] = None
    rec_hold:        Optional[int] = None
    rec_sell:        Optional[int] = None
    rec_strong_sell: Optional[int] = None

    @property
    def volume_ratio(self) -> float:
        return round(self.volume / self.avg_volume, 2) if self.avg_volume else 1.0

    @property
    def pct_from_52w_high(self) -> float:
        return round((self.price - self.week52_high) / self.week52_high * 100, 2)

    @property
    def support_proximity(self) -> float:
        return round((self.price - self.week52_low) / self.week52_low * 100, 2)

    @property
    def range_position(self) -> float:
        rng = self.week52_high - self.week52_low
        if rng == 0:
            return 50.0
        return round((self.price - self.week52_low) / rng * 100, 1)


@dataclass
class FullMarketData:
    """
    模組一的最終輸出物件。
    傳入模組二前先轉換為 MarketSnapshot（見 main.py）。
    """
    timestamp: str
    indices:          dict[str, StockData]
    vix:              float
    us10y:            float
    dxy:              float

    # 自選股（板塊分類，來自 watchlist.json）
    watchlist:        dict[WatchlistSector, list[StockData]] = field(default_factory=dict)

    # 財經新聞（三類別，已自動標注標的）
    news_by_category: dict[NewsCategory, list[EnrichedNewsItem]] = field(default_factory=dict)

    @property
    def sp500(self) -> float:
        return self.indices["S&P500"].price if "S&P500" in self.indices else 0.0

    @property
    def sp500_prev(self) -> float:
        return self.indices["S&P500"].prev_close if "S&P500" in self.indices else 0.0

    @property
    def nasdaq(self) -> float:
        return self.indices["NASDAQ"].price if "NASDAQ" in self.indices else 0.0

    @property
    def nasdaq_prev(self) -> float:
        return self.indices["NASDAQ"].prev_close if "NASDAQ" in self.indices else 0.0

    @property
    def djia(self) -> float:
        return self.indices["DJIA"].price if "DJIA" in self.indices else 0.0

    @property
    def djia_prev(self) -> float:
        return self.indices["DJIA"].prev_close if "DJIA" in self.indices else 0.0

    @property
    def total_watchlist_count(self) -> int:
        return sum(len(v) for v in self.watchlist.values())


# ══════════════════════════════════════════════
#  FMP 多年預估數據（P1 優先來源）
# ══════════════════════════════════════════════

def _fetch_finnhub_rec(symbol: str, finnhub_key: str) -> dict:
    """Finnhub /stock/recommendation → 最新一期分析師買/持/賣人數"""
    try:
        resp = requests.get(
            "https://finnhub.io/api/v1/stock/recommendation",
            params  = {"symbol": symbol, "token": finnhub_key},
            timeout = 8,
        )
        if resp.status_code != 200:
            return {}
        data = resp.json()
        if not isinstance(data, list) or not data:
            return {}
        latest = data[0]
        return {
            "rec_strong_buy":  int(latest.get("strongBuy",  0) or 0),
            "rec_buy":         int(latest.get("buy",        0) or 0),
            "rec_hold":        int(latest.get("hold",       0) or 0),
            "rec_sell":        int(latest.get("sell",       0) or 0),
            "rec_strong_sell": int(latest.get("strongSell", 0) or 0),
        }
    except Exception:
        return {}


def _fmp_stable_estimates(symbol: str, fmp_key: str, price: float,
                          mkt_cap: Optional[float]) -> dict:
    """
    FMP /stable/analyst-estimates (annual) → 多年預估 EPS / 營收 / PE / PS / 成長率
    返回 dict，key 格式：eps_est_YYYY / fpe_YYYY / fps_YYYY / rev_growth_YYYY / eps_growth_YYYY
    """
    result: dict = {}
    try:
        url = (
            "https://financialmodelingprep.com/stable/analyst-estimates"
            f"?symbol={symbol}&period=annual&limit=8&apikey={fmp_key}"
        )
        resp = requests.get(url, timeout=8)
        if resp.status_code != 200:
            return result

        rows = resp.json()
        if not isinstance(rows, list) or not rows:
            return result

        # 按日期升序排列，保留當年-1 以後（用於計算成長率）
        current_year = datetime.now().year
        rows_sorted = sorted(rows, key=lambda x: x.get("date", ""))
        year_data: dict[int, dict] = {}
        for r in rows_sorted:
            yr = int(r.get("date", "0000")[:4])
            if yr >= current_year - 1:
                year_data.setdefault(yr, r)  # 同一年只保留第一筆（最近財年）

        def _safe_float(v):
            try:
                return float(v) if v is not None else None
            except (TypeError, ValueError):
                return None

        # ── 逐年提取 EPS / PS ──────────────────────────
        for yr in [2026, 2027, 2028]:
            row = year_data.get(yr)
            if not row:
                continue

            # EPS（優先直接欄位，次選從 netIncome 推算）
            eps = _safe_float(row.get("epsAvg"))
            if eps is None and mkt_cap and price > 0 and mkt_cap > 0:
                ni = _safe_float(row.get("netIncomeAvg"))
                if ni:
                    shares = mkt_cap / price
                    eps = ni / shares if shares > 0 else None

            if eps and eps > 0 and price > 0:
                tentative_fpe = price / eps
                # 合理性檢查：P/E < 2x 代表 EPS 幣別錯誤（如 TSM ADR 用 NTD 計）
                if 2.0 <= tentative_fpe <= 400.0:
                    result[f"eps_est_{yr}"] = round(eps, 2)
                    result[f"fpe_{yr}"]     = round(tentative_fpe, 1)

            # P/S（合理性檢查：P/S < 0.8x 代表 revenue 可能為外幣計價，如 TSM 的 NTD）
            rev = _safe_float(row.get("revenueAvg"))
            if rev and rev > 0 and mkt_cap:
                tentative_fps = mkt_cap / rev
                if 0.8 <= tentative_fps <= 200.0:
                    result[f"fps_{yr}"] = round(tentative_fps, 2)

        # ── 成長率（需前一年數據）────────────────────────
        for yr in [2026, 2027, 2028]:
            row      = year_data.get(yr)
            prev_row = year_data.get(yr - 1)
            if not row or not prev_row:
                continue

            cur_rev  = _safe_float(row.get("revenueAvg"))
            prev_rev = _safe_float(prev_row.get("revenueAvg"))
            if cur_rev and prev_rev and prev_rev > 0:
                result[f"rev_growth_{yr}"] = round((cur_rev - prev_rev) / prev_rev * 100, 1)

            cur_eps  = _safe_float(row.get("epsAvg"))
            prev_eps = _safe_float(prev_row.get("epsAvg"))
            if cur_eps is None:
                cur_eps = result.get(f"eps_est_{yr}")
            if prev_eps is None:
                prev_eps = result.get(f"eps_est_{yr - 1}")
            if cur_eps and prev_eps and prev_eps != 0:
                result[f"eps_growth_{yr}"] = round((cur_eps - prev_eps) / abs(prev_eps) * 100, 1)

    except Exception:
        pass

    return result


# ══════════════════════════════════════════════
#  抓取函式
# ══════════════════════════════════════════════

def _fetch_ticker_data(symbol: str, name: str) -> Optional[StockData]:
    """單一標的資料抓取（OHLC / 估值 / 分析師目標價 / 多年預估成長率）"""
    try:
        t = yf.Ticker(symbol)

        # ── 優先抓 history（不限速；info 可能被 Yahoo 限速）────
        hist = t.history(period="5d")
        if hist.empty:
            hist = t.history(period="1mo")   # 備援：5d 空時改抓 1mo
        if hist.empty:
            return None

        closes     = hist["Close"].dropna()
        volumes    = hist["Volume"].dropna()
        price      = float(closes.iloc[-1])
        prev_close = float(closes.iloc[-2]) if len(closes) >= 2 else price
        volume     = int(volumes.iloc[-1]) if not volumes.empty else 0

        # ── OHLC（最新交易日）────────────────────────────
        open_price = round(float(hist["Open"].iloc[-1]),  2) if not hist.empty else None
        high_price = round(float(hist["High"].iloc[-1]),  2) if not hist.empty else None
        low_price  = round(float(hist["Low"].iloc[-1]),   2) if not hist.empty else None

        # ── t.info（Yahoo 可能限速；失敗時降級用 fast_info）──
        info = {}
        try:
            info = t.info or {}
        except Exception:
            try:
                fi = t.fast_info
                info = {
                    "fiftyTwoWeekHigh":   getattr(fi, "year_high",  price),
                    "fiftyTwoWeekLow":    getattr(fi, "year_low",   price),
                    "averageVolume10days": getattr(fi, "three_month_average_volume", volume),
                    "marketCap":           getattr(fi, "market_cap", None),
                }
            except Exception:
                pass

        beta = round(float(info["beta"]), 2) if info.get("beta") else None

        # ── 估值指標 ──────────────────────────────────────
        forward_pe  = info.get("forwardPE")
        trailing_pe = info.get("trailingPE")
        trailing_ps = info.get("priceToSalesTrailing12Months")
        is_profitable = bool(trailing_pe and trailing_pe > 0)
        mkt_cap       = info.get("marketCap")

        # 3年歷史平均PE
        pe_3y_avg = None
        try:
            inc = t.income_stmt
            if inc is not None and not inc.empty:
                ni_row = [r for r in inc.index if "Net Income" in str(r)]
                shares = info.get("sharesOutstanding") or info.get("impliedSharesOutstanding")
                if ni_row and shares:
                    ni_vals  = inc.loc[ni_row[0]].dropna().head(3)
                    eps_list = [float(v) / shares for v in ni_vals]
                    pe_list  = [price / e for e in eps_list if e > 0]
                    # 合理性過濾：< 3x 表示 Net Income 為外幣計（如 TSM 的 NTD）
                    valid_pe = [p for p in pe_list if 3.0 <= p <= 500.0]
                    if valid_pe:
                        pe_3y_avg = round(sum(valid_pe) / len(valid_pe), 1)
        except Exception:
            pass

        # Forward P/S（單一值，向後相容）
        forward_ps = None
        try:
            rev_est = info.get("revenueEstimatesAvg") or info.get("totalRevenue")
            if mkt_cap and rev_est and rev_est > 0:
                forward_ps = round(mkt_cap / rev_est, 2)
        except Exception:
            pass

        # ── 分析師目標價 ──────────────────────────────────
        def _sf(v):
            try: return round(float(v), 2)
            except: return None

        target_low    = _sf(info.get("targetLowPrice"))
        target_mean   = _sf(info.get("targetMeanPrice"))
        target_median = _sf(info.get("targetMedianPrice"))
        target_high   = _sf(info.get("targetHighPrice"))
        analyst_count = int(info["numberOfAnalystOpinions"]) \
                        if info.get("numberOfAnalystOpinions") else None

        # ── Forward PE/PS + 成長率預估 ──────────────────────
        eps_est_2026 = eps_est_2027 = eps_est_2028 = None
        fpe_2026 = fpe_2027 = fpe_2028 = None
        fps_2026 = fps_2027 = fps_2028 = None
        rev_growth_2026 = rev_growth_2027 = rev_growth_2028 = None
        eps_growth_2026 = eps_growth_2027 = eps_growth_2028 = None

        # ── Finnhub 分析師推薦（買/持/賣）────────────────────
        rec_strong_buy = rec_buy = rec_hold = rec_sell = rec_strong_sell = None
        finnhub_key_env = os.getenv("FINNHUB_KEY", "")
        if finnhub_key_env:
            rec = _fetch_finnhub_rec(symbol, finnhub_key_env)
            if rec:
                rec_strong_buy  = rec.get("rec_strong_buy")
                rec_buy         = rec.get("rec_buy")
                rec_hold        = rec.get("rec_hold")
                rec_sell        = rec.get("rec_sell")
                rec_strong_sell = rec.get("rec_strong_sell")

        # P1：FMP /stable/analyst-estimates（最完整，有 2028 數據）
        fmp_key = os.getenv("FMP_KEY", "")
        if fmp_key:
            fmp = _fmp_stable_estimates(symbol, fmp_key, price, mkt_cap)
            eps_est_2026    = fmp.get("eps_est_2026")
            eps_est_2027    = fmp.get("eps_est_2027")
            eps_est_2028    = fmp.get("eps_est_2028")
            fpe_2026        = fmp.get("fpe_2026")
            fpe_2027        = fmp.get("fpe_2027")
            fpe_2028        = fmp.get("fpe_2028")
            fps_2026        = fmp.get("fps_2026")
            fps_2027        = fmp.get("fps_2027")
            fps_2028        = fmp.get("fps_2028")
            rev_growth_2026 = fmp.get("rev_growth_2026")
            rev_growth_2027 = fmp.get("rev_growth_2027")
            rev_growth_2028 = fmp.get("rev_growth_2028")
            eps_growth_2026 = fmp.get("eps_growth_2026")
            eps_growth_2027 = fmp.get("eps_growth_2027")
            eps_growth_2028 = fmp.get("eps_growth_2028")

        # P2：yfinance earnings_estimate（填補 FMP 未覆蓋的空缺）
        # 注意：yfinance 1.x 正確屬性名為 singular（earnings_estimate，非 plural）
        try:
            ee = t.earnings_estimate
            if ee is not None and not ee.empty and "avg" in ee.columns:
                for period, yr in [("0y", 2026), ("+1y", 2027)]:
                    if period not in ee.index:
                        continue
                    try:
                        ef = float(ee.at[period, "avg"])
                        if ef > 0:
                            if yr == 2026 and eps_est_2026 is None:
                                eps_est_2026 = round(ef, 2)
                            elif yr == 2027 and eps_est_2027 is None:
                                eps_est_2027 = round(ef, 2)
                            pev = round(price / ef, 1) if price > 0 else None
                            if yr == 2026 and fpe_2026 is None: fpe_2026 = pev
                            elif yr == 2027 and fpe_2027 is None: fpe_2027 = pev
                    except Exception: pass
                    try:
                        gf = round(float(ee.at[period, "growth"]) * 100, 1)
                        if yr == 2026 and eps_growth_2026 is None: eps_growth_2026 = gf
                        elif yr == 2027 and eps_growth_2027 is None: eps_growth_2027 = gf
                    except Exception: pass
        except Exception: pass

        # P2：yfinance revenue_estimate（填補 FMP 未覆蓋的空缺）
        try:
            re = t.revenue_estimate
            if re is not None and not re.empty and "avg" in re.columns:
                for period, yr in [("0y", 2026), ("+1y", 2027)]:
                    if period not in re.index:
                        continue
                    try:
                        rf = float(re.at[period, "avg"])
                        if rf > 0 and mkt_cap:
                            psv = round(mkt_cap / rf, 2)
                            # 幣別合理性檢查（同 FMP 層）
                            if psv >= 0.8:
                                if yr == 2026 and fps_2026 is None: fps_2026 = psv
                                elif yr == 2027 and fps_2027 is None: fps_2027 = psv
                    except Exception: pass
                    try:
                        gf = round(float(re.at[period, "growth"]) * 100, 1)
                        if yr == 2026 and rev_growth_2026 is None: rev_growth_2026 = gf
                        elif yr == 2027 and rev_growth_2027 is None: rev_growth_2027 = gf
                    except Exception: pass
        except Exception: pass

        # P3：info 欄位（最後備援）
        if eps_est_2026 is None:
            try:
                fwd_eps = info.get("forwardEps")
                if fwd_eps and float(fwd_eps) > 0:
                    eps_est_2026 = round(float(fwd_eps), 2)
            except Exception: pass

        if fpe_2026 is None:
            try:
                fwd_eps = info.get("forwardEps")
                fwd_pe  = info.get("forwardPE")
                if fwd_eps and float(fwd_eps) > 0 and price > 0:
                    fpe_2026 = round(price / float(fwd_eps), 1)
                elif fwd_pe and float(fwd_pe) > 0:
                    fpe_2026 = round(float(fwd_pe), 1)
            except Exception: pass

        if fps_2026 is None:
            try:
                tot_rev = info.get("totalRevenue")
                if mkt_cap and tot_rev and float(tot_rev) > 0:
                    psv = round(mkt_cap / float(tot_rev), 2)
                    if psv >= 0.8:
                        fps_2026 = psv
            except Exception: pass

        if eps_growth_2026 is None:
            try:
                eg = info.get("earningsGrowth")
                if eg is not None:
                    eps_growth_2026 = round(float(eg) * 100, 1)
            except Exception: pass

        if rev_growth_2026 is None:
            try:
                rg = info.get("revenueGrowth")
                if rg is not None:
                    rev_growth_2026 = round(float(rg) * 100, 1)
            except Exception: pass

        return StockData(
            symbol        = symbol,
            name          = name,
            price         = round(price, 2),
            prev_close    = round(prev_close, 2),
            change_pct    = round((price - prev_close) / prev_close * 100, 2),
            volume        = volume,
            avg_volume    = int(info.get("averageVolume10days", volume) or volume),
            week52_high   = float(info.get("fiftyTwoWeekHigh", price) or price),
            week52_low    = float(info.get("fiftyTwoWeekLow",  price) or price),
            forward_pe    = round(float(forward_pe),  1) if forward_pe  and forward_pe  > 0 else None,
            trailing_pe   = round(float(trailing_pe), 1) if trailing_pe and trailing_pe > 0 else None,
            pe_3y_avg     = pe_3y_avg,
            forward_ps    = round(float(trailing_ps), 2) if trailing_ps and not is_profitable else forward_ps,
            trailing_ps   = round(float(trailing_ps), 2) if trailing_ps else None,
            is_profitable = is_profitable,
            # ── 新增欄位 ──
            eps_est_2026    = eps_est_2026,
            eps_est_2027    = eps_est_2027,
            eps_est_2028    = eps_est_2028,
            open_price      = open_price,
            high_price      = high_price,
            low_price       = low_price,
            beta            = beta,
            target_low      = target_low,
            target_mean     = target_mean,
            target_median   = target_median,
            target_high     = target_high,
            analyst_count   = analyst_count,
            fpe_2026        = fpe_2026,
            fpe_2027        = fpe_2027,
            fpe_2028        = fpe_2028,
            fps_2026        = fps_2026,
            fps_2027        = fps_2027,
            fps_2028        = fps_2028,
            rev_growth_2026 = rev_growth_2026,
            rev_growth_2027 = rev_growth_2027,
            rev_growth_2028 = rev_growth_2028,
            eps_growth_2026 = eps_growth_2026,
            eps_growth_2027 = eps_growth_2027,
            eps_growth_2028 = eps_growth_2028,
            rec_strong_buy  = rec_strong_buy,
            rec_buy         = rec_buy,
            rec_hold        = rec_hold,
            rec_sell        = rec_sell,
            rec_strong_sell = rec_strong_sell,
        )
    except Exception as e:
        print(f"    [警告] 無法抓取 {symbol}：{e}")
        return None


def fetch_market_indices() -> dict[str, StockData]:
    print("  正在抓取大盤指數...")
    result = {}
    for name, symbol in MAJOR_INDICES.items():
        data = _fetch_ticker_data(symbol, name)
        if data:
            result[name] = data
            print(f"    {name:<14} {data.price:>10,.2f}  ({data.change_pct:+.2f}%)")
    return result


def fetch_macro_indicators() -> tuple[float, float, float]:
    print("  正在抓取總經指標（VIX / US10Y / DXY）...")
    results = {}
    for name, symbol in MACRO_INDICATORS.items():
        val = 0.0
        for period in ["5d", "1mo"]:          # 5d 優先；若空再用 1mo
            try:
                t    = yf.Ticker(symbol)
                hist = t.history(period=period)
                if not hist.empty:
                    val = float(hist["Close"].dropna().iloc[-1])
                    break
            except Exception:
                pass
        results[name] = round(val, 3)
        print(f"    {name:<8}  {val:.3f}")
    return results.get("VIX", 0.0), results.get("US10Y", 0.0), results.get("DXY", 0.0)


def _print_watchlist_summary(watchlist: dict[WatchlistSector, list[StockData]]) -> None:
    """列印自選股板塊概覽"""
    total = sum(len(v) for v in watchlist.values())
    if total == 0:
        print("  （自選股清單為空，請執行：python module1_watchlist.py add <代號> <名稱> <板塊>）")
        return
    for sector, stocks in watchlist.items():
        label = SECTOR_LABELS[sector]
        for s in stocks:
            vol_flag = "  ★放量" if s.volume_ratio > 1.5 else ""
            print(
                f"    [{label}] {s.name:<12} ({s.symbol:<6})"
                f"  ${s.price:>8.2f}  ({s.change_pct:+.2f}%)"
                f"  量比 {s.volume_ratio:.1f}x{vol_flag}"
                f"  區間 {s.range_position:.0f}%"
            )


# ══════════════════════════════════════════════
#  模組一主入口
# ══════════════════════════════════════════════

def run_data_fetcher() -> FullMarketData:
    print("=" * 62)
    print("  模組一：數據抓取引擎  ──  開始執行")
    print(f"  觸發時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 62)

    indices         = fetch_market_indices()
    vix, us10y, dxy = fetch_macro_indicators()

    # 自選股（板塊分類，從 watchlist.json 讀取）
    print("\n  正在抓取自選股清單報價...")
    watchlist = fetch_watchlist_data()

    # 新聞（三類別有機探索 + Regex 標的標注）
    print("\n  正在抓取三大類別新聞...")
    marketaux_key = os.getenv("MARKETAUX_API_KEY", "")
    newsapi_key   = os.getenv("NEWS_API_KEY", "")

    if marketaux_key:
        print("  [新聞來源] Marketaux API（財經專用）")
    elif newsapi_key:
        print("  [新聞來源] NewsAPI.org（備援）")
    else:
        print("  [新聞來源] RSS 免費備援")

    news_by_category = fetch_categorized_news(
        api_key            = marketaux_key,
        newsapi_key        = newsapi_key,
        items_per_category = 3,   # 每類最多 3 則
    )

    data = FullMarketData(
        timestamp        = datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        indices          = indices,
        vix              = vix,
        us10y            = us10y,
        dxy              = dxy,
        watchlist        = watchlist,
        news_by_category = news_by_category,
    )

    total_news = sum(len(v) for v in news_by_category.values())
    print(
        f"\n  ✓ 模組一完成 | VIX={vix:.2f} | US10Y={us10y:.3f}% | DXY={dxy:.2f}"
        f" | 自選股 {data.total_watchlist_count} 檔"
        f" | 新聞 {total_news} 則"
    )
    return data


if __name__ == "__main__":
    data = run_data_fetcher()

    print("\n  ── 自選股概覽 ──")
    _print_watchlist_summary(data.watchlist)

    print("\n  ── 新聞情報預覽 ──")
    print(format_news_for_llm(data.news_by_category))
