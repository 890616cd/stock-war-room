"""
module_stock_chart.py
個股 K 線圖模組

包含：
  - 1年日K 蠟燭圖
  - MA 均線（5 / 10 / 20 / 50 / 120 / 200 / 250 日）
  - 成交量長條圖
  - MACD（12, 26, 9）
  - KDJ（9, 3, 3）
  - RSI（6 / 12 / 24）
"""

import numpy as np
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots


# ══════════════════════════════════════════════
#  均線顏色設定（對應截圖風格）
# ══════════════════════════════════════════════

MA_CONFIG = {
    5:   {"color": "#F5A623", "width": 1.2},   # 橙
    10:  {"color": "#7ED321", "width": 1.2},   # 綠
    20:  {"color": "#4A90E2", "width": 1.2},   # 藍
    50:  {"color": "#E91E63", "width": 1.2},   # 粉紅
    120: {"color": "#9B59B6", "width": 1.2},   # 紫
    200: {"color": "#1ABC9C", "width": 1.5},   # 青綠
    250: {"color": "#F1C40F", "width": 1.5},   # 黃
}


# ══════════════════════════════════════════════
#  技術指標計算（純硬邏輯，不用 LLM）
# ══════════════════════════════════════════════

def _calc_ma(close: pd.Series, window: int) -> pd.Series:
    return close.rolling(window=window, min_periods=1).mean()


def _calc_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain  = delta.clip(lower=0).rolling(period, min_periods=1).mean()
    loss  = (-delta.clip(upper=0)).rolling(period, min_periods=1).mean()
    rs    = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _calc_macd(close: pd.Series, fast=12, slow=26, signal=9):
    ema_fast   = close.ewm(span=fast,   adjust=False).mean()
    ema_slow   = close.ewm(span=slow,   adjust=False).mean()
    dif        = ema_fast - ema_slow
    dea        = dif.ewm(span=signal, adjust=False).mean()
    macd_hist  = (dif - dea) * 2
    return dif, dea, macd_hist


def _calc_kdj(high: pd.Series, low: pd.Series, close: pd.Series,
              n=9, m1=3, m2=3):
    lowest_low   = low.rolling(n,  min_periods=1).min()
    highest_high = high.rolling(n, min_periods=1).max()
    rsv = (close - lowest_low) / (highest_high - lowest_low + 1e-10) * 100
    K   = rsv.ewm(com=m1 - 1, adjust=False).mean()
    D   = K.ewm(com=m2 - 1,   adjust=False).mean()
    J   = 3 * K - 2 * D
    return K, D, J


# ══════════════════════════════════════════════
#  數據抓取
# ══════════════════════════════════════════════

def fetch_chart_data(symbol: str, period: str = "1y") -> pd.DataFrame:
    """
    抓取個股 1 年 OHLCV 日線數據。
    返回包含技術指標的 DataFrame。
    """
    t    = yf.Ticker(symbol)
    df   = t.history(period=period, interval="1d", auto_adjust=True)

    if df.empty:
        return df

    df.index = pd.to_datetime(df.index).tz_localize(None)
    df       = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.dropna(subset=["Close"], inplace=True)

    # ── 均線 ──────────────────────────────────
    for w in MA_CONFIG:
        df[f"MA{w}"] = _calc_ma(df["Close"], w)

    # ── RSI ───────────────────────────────────
    df["RSI6"]  = _calc_rsi(df["Close"], 6)
    df["RSI12"] = _calc_rsi(df["Close"], 12)
    df["RSI24"] = _calc_rsi(df["Close"], 24)

    # ── MACD ──────────────────────────────────
    df["DIF"], df["DEA"], df["MACD"] = _calc_macd(df["Close"])

    # ── KDJ ───────────────────────────────────
    df["K"], df["D"], df["J"] = _calc_kdj(df["High"], df["Low"], df["Close"])

    return df


# ══════════════════════════════════════════════
#  圖表建構
# ══════════════════════════════════════════════

def build_stock_chart(df: pd.DataFrame, symbol: str, name: str) -> go.Figure:
    """
    建構完整個股技術分析圖。
    layout：K線+均線 / 成交量 / MACD / KDJ / RSI
    """
    if df.empty:
        fig = go.Figure()
        fig.add_annotation(text="無法取得數據", showarrow=False, font_size=16)
        return fig

    # ── 用字串日期作為 categorical x，自動跳過非交易日（週末/假日）─────
    xs = df.index.strftime("%Y-%m-%d").tolist()

    # 每月第一個交易日作為 x 軸刻度
    tick_vals, tick_text = [], []
    prev_month = None
    for i, dt in enumerate(df.index):
        if dt.month != prev_month:
            tick_vals.append(xs[i])
            # 一月顯示年份，其餘只顯示月份縮寫
            tick_text.append(dt.strftime("%b\n%Y") if dt.month == 1 else dt.strftime("%b"))
            prev_month = dt.month

    # 漲跌顏色
    up_color   = "#26A69A"   # 綠（漲）
    dn_color   = "#EF5350"   # 紅（跌）
    vol_colors = [up_color if c >= o else dn_color
                  for c, o in zip(df["Close"], df["Open"])]

    # 不用 subplot_titles——那會產生浮動文字壓住數據；改用 y 軸 title_text
    fig = make_subplots(
        rows=5, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.025,
        row_heights=[0.46, 0.14, 0.14, 0.13, 0.13],
    )

    # ── Row 1：K 線 ───────────────────────────
    fig.add_trace(go.Candlestick(
        x          = xs,
        open       = df["Open"],
        high       = df["High"],
        low        = df["Low"],
        close      = df["Close"],
        name       = symbol,
        increasing = dict(line_color=up_color, fillcolor=up_color),
        decreasing = dict(line_color=dn_color, fillcolor=dn_color),
        showlegend = False,
        line_width = 1,
    ), row=1, col=1)

    # ── 均線 ──────────────────────────────────
    for w, cfg in MA_CONFIG.items():
        col_name = f"MA{w}"
        if col_name in df.columns:
            fig.add_trace(go.Scatter(
                x             = xs,
                y             = df[col_name],
                name          = f"MA{w}",
                line          = dict(color=cfg["color"], width=cfg["width"]),
                hovertemplate = f"MA{w}: %{{y:.2f}}<extra></extra>",
            ), row=1, col=1)

    # ── Row 2：成交量 ─────────────────────────
    fig.add_trace(go.Bar(
        x             = xs,
        y             = df["Volume"],
        name          = "Volume",
        marker_color  = vol_colors,
        showlegend    = False,
        hovertemplate = "成交量: %{y:,.0f}<extra></extra>",
    ), row=2, col=1)

    # ── Row 3：MACD ───────────────────────────
    macd_colors = [up_color if v >= 0 else dn_color for v in df["MACD"]]
    fig.add_trace(go.Bar(
        x             = xs,
        y             = df["MACD"],
        name          = "MACD Hist",
        marker_color  = macd_colors,
        showlegend    = False,
        hovertemplate = "MACD: %{y:.3f}<extra></extra>",
    ), row=3, col=1)
    fig.add_trace(go.Scatter(
        x=xs, y=df["DIF"],
        name="DIF", line=dict(color="#F5A623", width=1.2),
        hovertemplate="DIF: %{y:.3f}<extra></extra>",
    ), row=3, col=1)
    fig.add_trace(go.Scatter(
        x=xs, y=df["DEA"],
        name="DEA", line=dict(color="#4A90E2", width=1.2),
        hovertemplate="DEA: %{y:.3f}<extra></extra>",
    ), row=3, col=1)

    # ── Row 4：KDJ ────────────────────────────
    for lbl, series, clr in [("K", df["K"], "#F5A623"),
                               ("D", df["D"], "#4A90E2"),
                               ("J", df["J"], "#E91E63")]:
        fig.add_trace(go.Scatter(
            x=xs, y=series,
            name=lbl, line=dict(color=clr, width=1.2),
            hovertemplate=f"{lbl}: %{{y:.2f}}<extra></extra>",
        ), row=4, col=1)
    for ref in [80, 20]:
        fig.add_hline(y=ref, line_dash="dot", line_color="gray",
                      line_width=0.8, row=4, col=1)

    # ── Row 5：RSI ────────────────────────────
    for lbl, series, clr in [("RSI6",  df["RSI6"],  "#F5A623"),
                               ("RSI12", df["RSI12"], "#4A90E2"),
                               ("RSI24", df["RSI24"], "#E91E63")]:
        fig.add_trace(go.Scatter(
            x=xs, y=series,
            name=lbl, line=dict(color=clr, width=1.2),
            hovertemplate=f"{lbl}: %{{y:.2f}}<extra></extra>",
        ), row=5, col=1)
    for ref in [70, 30]:
        fig.add_hline(y=ref, line_dash="dot", line_color="gray",
                      line_width=0.8, row=5, col=1)

    # ── 版面設定 ──────────────────────────────
    latest  = df.iloc[-1]
    chg     = latest["Close"] - df.iloc[-2]["Close"] if len(df) > 1 else 0
    chg_pct = chg / df.iloc[-2]["Close"] * 100 if len(df) > 1 else 0
    t_color = up_color if chg >= 0 else dn_color
    sign    = "+" if chg >= 0 else ""

    fig.update_layout(
        title = dict(
            text  = (f"<b>{symbol}  {name}</b>  "
                     f"<span style='color:{t_color}'>"
                     f"{latest['Close']:.2f}  {sign}{chg:.2f} ({sign}{chg_pct:.2f}%)"
                     f"</span>"),
            font  = dict(size=16),
            x     = 0.01,
        ),
        paper_bgcolor = "#0E1117",
        plot_bgcolor  = "#0E1117",
        font          = dict(color="#CCCCCC", size=11),
        hovermode     = "x unified",
        legend        = dict(
            orientation = "h",
            y           = 1.02,
            x           = 0,
            bgcolor     = "rgba(0,0,0,0)",
            font        = dict(size=10),
        ),
        xaxis_rangeslider_visible = False,
        height  = 780,
        margin  = dict(l=50, r=20, t=60, b=20),
    )

    # ── 所有子圖 x 軸：categorical 跳過非交易日，只顯示月份刻度 ──
    xaxis_cfg = dict(
        type      = "category",        # 關鍵：不補空格
        tickvals  = tick_vals,
        ticktext  = tick_text,
        tickfont  = dict(size=9),
        gridcolor = "#1E2130",
        zeroline  = False,
        showgrid  = True,
    )
    yaxis_cfg = dict(
        gridcolor  = "#1E2130",
        zeroline   = False,
        showgrid   = True,
        tickfont   = dict(size=10),
        fixedrange = False,   # 允許拖拽 y 軸縮放
    )
    for i in range(1, 6):
        fig.update_xaxes(**xaxis_cfg, row=i, col=1)
        fig.update_yaxes(**yaxis_cfg, row=i, col=1)

    # 全部子圖 y 軸統一移至右側
    for i in range(1, 6):
        fig.update_yaxes(side="right", row=i, col=1)

    # 指標標籤改用 annotation 固定在各 panel 左上角，不佔 y 軸空間
    for row_num, lbl in {2: "VOL", 3: "MACD (12,26,9)", 4: "KDJ (9,3,3)", 5: "RSI (6,12,24)"}.items():
        axis_key = f"yaxis{row_num}"
        ydom = getattr(fig.layout, axis_key).domain
        fig.add_annotation(
            text      = lbl,
            xref      = "paper", yref = "paper",
            x         = 0.01,    y    = ydom[1],
            showarrow = False,
            font      = dict(size=9, color="#888888"),
            xanchor   = "left",  yanchor = "top",
        )

    return fig
