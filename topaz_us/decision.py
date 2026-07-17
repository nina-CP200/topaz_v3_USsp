"""Pure decision-snapshot logic shared by the local API and tests."""

from __future__ import annotations

from typing import Any


MAX_SINGLE_POSITION_PCT = 0.08
MAX_CANDIDATES = 10


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: Any, lower: float = 0.0, upper: float = 1.0) -> float:
    return min(upper, max(lower, _number(value)))


def _symbol(item: dict[str, Any]) -> str:
    return str(item.get("symbol", item.get("code", ""))).strip().upper()


def _candidate_targets(results: list[dict[str, Any]], entry_allowed: bool, gross_cap: float) -> dict[str, float]:
    """Allocate existing signal sizes in rank order without forcing full exposure."""
    if not entry_allowed or gross_cap <= 0:
        return {}

    targets: dict[str, float] = {}
    remaining = gross_cap
    active = sorted(
        (item for item in results if bool(item.get("active_long_signal", False))),
        key=lambda item: (_number(item.get("rank"), 9999), -_number(item.get("composite_score"))),
    )
    for item in active[:MAX_CANDIDATES]:
        if remaining <= 0:
            break
        target = min(MAX_SINGLE_POSITION_PCT, _clamp(item.get("position_pct")), remaining)
        if target > 0:
            targets[_symbol(item)] = round(target, 6)
            remaining -= target
    return targets


def build_decision_snapshot(
    analysis: dict[str, Any] | None,
    holdings: list[dict[str, Any]],
    investable_capital_usd: float,
    analysis_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Turn the latest scan and manual holdings into human-executable actions.

    No broker semantics are represented here: values are targets for manual
    review only. Exit keeps the existing bearish liquidity-sweep signal.
    """
    capital = max(0.0, _number(investable_capital_usd))
    status = analysis_status or {"status": "idle", "progress": 0, "message": ""}
    if not analysis:
        return {
            "has_analysis": False,
            "analysis_date": None,
            "strategy_name": "Topaz US Moon Accumulation + Liquidity Exit",
            "capital": {"investable_capital_usd": round(capital, 2)},
            "market": {},
            "portfolio": {"current_value_usd": 0.0, "current_pct": 0.0, "target_value_usd": 0.0, "target_pct": 0.0},
            "candidates": [],
            "holdings": [],
            "exit_warnings": [],
            "data_status": {"status": status.get("status", "idle"), "message": status.get("message", ""), "stale": True},
        }

    results = [dict(item) for item in analysis.get("results", analysis.get("all_results", []))]
    result_by_symbol = {_symbol(item): item for item in results}
    entry_allowed = bool(analysis.get("market_entry_allowed", analysis.get("qqq_above_ma200", False)))
    gross_cap = _clamp(analysis.get("recommended_position", 0.0))
    target_by_symbol = _candidate_targets(results, entry_allowed, gross_cap)
    holding_by_symbol = {_symbol(item): item for item in holdings if _symbol(item)}

    current_value = 0.0
    decision_holdings: list[dict[str, Any]] = []
    for symbol, holding in holding_by_symbol.items():
        stock = result_by_symbol.get(symbol)
        shares = max(0.0, _number(holding.get("shares")))
        cost = max(0.0, _number(holding.get("cost")))
        if stock is None:
            decision_holdings.append({
                "symbol": symbol,
                "name": holding.get("name") or symbol,
                "shares": shares,
                "cost": cost,
                "action": "unavailable",
                "reasons": ["No current NASDAQ 100 analysis is available for this holding."],
            })
            continue

        price = max(0.0, _number(stock.get("current_price")))
        value = price * shares
        current_value += value
        target_pct = target_by_symbol.get(symbol, 0.0)
        current_pct = value / capital if capital else 0.0
        bearish_exit = bool(stock.get("bearish_sweep", False))
        if bearish_exit:
            action = "exit"
            target_pct = 0.0
        elif current_pct > MAX_SINGLE_POSITION_PCT and current_pct > target_pct:
            action = "reduce"
            target_pct = max(target_pct, MAX_SINGLE_POSITION_PCT)
        elif target_pct > 0 and value < capital * target_pct * 0.98:
            action = "add"
        else:
            action = "hold"

        target_value = capital * target_pct
        decision_holdings.append({
            "symbol": symbol,
            "name": holding.get("name") or stock.get("name") or symbol,
            "sector": stock.get("sector", stock.get("industry", "")),
            "shares": shares,
            "cost": round(cost, 2),
            "current_price": round(price, 2),
            "market_value_usd": round(value, 2),
            "current_pct": round(current_pct, 6),
            "target_pct": round(target_pct, 6),
            "target_value_usd": round(target_value, 2),
            "delta_value_usd": round(target_value - value, 2),
            "pnl_usd": round((price - cost) * shares, 2),
            "pnl_pct": round((price / cost - 1) * 100, 2) if cost else 0.0,
            "action": action,
            "entry_price": stock.get("entry_price"),
            "stop_loss": stock.get("stop_loss"),
            "composite_score": stock.get("composite_score"),
            "signal_status": stock.get("signal_status"),
            "reasons": stock.get("reasons", []),
        })

    candidates: list[dict[str, Any]] = []
    for symbol, target_pct in target_by_symbol.items():
        stock = result_by_symbol[symbol]
        holding = holding_by_symbol.get(symbol)
        price = max(0.0, _number(stock.get("current_price")))
        held_value = price * _number(holding.get("shares")) if holding else 0.0
        action = "enter" if not holding or held_value <= 0 else "add" if held_value < capital * target_pct * 0.98 else "hold"
        candidates.append({
            "symbol": symbol,
            "name": stock.get("name") or symbol,
            "sector": stock.get("sector", stock.get("industry", "")),
            "rank": stock.get("rank"),
            "current_price": round(price, 2),
            "change_pct": stock.get("change_pct"),
            "composite_score": stock.get("composite_score"),
            "target_pct": round(target_pct, 6),
            "target_value_usd": round(capital * target_pct, 2),
            "entry_price": stock.get("entry_price"),
            "stop_loss": stock.get("stop_loss"),
            "action": action,
            "reasons": stock.get("reasons", []),
        })

    target_total_pct = sum(target_by_symbol.values())
    exit_warnings = [
        {
            "symbol": _symbol(stock),
            "name": stock.get("name") or _symbol(stock),
            "is_holding": _symbol(stock) in holding_by_symbol,
            "current_price": stock.get("current_price"),
            "reasons": stock.get("reasons", []),
        }
        for stock in results
        if bool(stock.get("bearish_sweep", False))
    ]
    decision_holdings.sort(key=lambda item: (item.get("action") not in {"exit", "reduce"}, item.get("symbol", "")))
    candidates.sort(key=lambda item: (_number(item.get("rank"), 9999), item["symbol"]))

    return {
        "has_analysis": True,
        "analysis_date": analysis.get("date"),
        "strategy_name": analysis.get("strategy_name", "Topaz US Moon Accumulation + Liquidity Exit"),
        "capital": {"investable_capital_usd": round(capital, 2)},
        "market": {
            "regime": analysis.get("market_regime", "unknown"),
            "description": analysis.get("market_description", ""),
            "entry_allowed": entry_allowed,
            "qqq_above_ma200": bool(analysis.get("qqq_above_ma200", False)),
            "recommended_position_pct": round(gross_cap, 6),
            "advance_ratio": _number(analysis.get("advance_ratio")),
            "qqq_ma20": analysis.get("qqq_ma20"),
            "qqq_ma50": analysis.get("qqq_ma50"),
            "qqq_ma200": analysis.get("qqq_ma200"),
        },
        "portfolio": {
            "current_value_usd": round(current_value, 2),
            "current_pct": round(current_value / capital, 6) if capital else 0.0,
            "target_value_usd": round(capital * target_total_pct, 2),
            "target_pct": round(target_total_pct, 6),
        },
        "candidates": candidates,
        "holdings": decision_holdings,
        "exit_warnings": exit_warnings,
        "data_status": {
            "status": status.get("status", "idle"),
            "message": status.get("message", ""),
            "stale": status.get("status") == "error",
        },
    }
