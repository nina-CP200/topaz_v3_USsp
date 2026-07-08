from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict

from topaz_us.data.regime import classify_qqq_regime
from topaz_us.data.sentiment import get_market_sentiment
from topaz_us.data.us_provider import get_history_data, load_histories, load_us_stock_list
from topaz_us.strategy import (
    build_cross_section_features,
    get_advice_from_score,
    risk_level_from_score,
    score_stock,
    suggest_position,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STOCK_LIST = PROJECT_ROOT / "config" / "nasdaq100_stocks.json"
RESULT_FILE = PROJECT_ROOT / "data" / "raw" / "latest_analysis_results.json"


def analyze_stocks(stock_list_file: str | os.PathLike = DEFAULT_STOCK_LIST) -> Dict:
    stocks = load_us_stock_list(stock_list_file)
    symbols = [symbol for symbol, _, _ in stocks]
    meta = {symbol: {"name": name, "sector": sector} for symbol, name, sector in stocks}

    qqq_history = get_history_data("QQQ", days=300)
    regime_info = classify_qqq_regime(qqq_history)
    qqq_above_ma200 = regime_info.get("qqq_above_ma200", False)

    histories = load_histories(symbols, days=300)
    sentiment = get_market_sentiment(histories)
    features = build_cross_section_features(histories, qqq_history)

    results = []
    if not features.empty:
        for _, row in features.iterrows():
            symbol = row["symbol"]
            breakdown = score_stock(row)
            advice = get_advice_from_score(breakdown.composite_score, qqq_above_ma200)
            position_pct = suggest_position(breakdown.composite_score, qqq_above_ma200)
            results.append({
                "symbol": symbol,
                "name": meta.get(symbol, {}).get("name", symbol),
                "sector": meta.get(symbol, {}).get("sector", ""),
                "industry": meta.get(symbol, {}).get("sector", ""),
                "current_price": round(float(row["current_price"]), 2),
                "change_pct": round(float(row["change_pct"]), 2),
                "probability": round(breakdown.composite_score / 100, 4),
                "composite_score": breakdown.composite_score,
                "trend_score": breakdown.trend_score,
                "relative_strength_score": breakdown.relative_strength_score,
                "momentum_score": breakdown.momentum_score,
                "entry_score": breakdown.entry_score,
                "risk_penalty": breakdown.risk_penalty,
                "advice": advice,
                "reasons": breakdown.reasons,
                "position_pct": position_pct,
                "predicted_return": round((breakdown.composite_score - 50) / 10, 2),
                "risk_level": risk_level_from_score(breakdown.composite_score),
                "model_confidence": 1.0,
            })

    results = sorted(results, key=lambda x: x.get("composite_score", 0), reverse=True)
    for index, item in enumerate(results, 1):
        item["rank"] = index

    return {
        "all_results": results,
        "market_regime": regime_info["regime"],
        "market_description": regime_info["description"],
        "model_confidence": 1.0,
        "advance_ratio": sentiment.get("advance_ratio", 0.0),
        "recommended_position": regime_info.get("recommended_position", 0.25),
        "qqq_above_ma200": qqq_above_ma200,
        "qqq_ma20": regime_info.get("ma20"),
        "qqq_ma50": regime_info.get("ma50"),
        "qqq_ma200": regime_info.get("ma200"),
        "sentiment": sentiment,
    }


def save_analysis_result(analysis_data: Dict, output_file: str | os.PathLike = RESULT_FILE) -> Dict:
    results = analysis_data.get("all_results", [])
    output_data = {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "strategy_name": "Topaz US Trend Quality",
        "benchmark": "QQQ",
        "market_regime": analysis_data.get("market_regime", "sideways"),
        "market_description": analysis_data.get("market_description", ""),
        "model_confidence": analysis_data.get("model_confidence", 1.0),
        "advance_ratio": analysis_data.get("advance_ratio", 0.0),
        "recommended_position": analysis_data.get("recommended_position", 0.25),
        "qqq_above_ma200": analysis_data.get("qqq_above_ma200", False),
        "total_stocks": len(results),
        "results": results,
    }
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    return output_data


def print_report(analysis_data: Dict):
    print("\n" + "=" * 80)
    print("Topaz US Trend Quality")
    print("=" * 80)
    print(f"Report time: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"Benchmark: QQQ | Regime: {analysis_data.get('market_regime')}")
    print(f"Suggested gross exposure: {analysis_data.get('recommended_position', 0):.0%}")

    results = analysis_data.get("all_results", [])
    for stock in results[:10]:
        print(
            f"#{stock['rank']:02d} {stock['symbol']} {stock['name']} "
            f"score={stock['composite_score']:.1f} pos={stock['position_pct']:.0%} {stock['advice']}"
        )


def main():
    parser = argparse.ArgumentParser(description="Topaz US Trend Quality daily analysis")
    parser.add_argument("--stock-list", default=str(DEFAULT_STOCK_LIST))
    args = parser.parse_args()

    analysis_data = analyze_stocks(args.stock_list)
    save_analysis_result(analysis_data)
    print_report(analysis_data)


if __name__ == "__main__":
    main()
