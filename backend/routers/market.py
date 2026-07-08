from __future__ import annotations

from fastapi import APIRouter, Query

from topaz_us.data.market import get_index_data, get_index_history, get_market_adjusted_thresholds
from topaz_us.data.regime import classify_qqq_regime

router = APIRouter()


@router.get("/overview")
def market_overview():
    index_data = get_index_data("QQQ")
    history = get_index_history("QQQ", days=300)
    if not index_data or history is None or history.empty:
        return {"error": "Unable to fetch QQQ market data"}

    regime_info = classify_qqq_regime(history)
    thresholds = get_market_adjusted_thresholds(regime_info["regime"])
    return {
        "regime": regime_info["regime"],
        "regime_description": regime_info["description"],
        "index_price": index_data.get("price", 0),
        "index_change_pct": index_data.get("change_pct", 0),
        "index_high": index_data.get("high", 0),
        "index_low": index_data.get("low", 0),
        "index_open": index_data.get("open", 0),
        "index_prev_close": index_data.get("prev_close", 0),
        "index_name": "QQQ",
        "sentiment_advance_ratio": 0,
        "sentiment_up_count": 0,
        "sentiment_down_count": 0,
        "sentiment_limit_up": 0,
        "sentiment_limit_down": 0,
        "buy_threshold": thresholds.get("buy_threshold", 75),
        "sell_threshold": thresholds.get("sell_threshold", 50),
        "position_max": thresholds.get("position_max", 0.25),
        "qqq_above_ma200": regime_info.get("qqq_above_ma200", False),
        "qqq_ma20": regime_info.get("ma20"),
        "qqq_ma50": regime_info.get("ma50"),
        "qqq_ma200": regime_info.get("ma200"),
    }


@router.get("/history")
def market_history(days: int = Query(60, ge=10, le=500)):
    df = get_index_history("QQQ", days=days)
    if df is None or df.empty:
        return {"error": "Unable to fetch QQQ history", "data": []}
    data = df.tail(days)[["date", "open", "high", "low", "close", "volume"]].copy()
    data["date"] = data["date"].dt.strftime("%Y-%m-%d")
    return {
        "data": data.to_dict(orient="records"),
        "index_name": "QQQ",
        "code": "QQQ",
    }
