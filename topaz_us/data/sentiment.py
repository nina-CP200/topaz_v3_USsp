from __future__ import annotations

from typing import Dict

import pandas as pd


def get_market_sentiment(histories: dict[str, pd.DataFrame] | None = None) -> Dict:
    if not histories:
        return {
            "advance_ratio": 0.0,
            "up_count": 0,
            "down_count": 0,
            "limit_up": 0,
            "limit_down": 0,
        }

    up_count = 0
    down_count = 0
    for history in histories.values():
        if len(history) < 2:
            continue
        change = history["close"].iloc[-1] / history["close"].iloc[-2] - 1
        if change >= 0:
            up_count += 1
        else:
            down_count += 1

    total = up_count + down_count
    return {
        "advance_ratio": up_count / total if total else 0.0,
        "up_count": up_count,
        "down_count": down_count,
        "limit_up": 0,
        "limit_down": 0,
    }
