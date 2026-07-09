from __future__ import annotations

import argparse
import json
import os


RESULT_FILE = "data/raw/latest_analysis_results.json"


def normalize_stock_code(code: str) -> str:
    return code.strip().upper()


def load_analysis_results() -> dict | None:
    if not os.path.exists(RESULT_FILE):
        return None
    try:
        with open(RESULT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        print(f"Unable to read result file: {exc}")
        return None


def query_stock(stock_code: str) -> None:
    normalized_code = normalize_stock_code(stock_code)
    data = load_analysis_results()
    if data is None:
        print("No analysis result found. Run: uv run python -m topaz_us.analysis.daily")
        return

    results = data.get("results", [])
    stock = next((r for r in results if r.get("symbol") == normalized_code), None)
    if stock is None:
        print(f"{normalized_code} was not found in the latest NASDAQ 100 analysis.")
        return

    total = data.get("total_stocks", len(results))
    print("=" * 60)
    print("Topaz US Stock Query")
    print("=" * 60)
    print(f"Analysis date: {data.get('date', 'unknown')}")
    print(f"Strategy: {data.get('strategy_name', 'Topaz US Liquidity Entry Signals')}")
    print(f"Market regime: {data.get('market_regime', 'unknown')}")
    print()
    print(f"Name: {stock.get('name', normalized_code)}")
    print(f"Symbol: {normalized_code}")
    print(f"Rank: {stock.get('rank', 0)} / {total}")
    print(f"Price: ${stock.get('current_price', 0):.2f}")
    print(f"Daily change: {stock.get('change_pct', 0):+.2f}%")
    print(f"Composite score: {stock.get('composite_score', 0):.1f}")
    print(f"Signal: {stock.get('signal_status', 'No Signal')}")
    if stock.get("entry_price"):
        print(f"Entry: {stock.get('entry_price', 0):.2f}")
        print(f"Stop: {stock.get('stop_loss', 0):.2f}")
        print(f"TP1: {stock.get('tp1', 0):.2f}")
    print(f"Advice: {stock.get('advice', '')}")
    print(f"Position: {stock.get('position_pct', 0):.0%}")
    print("Reasons: " + " | ".join(stock.get("reasons", [])))
    print("=" * 60)


def list_top_stocks(n: int = 10) -> None:
    data = load_analysis_results()
    if data is None:
        print("No analysis result found. Run: uv run python -m topaz_us.analysis.daily")
        return
    print("=" * 60)
    print(f"Top {n} Topaz US candidates")
    print("=" * 60)
    print(f"Analysis date: {data.get('date', 'unknown')}")
    print()
    for item in data.get("results", [])[:n]:
        print(
            f"{item.get('rank', 0):3d}. {item.get('symbol', ''):<6} "
            f"{item.get('name', ''):<28} score={item.get('composite_score', 0):5.1f} "
            f"pos={item.get('position_pct', 0):.0%} {item.get('advice', '')}"
        )


def main():
    parser = argparse.ArgumentParser(description="Query latest Topaz US analysis results")
    parser.add_argument("code", nargs="?", help="Ticker, for example AAPL")
    parser.add_argument("--top", type=int, default=0, help="Show top N candidates")
    args = parser.parse_args()

    if args.top > 0:
        list_top_stocks(args.top)
    elif args.code:
        query_stock(args.code)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
