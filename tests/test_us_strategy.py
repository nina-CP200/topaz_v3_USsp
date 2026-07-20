from __future__ import annotations

import unittest

import pandas as pd

from topaz_us.data.us_provider import _get_yfinance_proxy, _normalize_history
from topaz_us.decision import MAX_GROSS_POSITION_PCT, MAX_SINGLE_POSITION_PCT, build_decision_snapshot
from topaz_us.data.regime import classify_qqq_regime
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
    def test_decision_blocks_entries_when_qqq_gate_is_closed(self):
        analysis = {
            "date": "2026-07-15 16:00",
            "qqq_above_ma200": False,
            "market_entry_allowed": False,
            "recommended_position": 0.5,
            "results": [{
                "symbol": "AAPL", "name": "Apple", "rank": 1,
                "active_long_signal": True, "position_pct": 0.08,
                "current_price": 200, "composite_score": 90,
            }],
        }
        snapshot = build_decision_snapshot(analysis, [], 100_000)
        self.assertFalse(snapshot["market"]["entry_allowed"])
        self.assertEqual(snapshot["candidates"], [])

    def test_decision_never_exceeds_individual_or_gross_limits(self):
        results = [
            {
                "symbol": f"T{i}", "name": f"Test {i}", "rank": i,
                "active_long_signal": True, "position_pct": 0.12,
                "current_price": 100, "composite_score": 95,
            }
            for i in range(1, 12)
        ]
        snapshot = build_decision_snapshot({
            "market_entry_allowed": True,
            "qqq_above_ma200": True,
            "recommended_position": 0.2,
            "results": results,
        }, [], 100_000)
        targets = [candidate["target_pct"] for candidate in snapshot["candidates"]]
        self.assertTrue(all(target <= MAX_SINGLE_POSITION_PCT for target in targets))
        self.assertLessEqual(sum(targets), 0.2)

    def test_decision_caps_gross_target_at_seventy_percent(self):
        results = [
            {
                "symbol": f"T{i}", "name": f"Test {i}", "rank": i,
                "active_long_signal": True, "position_pct": 0.12,
                "current_price": 100, "composite_score": 95,
            }
            for i in range(1, 11)
        ]
        snapshot = build_decision_snapshot({
            "market_entry_allowed": True,
            "qqq_above_ma200": True,
            "recommended_position": 0.95,
            "results": results,
        }, [], 100_000)
        targets = [candidate["target_pct"] for candidate in snapshot["candidates"]]
        self.assertLessEqual(sum(targets), MAX_GROSS_POSITION_PCT)
        self.assertTrue(all(target <= MAX_SINGLE_POSITION_PCT for target in targets))

    def test_decision_maps_five_holding_actions(self):
        base = {
            "market_entry_allowed": True,
            "qqq_above_ma200": True,
            "recommended_position": 0.4,
            "results": [
                {"symbol": "ADD", "rank": 1, "active_long_signal": True, "position_pct": 0.08, "current_price": 100},
                {"symbol": "EXIT", "rank": 2, "bearish_sweep": True, "current_price": 100},
                {"symbol": "REDUCE", "rank": 3, "current_price": 100},
                {"symbol": "HOLD", "rank": 4, "current_price": 100},
            ],
        }
        snapshot = build_decision_snapshot(base, [
            {"symbol": "ADD", "shares": 10, "cost": 90},
            {"symbol": "EXIT", "shares": 10, "cost": 90},
            {"symbol": "REDUCE", "shares": 130, "cost": 90},
            {"symbol": "HOLD", "shares": 20, "cost": 90},
        ], 100_000)
        actions = {holding["symbol"]: holding["action"] for holding in snapshot["holdings"]}
        self.assertEqual(actions["ADD"], "add")
        self.assertEqual(actions["EXIT"], "exit")
        self.assertEqual(actions["REDUCE"], "reduce")
        self.assertEqual(actions["HOLD"], "hold")
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

    def test_qqq_negative_momentum_activates_risk_off_override(self):
        history = make_history(100, 0.25, days=260, symbol="QQQ")
        for offset in range(20, 0, -1):
            index = history.index[-offset]
            history.loc[index, "close"] = history.loc[index - 1, "close"] - 1.5
            history.loc[index, "open"] = history.loc[index, "close"] + 0.2
            history.loc[index, "high"] = history.loc[index, "close"] + 0.5
            history.loc[index, "low"] = history.loc[index, "close"] - 0.5

        regime = classify_qqq_regime(history)
        self.assertEqual(regime["market_momentum_state"], "risk_off")
        self.assertFalse(regime["market_entry_allowed"])
        self.assertEqual(regime["recommended_position"], 0.25)

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
