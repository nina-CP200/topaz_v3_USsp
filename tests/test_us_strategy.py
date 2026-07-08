from __future__ import annotations

import unittest

import pandas as pd

from topaz_us.data.us_provider import _get_yfinance_proxy, _normalize_history
from topaz_us.strategy import build_cross_section_features, get_advice_from_score, score_stock, suggest_position


def make_history(start: float, step: float, days: int = 260, symbol: str = "TEST") -> pd.DataFrame:
    dates = pd.date_range("2025-01-01", periods=days, freq="B")
    close = pd.Series([start + i * step for i in range(days)])
    return pd.DataFrame({
        "date": dates,
        "open": close * 0.995,
        "high": close * 1.01,
        "low": close * 0.99,
        "close": close,
        "volume": 1_000_000,
        "symbol": symbol,
    })


class USStrategyTests(unittest.TestCase):
    def test_yfinance_shape_is_normalized(self):
        raw = pd.DataFrame({
            "Date": pd.date_range("2025-01-01", periods=3),
            "Open": [10, 11, 12],
            "High": [11, 12, 13],
            "Low": [9, 10, 11],
            "Close": [10.5, 11.5, 12.5],
            "Volume": [100, 110, 120],
        }).set_index("Date")
        normalized = _normalize_history(raw, "aapl")
        self.assertEqual(list(normalized.columns), ["date", "open", "high", "low", "close", "volume", "symbol"])
        self.assertEqual(normalized.iloc[-1]["symbol"], "AAPL")
        self.assertEqual(float(normalized.iloc[-1]["close"]), 12.5)

    def test_strong_trend_scores_above_weak_trend(self):
        benchmark = make_history(100, 0.10, symbol="QQQ")
        strong = make_history(80, 0.45, symbol="STRONG")
        weak = make_history(180, -0.20, symbol="WEAK")

        features = build_cross_section_features({"STRONG": strong, "WEAK": weak}, benchmark)
        rows = {row["symbol"]: row for _, row in features.iterrows()}
        strong_score = score_stock(rows["STRONG"]).composite_score
        weak_score = score_stock(rows["WEAK"]).composite_score

        self.assertGreaterEqual(strong_score, 75)
        self.assertLess(weak_score, 50)
        self.assertGreater(strong_score, weak_score)

    def test_qqq_below_ma200_caps_buy_signal(self):
        self.assertEqual(get_advice_from_score(92, qqq_above_ma200=False), "可以关注")
        self.assertEqual(suggest_position(92, qqq_above_ma200=False), 0.0)

    def test_yfinance_proxy_can_be_read_from_environment(self):
        import os

        old = os.environ.get("TOPAZ_YF_PROXY")
        os.environ["TOPAZ_YF_PROXY"] = "http://127.0.0.1:7897"
        try:
            self.assertEqual(_get_yfinance_proxy(), "http://127.0.0.1:7897")
        finally:
            if old is None:
                os.environ.pop("TOPAZ_YF_PROXY", None)
            else:
                os.environ["TOPAZ_YF_PROXY"] = old


if __name__ == "__main__":
    unittest.main()
