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


def make_bullish_sweep_history(symbol: str = "SWEEP") -> pd.DataFrame:
    history = make_history(100, 0.12, days=90, symbol=symbol)
    structure_low = history["low"].shift(1).rolling(20).min().iloc[-1]
    history.loc[history.index[-1], "open"] = structure_low + 0.10
    history.loc[history.index[-1], "low"] = structure_low - 0.50
    history.loc[history.index[-1], "close"] = structure_low + 1.25
    history.loc[history.index[-1], "high"] = structure_low + 1.80
    history.loc[history.index[-1], "volume"] = 2_000_000
    return history


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

    def test_bullish_sweep_with_filters_scores_as_entry_signal(self):
        benchmark = make_history(100, 0.10, symbol="QQQ")
        sweep = make_bullish_sweep_history()
        quiet = make_history(100, 0.05, symbol="QUIET")

        features = build_cross_section_features({"SWEEP": sweep, "QUIET": quiet}, benchmark)
        rows = {row["symbol"]: row for _, row in features.iterrows()}
        sweep_score = score_stock(rows["SWEEP"]).composite_score
        quiet_score = score_stock(rows["QUIET"]).composite_score

        self.assertTrue(rows["SWEEP"]["bullish_sweep"])
        self.assertTrue(rows["SWEEP"]["active_long_signal"])
        self.assertGreaterEqual(sweep_score, 85)
        self.assertLess(quiet_score, 35)
        self.assertGreater(sweep_score, quiet_score)

    def test_qqq_below_ma200_caps_buy_signal(self):
        self.assertEqual(get_advice_from_score(92, qqq_above_ma200=False, active_long_signal=True), "可以关注")
        self.assertEqual(suggest_position(92, qqq_above_ma200=False, active_long_signal=True), 0.0)

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
