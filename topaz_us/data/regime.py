from __future__ import annotations

from typing import Dict

import pandas as pd


def classify_qqq_regime(history: pd.DataFrame | None) -> Dict:
    if history is None or len(history) < 60:
        return {
            "regime": "sideways",
            "description": "QQQ history is insufficient",
            "recommended_position": 0.25,
            "qqq_above_ma200": False,
        }

    close = history["close"]
    ma20 = close.rolling(20).mean().iloc[-1]
    ma50 = close.rolling(50).mean().iloc[-1]
    ma200 = close.rolling(200).mean().iloc[-1] if len(close) >= 200 else close.rolling(60).mean().iloc[-1]
    price = close.iloc[-1]
    ret_20d = price / close.iloc[-20] - 1 if len(close) >= 20 else 0.0
    above_ma200 = bool(price >= ma200)

    if price > ma20 > ma50 and price > ma200 and ret_20d > 0:
        regime = "bull"
        position = 0.80
        description = "QQQ is above key moving averages with positive 20-day momentum"
    elif not above_ma200:
        regime = "bear"
        position = 0.25
        description = "QQQ is below MA200; new long entries are capped"
    elif price < ma20 and ret_20d < 0:
        regime = "pullback"
        position = 0.45
        description = "QQQ is above MA200 but short-term momentum is weak"
    else:
        regime = "sideways"
        position = 0.55
        description = "QQQ trend is mixed"

    return {
        "regime": regime,
        "description": description,
        "recommended_position": position,
        "qqq_above_ma200": above_ma200,
        "ma20": float(ma20),
        "ma50": float(ma50),
        "ma200": float(ma200),
        "ret_20d": float(ret_20d),
    }


def judge_market_regime(history: pd.DataFrame | None = None) -> Dict:
    return classify_qqq_regime(history)


def get_market_adjusted_thresholds(market_env: str) -> Dict:
    thresholds = {
        "bull": {"buy_threshold": 75, "sell_threshold": 50, "position_max": 0.80},
        "sideways": {"buy_threshold": 75, "sell_threshold": 50, "position_max": 0.55},
        "pullback": {"buy_threshold": 75, "sell_threshold": 50, "position_max": 0.45},
        "bear": {"buy_threshold": 101, "sell_threshold": 50, "position_max": 0.25},
    }
    return thresholds.get(market_env, thresholds["sideways"])

