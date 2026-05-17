"""
module1_watchlist.py
自選股清單管理器

設計原則：
  - 持久化存在 watchlist.json，不寫死在程式碼裡
  - 提供 CLI 介面，讓你用指令新增/刪除，完全不需要改原始碼
  - 按板塊分類（半導體 / 科技 / 金融 / 能源 / 國防 / 消費 / ETF / 其他）
  - 首次執行自動建立空白 watchlist.json

CLI 使用方式：
  python module1_watchlist.py add NVDA "NVIDIA" semiconductor
  python module1_watchlist.py add AAPL "Apple" tech
  python module1_watchlist.py add JPM "JPMorgan" finance
  python module1_watchlist.py remove NVDA
  python module1_watchlist.py list
  python module1_watchlist.py sectors       ← 顯示所有可用板塊
"""

import os
import sys
import json
import yfinance as yf
from enum import Enum
from dataclasses import dataclass
from typing import Optional
from pathlib import Path


# ══════════════════════════════════════════════
#  板塊定義
# ══════════════════════════════════════════════

class WatchlistSector(str, Enum):
    SEMICONDUCTOR = "semiconductor"   # 半導體
    TECH          = "tech"            # 大型科技
    FINANCE       = "finance"         # 金融 / 銀行
    ENERGY        = "energy"          # 能源 / 大宗商品
    DEFENSE       = "defense"         # 國防 / 航太
    CONSUMER      = "consumer"        # 消費 / 零售
    ETF           = "etf"             # ETF / 指數基金
    OTHER         = "other"           # 其他

SECTOR_LABELS = {
    WatchlistSector.SEMICONDUCTOR: "半導體",
    WatchlistSector.TECH:          "大型科技",
    WatchlistSector.FINANCE:       "金融 / 銀行",
    WatchlistSector.ENERGY:        "能源 / 大宗商品",
    WatchlistSector.DEFENSE:       "國防 / 航太",
    WatchlistSector.CONSUMER:      "消費 / 零售",
    WatchlistSector.ETF:           "ETF / 指數基金",
    WatchlistSector.OTHER:         "其他",
}

WATCHLIST_FILE = Path(__file__).parent / "watchlist.json"


# ══════════════════════════════════════════════
#  JSON 讀寫
# ══════════════════════════════════════════════

def _empty_watchlist() -> dict:
    """建立空白的清單結構（所有板塊皆為空）"""
    return {sector.value: {} for sector in WatchlistSector}


def load_watchlist() -> dict:
    """從 watchlist.json 讀取清單，不存在則自動建立空白版本"""
    if not WATCHLIST_FILE.exists():
        _save_raw(_empty_watchlist())
        print(f"  [初始化] 已建立空白 watchlist.json → {WATCHLIST_FILE}")
    with open(WATCHLIST_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    # 補齊缺少的板塊 key（向後相容）
    for sector in WatchlistSector:
        data.setdefault(sector.value, {})
    return data


def _save_raw(data: dict) -> None:
    with open(WATCHLIST_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ══════════════════════════════════════════════
#  新增 / 刪除 / 列表
# ══════════════════════════════════════════════

def add_stock(symbol: str, name: str, sector: str) -> None:
    """
    新增股票到指定板塊。
    例：add_stock("NVDA", "NVIDIA", "semiconductor")
    """
    symbol = symbol.upper().strip()
    sector = sector.lower().strip()

    try:
        target = WatchlistSector(sector)
    except ValueError:
        valid = ", ".join(s.value for s in WatchlistSector)
        print(f"  [錯誤] 不認識的板塊「{sector}」")
        print(f"  可用板塊：{valid}")
        return

    data = load_watchlist()

    # 檢查是否已存在（可能在其他板塊）
    for sec, stocks in data.items():
        if symbol in stocks:
            if sec == sector:
                print(f"  [提示] {symbol} 已在 {sec} 板塊中")
                return
            else:
                print(f"  [提示] {symbol} 已存在於「{sec}」板塊，將移動至「{sector}」")
                del data[sec][symbol]

    data[target.value][symbol] = name
    _save_raw(data)
    label = SECTOR_LABELS[target]
    print(f"  ✓ [{label}] {symbol} ({name}) 已加入關注清單")


def remove_stock(symbol: str) -> None:
    """從清單中移除股票（不需要指定板塊）"""
    symbol = symbol.upper().strip()
    data   = load_watchlist()
    found  = False

    for sector, stocks in data.items():
        if symbol in stocks:
            name = stocks.pop(symbol)
            _save_raw(data)
            label = SECTOR_LABELS[WatchlistSector(sector)]
            print(f"  ✓ [{label}] {symbol} ({name}) 已從關注清單移除")
            found = True
            break

    if not found:
        print(f"  [提示] {symbol} 不在關注清單中")


def list_watchlist() -> None:
    """列印目前關注清單（按板塊分組）"""
    data    = load_watchlist()
    total   = sum(len(v) for v in data.values())

    print(f"\n  自選股關注清單（共 {total} 檔）")
    print("  " + "─" * 40)

    if total == 0:
        print("  （尚無任何股票，請用以下指令新增）")
        print("  python module1_watchlist.py add <代號> <名稱> <板塊>")
        print("  範例：python module1_watchlist.py add NVDA NVIDIA semiconductor")
    else:
        for sector in WatchlistSector:
            stocks = data.get(sector.value, {})
            if not stocks:
                continue
            label = SECTOR_LABELS[sector]
            print(f"\n  [{label}]")
            for sym, name in stocks.items():
                print(f"    {sym:<8} {name}")

    print()


def list_sectors() -> None:
    """列印所有可用板塊"""
    print("\n  可用板塊（輸入小寫英文）：")
    print("  " + "─" * 40)
    for sector in WatchlistSector:
        print(f"    {sector.value:<16} {SECTOR_LABELS[sector]}")
    print()


# ══════════════════════════════════════════════
#  數據抓取（供 module1_data_fetcher 呼叫）
# ══════════════════════════════════════════════

def fetch_watchlist_data() -> dict[WatchlistSector, list]:
    """
    抓取清單中所有股票的報價，按板塊分組返回。
    返回值：{WatchlistSector → [StockData, ...]}
    空板塊不包含在結果中。
    """
    from module1_data_fetcher import _fetch_ticker_data   # 避免循環 import

    raw    = load_watchlist()
    result = {}

    for sector in WatchlistSector:
        stocks_raw = raw.get(sector.value, {})
        if not stocks_raw:
            continue

        label  = SECTOR_LABELS[sector]
        fetched = []
        print(f"  [{label}]")

        for symbol, name in stocks_raw.items():
            data = _fetch_ticker_data(symbol, name)
            if data:
                fetched.append(data)
                vol_flag = "  ★放量" if data.volume_ratio > 1.5 else ""
                pos_flag = f"  區間 {data.range_position:.0f}%"
                print(
                    f"    {name:<12} ({symbol:<6})  ${data.price:>8.2f}"
                    f"  ({data.change_pct:+.2f}%)"
                    f"  量比 {data.volume_ratio:.1f}x{vol_flag}{pos_flag}"
                )

        if fetched:
            result[sector] = fetched

    return result


def format_watchlist_for_llm(watchlist: dict[WatchlistSector, list]) -> str:
    """
    將關注清單格式化為 LLM 可讀文字（供模組三使用）。
    """
    if not watchlist:
        return "  （關注清單為空）"

    sections = []
    for sector, stocks in watchlist.items():
        label = SECTOR_LABELS[sector]
        lines = [f"\n  [{label}]"]
        for s in stocks:
            lines.append(
                f"    {s.name:<12} ({s.symbol:<6}) ${s.price:>8.2f}"
                f"  ({s.change_pct:+.2f}%)"
                f"  距年高 {s.pct_from_52w_high:.1f}%"
                f"  區間位置 {s.range_position:.0f}%"
            )
        sections.append("\n".join(lines))

    return "\n".join(sections)


# ══════════════════════════════════════════════
#  CLI 入口
# ══════════════════════════════════════════════

def _print_help():
    print("""
  自選股清單管理器 ── 指令說明
  ─────────────────────────────────────────────
  新增股票：
    python module1_watchlist.py add <代號> <名稱> <板塊>
    範例：
      python module1_watchlist.py add NVDA NVIDIA semiconductor
      python module1_watchlist.py add AAPL Apple tech
      python module1_watchlist.py add JPM JPMorgan finance
      python module1_watchlist.py add USO "US Oil ETF" etf

  移除股票：
    python module1_watchlist.py remove <代號>
    範例：python module1_watchlist.py remove NVDA

  列出清單：
    python module1_watchlist.py list

  查看板塊：
    python module1_watchlist.py sectors
  ─────────────────────────────────────────────
""")


if __name__ == "__main__":
    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help", "help"):
        _print_help()

    elif args[0] == "add":
        if len(args) < 4:
            print("  用法：python module1_watchlist.py add <代號> <名稱> <板塊>")
            print("  範例：python module1_watchlist.py add NVDA NVIDIA semiconductor")
        else:
            add_stock(symbol=args[1], name=args[2], sector=args[3])

    elif args[0] == "remove":
        if len(args) < 2:
            print("  用法：python module1_watchlist.py remove <代號>")
        else:
            remove_stock(symbol=args[1])

    elif args[0] == "list":
        list_watchlist()

    elif args[0] == "sectors":
        list_sectors()

    else:
        print(f"  [錯誤] 不認識的指令「{args[0]}」")
        _print_help()
