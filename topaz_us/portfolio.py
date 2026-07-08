from __future__ import annotations

import json
import os
from typing import Dict, List

from topaz_us.analysis.daily import DEFAULT_STOCK_LIST
from topaz_us.data.regime import classify_qqq_regime
from topaz_us.data.us_provider import get_history_data, load_us_stock_list
from topaz_us.strategy import build_cross_section_features, get_advice_from_score, score_stock


def load_portfolio(file_path: str) -> List[Dict]:
    if not os.path.exists(file_path):
        return []
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read().strip()
    if content.startswith("["):
        return json.loads(content)

    holdings = []
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 2:
            holdings.append({
                "code": parts[0].upper(),
                "name": "",
                "shares": int(parts[1]),
                "cost": float(parts[2]) if len(parts) > 2 else 0.0,
            })
    return holdings


def analyze_portfolio(portfolio: List[Dict]) -> Dict:
    universe = {symbol: {"name": name, "sector": sector} for symbol, name, sector in load_us_stock_list(DEFAULT_STOCK_LIST)}
    qqq_history = get_history_data("QQQ", days=300)
    regime_info = classify_qqq_regime(qqq_history)
    qqq_above_ma200 = regime_info.get("qqq_above_ma200", False)

    symbols = [item.get("code", item.get("symbol", "")).strip().upper() for item in portfolio]
    histories = {}
    failed = []
    for symbol in symbols:
        history = get_history_data(symbol, days=300)
        if history is None or len(history) < 60:
            failed.append({"code": symbol, "reason": "Unable to fetch enough yfinance history"})
        else:
            histories[symbol] = history

    features = build_cross_section_features(histories, qqq_history)
    feature_by_symbol = {row["symbol"]: row for _, row in features.iterrows()} if not features.empty else {}

    holdings = []
    sector_data = {}
    for item in portfolio:
        symbol = item.get("code", item.get("symbol", "")).strip().upper()
        shares = item.get("shares", 0)
        cost = item.get("cost", 0)
        if symbol not in feature_by_symbol:
            continue

        row = feature_by_symbol[symbol]
        breakdown = score_stock(row)
        advice = get_advice_from_score(breakdown.composite_score, qqq_above_ma200)
        current_price = float(row["current_price"])
        market_value = current_price * shares
        cost_value = cost * shares
        pnl = market_value - cost_value
        pnl_pct = (current_price / cost - 1) * 100 if cost > 0 else 0
        sector = universe.get(symbol, {}).get("sector", "Unknown")

        holding = {
            "symbol": symbol,
            "name": item.get("name") or universe.get(symbol, {}).get("name", symbol),
            "industry": sector,
            "sector": sector,
            "shares": shares,
            "cost": cost,
            "current_price": round(current_price, 2),
            "market_value": round(market_value, 2),
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "change_today": round(float(row["change_pct"]), 2),
            "composite_score": breakdown.composite_score,
            "advice": advice,
            "reasons": breakdown.reasons,
            "rsi": 0,
            "ret_5d": 0,
            "ret_20d": round(float(row.get("ret_20", 0)) * 100, 2),
        }
        holdings.append(holding)

        sector_data.setdefault(sector, {"value": 0.0, "pnl": 0.0, "stocks": []})
        sector_data[sector]["value"] += market_value
        sector_data[sector]["pnl"] += pnl
        sector_data[sector]["stocks"].append(holding["name"])

    total_value = sum(h["market_value"] for h in holdings)
    total_cost = sum(h["cost"] * h["shares"] for h in holdings)
    total_pnl = total_value - total_cost
    total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0

    sector_allocation = {}
    for sector, data in sector_data.items():
        sector_allocation[sector] = {
            "value": round(data["value"], 2),
            "pct": round(data["value"] / total_value * 100, 2) if total_value else 0,
            "pnl": round(data["pnl"], 2),
            "stocks": data["stocks"],
        }

    return {
        "holdings": holdings,
        "failed": failed,
        "total_value": round(total_value, 2),
        "total_cost": round(total_cost, 2),
        "total_pnl": round(total_pnl, 2),
        "total_pnl_pct": round(total_pnl_pct, 2),
        "industry_allocation": sector_allocation,
        "regime": regime_info["regime"],
        "buy_count": sum(1 for h in holdings if h["advice"] == "建议买入"),
        "sell_count": sum(1 for h in holdings if h["advice"] == "建议回避"),
        "loss_count": sum(1 for h in holdings if h["pnl_pct"] < 0),
    }
