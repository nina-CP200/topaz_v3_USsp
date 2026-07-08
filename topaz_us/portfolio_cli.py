from __future__ import annotations

import argparse

from topaz_us.portfolio import analyze_portfolio, load_portfolio


def print_portfolio_report(result: dict):
    print("=" * 72)
    print("Topaz US Portfolio")
    print("=" * 72)
    print(f"Regime: {result.get('regime', 'unknown')}")
    print(f"Total value: ${result.get('total_value', 0):,.2f}")
    print(f"P/L: ${result.get('total_pnl', 0):,.2f} ({result.get('total_pnl_pct', 0):+.2f}%)")
    print(f"Buy signals: {result.get('buy_count', 0)} | Avoid signals: {result.get('sell_count', 0)} | Losing positions: {result.get('loss_count', 0)}")
    print()

    for item in result.get("holdings", []):
        print(
            f"{item['symbol']:<6} {item.get('name', ''):<28} "
            f"value=${item['market_value']:>10,.2f} pnl={item['pnl_pct']:>7.2f}% "
            f"score={item['composite_score']:>5.1f} {item['advice']}"
        )
        if item.get("reasons"):
            print(f"       {' | '.join(item['reasons'][:4])}")

    failed = result.get("failed", [])
    if failed:
        print()
        print("Failed:")
        for item in failed:
            print(f"  {item.get('code')}: {item.get('reason')}")


def main():
    parser = argparse.ArgumentParser(description="Analyze a Topaz US portfolio file")
    parser.add_argument("file", nargs="?", default="data/raw/portfolio.json")
    args = parser.parse_args()

    portfolio = load_portfolio(args.file)
    if not portfolio:
        print(f"No holdings found in {args.file}")
        return
    print_portfolio_report(analyze_portfolio(portfolio))


if __name__ == "__main__":
    main()
