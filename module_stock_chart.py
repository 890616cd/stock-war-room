"""
module_stock_chart.py
個股 K 線圖模組

包含：
  - 1年日K 蠟燭圖 + 均線 + 成交量（主圖，白色背景）
  - MACD、KDJ、RSI 獨立子圖（可摺疊）
"""

import numpy as np
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots


# ══════════════════════════════════════════════
#  顏色設定
# ══════════════════════════════════════════════

MA_CONFIG = {
    5:   {"color": "#E07B00", "width": 1.2},
    10:  {"color": "#2E8B00", "width": 1.2},
    20:  {"color": "#1565C0", "width": 1.2},
    50:  {"color": "#C62828", "width": 1.2},
    120: {"color": "#6A1B9A", "width": 1.2},
    200: {"color": "#00796B", "width": 1.5},
    250: {"color": "#F9A825", "width": 1.5},
}

UP_COLOR = "#26A69A"
DN_COLOR = "#EF5350"

# 白色主題通用設定
_WHITE_LAYOUT = dict(
    paper_bgcolor = "#FFFFFF",
    plot_bgcolor  = "#FFFFFF",
    font          = dict(color="#333333", size=11),
)
_AXIS_CFG = dict(
    gridcolor = "#E8E8E8",
    zeroline  = False,
    showgrid  = True,
    tickfont  = dict(size=10, color="#555555"),
    fixedrange = False,
)


# ══════════════════════════════════════════════
#  技術指標計算
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
    ema_fast  = close.ewm(span=fast,   adjust=False).mean()
    ema_slow  = close.ewm(span=slow,   adjust=False).mean()
    dif       = ema_fast - ema_slow
    dea       = dif.ewm(span=signal, adjust=False).mean()
    macd_hist = (dif - dea) * 2
    return dif, dea, macd_hist


def _calc_kdj(high: pd.Series, low: pd.Series, close: pd.Series, n=9, m1=3, m2=3):
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
    t  = yf.Ticker(symbol)
    df = t.history(period=period, interval="1d", auto_adjust=True)
    if df.empty:
        return df
    df.index = pd.to_datetime(df.index).tz_localize(None)
    df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.dropna(subset=["Close"], inplace=True)
    for w in MA_CONFIG:
        df[f"MA{w}"] = _calc_ma(df["Close"], w)
    df["RSI6"],  df["RSI12"], df["RSI24"] = (
        _calc_rsi(df["Close"], 6), _calc_rsi(df["Close"], 12), _calc_rsi(df["Close"], 24)
    )
    df["DIF"], df["DEA"], df["MACD"] = _calc_macd(df["Close"])
    df["K"],   df["D"],   df["J"]    = _calc_kdj(df["High"], df["Low"], df["Close"])
    return df


def _make_x_axis(df: pd.DataFrame):
    """產生 categorical x 軸資料（跳過週末），返回 xs, tick_vals, tick_text"""
    xs = df.index.strftime("%Y-%m-%d").tolist()
    tick_vals, tick_text, prev_month = [], [], None
    for i, dt in enumerate(df.index):
        if dt.month != prev_month:
            tick_vals.append(xs[i])
            tick_text.append(dt.strftime("%b\n%Y") if dt.month == 1 else dt.strftime("%b"))
            prev_month = dt.month
    return xs, tick_vals, tick_text


def _apply_x_axis(fig, tick_vals, tick_text, rows: int):
    xaxis_cfg = dict(
        type      = "category",
        tickvals  = tick_vals,
        ticktext  = tick_text,
        tickfont  = dict(size=9, color="#555555"),
        gridcolor = "#E8E8E8",
        zeroline  = False,
        showgrid  = True,
    )
    for i in range(1, rows + 1):
        fig.update_xaxes(**xaxis_cfg, row=i, col=1)
        fig.update_yaxes(**_AXIS_CFG, side="right", row=i, col=1)


# ══════════════════════════════════════════════
#  主圖：K 線 + 均線 + 成交量
# ══════════════════════════════════════════════

def build_stock_chart(df: pd.DataFrame, symbol: str, name: str) -> go.Figure:
    """K 線 + 均線 + 成交量（白色背景，2 列）"""
    if df.empty:
        fig = go.Figure()
        fig.add_annotation(text="無法取得數據", showarrow=False, font_size=16)
        return fig

    xs, tick_vals, tick_text = _make_x_axis(df)
    vol_colors = [UP_COLOR if c >= o else DN_COLOR
                  for c, o in zip(df["Close"], df["Open"])]

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.78, 0.22],
    )

    # K 線
    fig.add_trace(go.Candlestick(
        x=xs, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"],
        name=symbol,
        increasing=dict(line_color=UP_COLOR, fillcolor=UP_COLOR),
        decreasing=dict(line_color=DN_COLOR, fillcolor=DN_COLOR),
        showlegend=False, line_width=1,
    ), row=1, col=1)

    # 均線
    for w, cfg in MA_CONFIG.items():
        col_name = f"MA{w}"
        if col_name in df.columns:
            fig.add_trace(go.Scatter(
                x=xs, y=df[col_name], name=f"MA{w}",
                line=dict(color=cfg["color"], width=cfg["width"]),
                hovertemplate=f"MA{w}: %{{y:.2f}}<extra></extra>",
            ), row=1, col=1)

    # 成交量
    fig.add_trace(go.Bar(
        x=xs, y=df["Volume"], name="Volume",
        marker_color=vol_colors, showlegend=False,
        hovertemplate="成交量: %{y:,.0f}<extra></extra>",
    ), row=2, col=1)

    # 標題
    latest  = df.iloc[-1]
    chg     = latest["Close"] - df.iloc[-2]["Close"] if len(df) > 1 else 0
    chg_pct = chg / df.iloc[-2]["Close"] * 100 if len(df) > 1 else 0
    t_color = UP_COLOR if chg >= 0 else DN_COLOR
    sign    = "+" if chg >= 0 else ""

    fig.update_layout(
        **_WHITE_LAYOUT,
        title=dict(
            text=(f"<b>{symbol}  {name}</b>  "
                  f"<span style='color:{t_color}'>"
                  f"{latest['Close']:.2f}  {sign}{chg:.2f} ({sign}{chg_pct:.2f}%)"
                  f"</span>"),
            font=dict(size=16, color="#222222"), x=0.01,
        ),
        hovermode="x unified",
        legend=dict(
            orientation="h", y=1.02, x=0,
            bgcolor="rgba(255,255,255,0)", font=dict(size=10),
        ),
        xaxis_rangeslider_visible=False,
        height=560,
        margin=dict(l=10, r=60, t=60, b=20),
    )
    _apply_x_axis(fig, tick_vals, tick_text, rows=2)

    # VOL 標籤
    fig.add_annotation(
        text="VOL", xref="paper", yref="paper",
        x=0.01, y=fig.layout.yaxis2.domain[1] if fig.layout.yaxis2.domain else 0.22,
        showarrow=False, font=dict(size=9, color="#888888"),
        xanchor="left", yanchor="top",
    )
    return fig


# ══════════════════════════════════════════════
#  獨立技術指標子圖（可摺疊）
# ══════════════════════════════════════════════

def _indicator_base_layout(height=160) -> dict:
    return dict(
        **_WHITE_LAYOUT,
        hovermode="x unified",
        showlegend=True,
        legend=dict(orientation="h", y=1.15, x=0,
                    bgcolor="rgba(255,255,255,0)", font=dict(size=10)),
        height=height,
        margin=dict(l=10, r=60, t=10, b=20),
        xaxis_rangeslider_visible=False,
    )


def build_macd_chart(df: pd.DataFrame) -> go.Figure:
    """獨立 MACD 圖"""
    if df.empty:
        return go.Figure()
    xs, tick_vals, tick_text = _make_x_axis(df)
    macd_colors = [UP_COLOR if v >= 0 else DN_COLOR for v in df["MACD"]]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=xs, y=df["MACD"], name="MACD",
        marker_color=macd_colors, showlegend=False,
        hovertemplate="MACD: %{y:.3f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=xs, y=df["DIF"], name="DIF",
        line=dict(color="#E07B00", width=1.2),
        hovertemplate="DIF: %{y:.3f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=xs, y=df["DEA"], name="DEA",
        line=dict(color="#1565C0", width=1.2),
        hovertemplate="DEA: %{y:.3f}<extra></extra>",
    ))
    fig.update_layout(**_indicator_base_layout())
    fig.update_xaxes(type="category", tickvals=tick_vals, ticktext=tick_text,
                     tickfont=dict(size=9), gridcolor="#E8E8E8", zeroline=False)
    fig.update_yaxes(**_AXIS_CFG, side="right")
    return fig


def build_kdj_chart(df: pd.DataFrame) -> go.Figure:
    """獨立 KDJ 圖"""
    if df.empty:
        return go.Figure()
    xs, tick_vals, tick_text = _make_x_axis(df)

    fig = go.Figure()
    for lbl, series, clr in [("K", df["K"], "#E07B00"),
                               ("D", df["D"], "#1565C0"),
                               ("J", df["J"], "#C62828")]:
        fig.add_trace(go.Scatter(
            x=xs, y=series, name=lbl,
            line=dict(color=clr, width=1.2),
            hovertemplate=f"{lbl}: %{{y:.2f}}<extra></extra>",
        ))
    for ref in [80, 20]:
        fig.add_hline(y=ref, line_dash="dot", line_color="#AAAAAA", line_width=0.8)
    fig.update_layout(**_indicator_base_layout())
    fig.update_xaxes(type="category", tickvals=tick_vals, ticktext=tick_text,
                     tickfont=dict(size=9), gridcolor="#E8E8E8", zeroline=False)
    fig.update_yaxes(**_AXIS_CFG, side="right")
    return fig


def build_rsi_chart(df: pd.DataFrame) -> go.Figure:
    """獨立 RSI 圖"""
    if df.empty:
        return go.Figure()
    xs, tick_vals, tick_text = _make_x_axis(df)

    fig = go.Figure()
    for lbl, series, clr in [("RSI6",  df["RSI6"],  "#E07B00"),
                               ("RSI12", df["RSI12"], "#1565C0"),
                               ("RSI24", df["RSI24"], "#C62828")]:
        fig.add_trace(go.Scatter(
            x=xs, y=series, name=lbl,
            line=dict(color=clr, width=1.2),
            hovertemplate=f"{lbl}: %{{y:.2f}}<extra></extra>",
        ))
    for ref in [70, 30]:
        fig.add_hline(y=ref, line_dash="dot", line_color="#AAAAAA", line_width=0.8)
    fig.update_layout(**_indicator_base_layout())
    fig.update_xaxes(type="category", tickvals=tick_vals, ticktext=tick_text,
                     tickfont=dict(size=9), gridcolor="#E8E8E8", zeroline=False)
    fig.update_yaxes(**_AXIS_CFG, side="right")
    return fig
