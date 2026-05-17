"""
module2_discipline_warning.py
模組二：紀律警告協議 ── 絕對核心

架構準則：所有數值比較硬邏輯處理，LLM 僅負責語意彙整
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import yfinance as yf


# ════════════════════════════════════════════
#  常數區：硬寫死警戒線
# ════════════════════════════════════════════

VIX_YELLOW  = 20.0
VIX_RED     = 30.0
VIX_BLACK   = 40.0

US10Y_YELLOW = 4.30
US10Y_RED    = 4.70
US10Y_BLACK  = 5.20

SP500_CTA_WARN       = -0.020
SP500_CIRCUIT_BREAK  = -0.070
NASDAQ_CTA_WARN      = -0.025

FOMO_DROP_THRESHOLD  = -0.015
FOMO_VIX_THRESHOLD   = 20.0
DEAD_CAT_VIX         = 25.0


# ════════════════════════════════════════════
#  資料結構
# ════════════════════════════════════════════

class AlertLevel(Enum):
    GREEN  = "green"
    YELLOW = "yellow"
    RED    = "red"
    BLACK  = "black"


@dataclass
class MarketSnapshot:
    """從 API 獲取的精確市場數值（不允許估算）"""
    vix:               float
    us10y:             float
    sp500:             float
    sp500_prev_close:  float
    nasdaq:            float
    nasdaq_prev_close: float
    watchlist:         dict = field(default_factory=dict)


@dataclass
class RiskAssessment:
    """評估結果：傳入 Module 3 LLM 的精確上下文"""
    alert_level:         AlertLevel
    triggered_rules:     list[str]
    fomo_intercept:      bool
    fomo_signals:        list[str]
    worst_case_scenario: Optional[str]
    llm_context:         dict
    should_block_llm:    bool


# ════════════════════════════════════════════
#  模組二核心：紀律警告協議
# ════════════════════════════════════════════

class DisciplineWarningProtocol:
    """
    所有「數值比較」在此類別中以硬邏輯完成。
    LLM 絕對不會收到需要它自行判斷數值的指令。
    """

    def __init__(self, snapshot: MarketSnapshot):
        self.data   = snapshot
        self._rules: list[str] = []
        self._fomo:  list[str] = []

    def _check_vix(self) -> AlertLevel:
        v = self.data.vix
        if v >= VIX_BLACK:
            self._rules.append(
                f"[VIX BLACK] {v:.1f} >= {VIX_BLACK} — "
                f"Extreme panic, historical median S&P500 drawdown -18% in following month"
            )
            return AlertLevel.BLACK
        if v >= VIX_RED:
            self._rules.append(
                f"[VIX RED] {v:.1f} >= {VIX_RED} — "
                f"Severe market panic, implied volatility reflects systemic risk"
            )
            return AlertLevel.RED
        if v >= VIX_YELLOW:
            self._rules.append(
                f"[VIX YELLOW] {v:.1f} >= {VIX_YELLOW} — "
                f"Fear rising, reduce leverage, increase cash"
            )
            return AlertLevel.YELLOW
        return AlertLevel.GREEN

    def _check_us10y(self) -> AlertLevel:
        y = self.data.us10y
        if y >= US10Y_BLACK:
            self._rules.append(
                f"[US10Y BLACK] {y:.2f}% >= {US10Y_BLACK}% — "
                f"Extreme risk-free rate, growth stock valuations crushed"
            )
            return AlertLevel.BLACK
        if y >= US10Y_RED:
            self._rules.append(
                f"[US10Y RED] {y:.2f}% >= {US10Y_RED}% — "
                f"Broke strong resistance, P/E compression accelerating"
            )
            return AlertLevel.RED
        if y >= US10Y_YELLOW:
            self._rules.append(
                f"[US10Y YELLOW] {y:.2f}% >= {US10Y_YELLOW}% — "
                f"Watch Fed statements closely"
            )
            return AlertLevel.YELLOW
        return AlertLevel.GREEN

    def _check_cta_levels(self) -> AlertLevel:
        sp_chg = (self.data.sp500 - self.data.sp500_prev_close) / self.data.sp500_prev_close
        nq_chg = (self.data.nasdaq - self.data.nasdaq_prev_close) / self.data.nasdaq_prev_close

        if sp_chg <= SP500_CIRCUIT_BREAK:
            self._rules.append(
                f"[CIRCUIT BREAKER] S&P500 daily {sp_chg:.1%} — "
                f"Near -7% circuit breaker, CTA forced mass liquidation risk"
            )
            return AlertLevel.BLACK

        if sp_chg <= SP500_CTA_WARN:
            self._rules.append(
                f"[CTA RED] S&P500 daily {sp_chg:.1%} — "
                f"Triggered -2% CTA threshold, momentum strategies flipping short"
            )
            return AlertLevel.RED

        if nq_chg <= NASDAQ_CTA_WARN:
            self._rules.append(
                f"[NASDAQ CTA] NASDAQ daily {nq_chg:.1%} — "
                f"Tech sector triggered -2.5% CTA line, semiconductors at risk"
            )
            return AlertLevel.RED

        return AlertLevel.GREEN

    def _check_fomo(self) -> bool:
        detected = False
        sp_chg = (self.data.sp500 - self.data.sp500_prev_close) / self.data.sp500_prev_close

        if sp_chg < FOMO_DROP_THRESHOLD and self.data.vix > FOMO_VIX_THRESHOLD:
            self._fomo.append(
                f"FOMO ALERT — Catching falling knife risk: "
                f"market {sp_chg:.1%} + VIX {self.data.vix:.1f}. "
                f"Confirm structural support before any action."
            )
            detected = True

        if self.data.vix > DEAD_CAT_VIX and sp_chg > 0.01:
            self._fomo.append(
                f"DEAD CAT BOUNCE WARNING — VIX {self.data.vix:.1f} > {DEAD_CAT_VIX} "
                f"with {sp_chg:.1%} bounce. Assume bear market rally until proven otherwise."
            )
            detected = True

        return detected

    def _generate_worst_case(self) -> str:
        bullets = []
        sp_chg = (self.data.sp500 - self.data.sp500_prev_close) / self.data.sp500_prev_close

        if self.data.vix >= VIX_RED:
            proj_vix = self.data.vix * 1.30
            bullets.append(
                f"If VIX rises to {proj_vix:.0f} (current +30%), "
                f"historical data shows S&P500 median drawdown 15-25%, "
                f"semiconductors (NVDA/AMD) potential 30-45% decline."
            )

        if self.data.us10y >= US10Y_YELLOW:
            proj_10y = self.data.us10y + 0.50
            bullets.append(
                f"If US10Y rises to {proj_10y:.2f}%, "
                f"growth stock P/E compression 20-30%, "
                f"TSM ADR price target potentially revised down to $130-$150."
            )

        if sp_chg <= SP500_CTA_WARN:
            bullets.append(
                "After CTA flips short, historically requires 3-5 trading days to confirm bottom. "
                "Frequent bear traps during this period. "
                "Hold cash, wait for volume to drop below 60% of average before considering entry."
            )

        if not bullets:
            return "No extreme values detected. Monitor VIX and US10Y direction."

        header = "[WORST CASE SCENARIO — FORCED PROJECTION]\n"
        return header + "\n".join(f"  * {b}" for b in bullets)

    def run(self) -> RiskAssessment:
        levels = [
            self._check_vix(),
            self._check_us10y(),
            self._check_cta_levels(),
        ]

        priority = {
            AlertLevel.BLACK:  4,
            AlertLevel.RED:    3,
            AlertLevel.YELLOW: 2,
            AlertLevel.GREEN:  1,
        }
        overall = max(levels, key=lambda x: priority[x])

        fomo_detected = self._check_fomo()

        worst_case = None
        if overall in (AlertLevel.RED, AlertLevel.BLACK) or fomo_detected:
            worst_case = self._generate_worst_case()

        should_block = overall in (AlertLevel.RED, AlertLevel.BLACK)

        sp_chg = round(
            (self.data.sp500 - self.data.sp500_prev_close)
            / self.data.sp500_prev_close * 100, 2
        )

        llm_context = {
            "alert_level":         overall.value.upper(),
            "triggered_rules":     self._rules,
            "fomo_signals":        self._fomo if fomo_detected else [],
            "worst_case_scenario": worst_case,
            "market_snapshot": {
                "vix":       round(self.data.vix, 2),
                "us10y_pct": round(self.data.us10y, 3),
                "sp500":     round(self.data.sp500, 2),
                "sp500_chg": sp_chg,
                "nasdaq":    round(self.data.nasdaq, 2),
            },
        }

        return RiskAssessment(
            alert_level         = overall,
            triggered_rules     = self._rules,
            fomo_intercept      = fomo_detected,
            fomo_signals        = self._fomo,
            worst_case_scenario = worst_case,
            llm_context         = llm_context,
            should_block_llm    = should_block,
        )


# ════════════════════════════════════════════
#  緊急警告輸出格式化（不經過 LLM）
# ════════════════════════════════════════════

def format_emergency_output(assessment: RiskAssessment) -> str:
    level_label = {
        AlertLevel.BLACK:  "[ BLACK ALERT ]",
        AlertLevel.RED:    "[ RED ALERT ]",
        AlertLevel.YELLOW: "[ YELLOW WARNING ]",
        AlertLevel.GREEN:  "[ GREEN ]",
    }[assessment.alert_level]

    lines = [
        "=" * 60,
        f"  Discipline Warning Protocol — {level_label}",
        "=" * 60,
        "",
        "— Triggered Rules —",
    ]
    for r in assessment.triggered_rules:
        lines.append(f"  {r}")

    if assessment.fomo_intercept:
        lines += ["", "— FOMO Intercept Warning —"]
        for s in assessment.fomo_signals:
            lines.append(f"  {s}")

    if assessment.worst_case_scenario:
        lines += ["", assessment.worst_case_scenario]

    lines += [
        "",
        "— Core Discipline —",
        "  Cash is the best position.",
        "  No chasing. No catching falling knives.",
        "  Wait for VIX pullback + CTA direction confirmation.",
        "=" * 60,
    ]
    return "\n".join(lines)


# ════════════════════════════════════════════
#  手動觸發測試
# ════════════════════════════════════════════

if __name__ == "__main__":
    print(">>> Manual trigger: fetching market data...\n")

    try:
        import yfinance as yf
        tickers = yf.download(
            ["^VIX", "^TNX", "^GSPC", "^IXIC"],
            period="2d", interval="1d",
            progress=False, auto_adjust=True,
        )
        close = tickers["Close"]

        def latest(sym):
            return float(close[sym].dropna().iloc[-1])
        def prev(sym):
            col = close[sym].dropna()
            return float(col.iloc[-2]) if len(col) >= 2 else float(col.iloc[-1])

        snapshot = MarketSnapshot(
            vix               = latest("^VIX"),
            us10y             = latest("^TNX"),
            sp500             = latest("^GSPC"),
            sp500_prev_close  = prev("^GSPC"),
            nasdaq            = latest("^IXIC"),
            nasdaq_prev_close = prev("^IXIC"),
        )
    except Exception as e:
        print(f"API error ({e}), using test data...\n")
        snapshot = MarketSnapshot(
            vix=33.8, us10y=4.82,
            sp500=5080.0, sp500_prev_close=5230.0,
            nasdaq=16050.0, nasdaq_prev_close=16580.0,
        )

    protocol   = DisciplineWarningProtocol(snapshot)
    assessment = protocol.run()

    if assessment.should_block_llm:
        print(format_emergency_output(assessment))
    else:
        print(f"Alert Level: {assessment.alert_level.value.upper()}")
        for r in assessment.triggered_rules:
            print(f"  {r}")
        print("\n>>> Sending to Module 3 LLM...")
