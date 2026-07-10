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


def make_accumulation_history(symbol: str = "ACCUM") -> pd.DataFrame:
    history = make_history(100, 0.40, days=260, symbol=symbol)
    # A measured pullback inside a long-running trend: below the fast TMA,
    # while the medium/slow trend and 50-day structure remain intact.
    for offset in range(8, 0, -1):
        index = history.index[-offset]
        previous_close = history.loc[index - 1, "close"]
        close = previous_close + (0.50 if offset == 1 else -1.0)
        history.loc[index, ["open", "high", "low", "close"]] = [
            close + 0.25,
            close + 0.50,
            close - 0.50,
            close,
        ]
    # The prior bar breaks structure; the final bullish repair creates the
    # first valid setup rather than continuing an already-active zone.
    prior_index = history.index[-2]
    history.loc[prior_index, ["open", "high", "low", "close"]] = [180.5, 181.0, 179.5, 180.0]
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

    def test_accumulation_setup_scores_as_entry_signal(self):
        benchmark = make_history(100, 0.10, symbol="QQQ")
        accumulation = make_accumulation_history()
        quiet = make_history(100, 0.05, days=260, symbol="QUIET")

        features = build_cross_section_features({"ACCUM": accumulation, "QUIET": quiet}, benchmark)
        rows = {row["symbol"]: row for _, row in features.iterrows()}
        accumulation_score = score_stock(rows["ACCUM"]).composite_score
        quiet_score = score_stock(rows["QUIET"]).composite_score

        self.assertTrue(rows["ACCUM"]["accumulation_entry"])
        self.assertTrue(rows["ACCUM"]["active_long_signal"])
        self.assertGreaterEqual(accumulation_score, 85)
        self.assertLess(quiet_score, 35)
        self.assertGreater(accumulation_score, quiet_score)

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
