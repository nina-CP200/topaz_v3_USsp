import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from topaz_us.indicators import build_indicator_frame, latest_indicators, interpret_indicators, summarize_signals, build_moon_assessment
from tests.test_us_strategy import make_history, make_accumulation_history


class IndicatorTests(unittest.TestCase):
    def test_moon_explains_real_accumulation_and_market_gate(self):
        history = make_accumulation_history()
        active = build_moon_assessment(history, True)
        self.assertEqual(active['label'], '吸筹触发')
        self.assertEqual(active['direction'], 'bullish')
        self.assertTrue(active['triggered'])
        blocked = build_moon_assessment(history, False)
        self.assertEqual(blocked['label'], '等待市场')
        self.assertEqual(blocked['direction'], 'neutral')
        self.assertEqual(blocked['setup'], active['setup'])

    def test_moon_prioritizes_exit_and_distinguishes_ongoing_setup(self):
        history = make_history(100, 0.5)
        frame = pd.DataFrame([{'date': history.date.iloc[-1], 'accumulation_entry': True, 'expansion_add_entry': False, 'moon_buy_signal': False, 'bearish_sweep': False, 'below_structure': False, 'bull_order': True}])
        with patch('topaz_us.strategy.build_signal_frame', return_value=frame):
            ongoing = build_moon_assessment(history, True)
            self.assertEqual(ongoing['label'], '吸筹延续')
            self.assertFalse(ongoing['triggered'])
            frame.loc[0, 'bearish_sweep'] = True
            risk = build_moon_assessment(history, True)
            self.assertEqual(risk['label'], '退出预警')
            self.assertEqual(risk['direction'], 'bearish')

    def test_moon_waits_for_history_and_does_not_invent_entry(self):
        self.assertEqual(build_moon_assessment(make_history(100, 0.5, days=100), True)['direction'], 'unavailable')
        self.assertEqual(build_moon_assessment(make_history(100, 0.5), True)['label'], '等待形态')

    def test_values_follow_daily_formulas(self):
        history = make_history(100, 0.5, days=80)
        result = latest_indicators(history)
        high = history.high.iloc[-14:].max()
        low = history.low.iloc[-14:].min()
        self.assertAlmostEqual(result['williams_r'], -100 * (high - history.close.iloc[-1]) / (high - low), places=3)
        typical = (history.high + history.low + history.close).iloc[-20:] / 3
        expected = (typical.iloc[-1] - typical.mean()) / (0.015 * (typical - typical.mean()).abs().mean())
        self.assertAlmostEqual(result['cci'], expected, places=3)
        self.assertAlmostEqual(result['macd_hist'], result['macd'] - result['macd_signal'], places=3)

    def test_cross_is_only_marked_on_crossing_bar(self):
        history = make_history(100, -0.4, days=120)
        history.loc[60:, 'close'] = np.linspace(76, 140, 60)
        frame = build_indicator_frame(history)
        crosses = frame.index[frame.ma_cross == 'golden_cross'].tolist()
        self.assertEqual(len(crosses), 1)
        self.assertEqual(frame.loc[crosses[0] + 1, 'ma_cross'], 'above')
        self.assertEqual(frame.loc[10, 'ma_cross'], 'unavailable')

    def test_zero_ranges_are_null_and_serializable(self):
        history = make_history(100, 0, days=80)
        history[['high', 'low']] = 100.0
        result = latest_indicators(history)
        self.assertIsNone(result['williams_r'])
        self.assertIsNone(result['cci'])
        self.assertEqual(result['ma_cross'], 'equal')

    def test_indicators_do_not_look_ahead(self):
        history = make_history(100, 0.5, days=90)
        prefix = build_indicator_frame(history.iloc[:70])
        full = build_indicator_frame(history)
        pd.testing.assert_frame_equal(prefix, full.iloc[:70])

    def test_snapshot_backfill_stops_at_original_date(self):
        from backend.routers.analysis import daily_analysis
        history = make_history(100, 0.5, days=90)
        snapshot = {'date': str(history.date.iloc[69].date()), 'results': [{'symbol': 'TEST'}]}
        with patch('backend.routers.analysis.load_analysis_results', return_value=snapshot), patch('backend.routers.analysis.pd.read_parquet', return_value=history), patch('pathlib.Path.exists', return_value=True):
            result = daily_analysis()['results'][0]
        self.assertEqual(result['williams_r'], latest_indicators(history.iloc[:70])['williams_r'])
        self.assertEqual(result['cci'], latest_indicators(history.iloc[:70])['cci'])

    def test_horizons_have_distinct_parameters_and_direction(self):
        for step, direction in ((0.5, 'bullish'), (-0.2, 'bearish')):
            with self.subTest(step=step):
                result = latest_indicators(make_history(100, step))
                analysis = result['technical_analysis']
                self.assertEqual(set(analysis['horizons']), {'short', 'medium', 'long'})
                self.assertEqual(analysis['horizons']['short']['parameters']['ma'], (5, 20))
                self.assertEqual(analysis['horizons']['long']['parameters']['ma'], (50, 200))
                for horizon in analysis['horizons'].values():
                    self.assertEqual(horizon['summary']['direction'], direction)
                    self.assertEqual(len(horizon['signals']), 4)
                    self.assertTrue(all(signal['reason'] for signal in horizon['signals'].values()))
                medium = analysis['horizons']['medium']['values']
                self.assertEqual(result['macd'], medium['macd'])
                self.assertEqual(result['cci'], medium['cci'])

    def test_long_horizon_requires_full_ma_history(self):
        result = latest_indicators(make_history(100, 0.5, days=200))
        self.assertEqual(result['technical_analysis']['horizons']['long']['summary']['direction'], 'unavailable')
        full = latest_indicators(make_history(100, 0.5, days=201))
        self.assertNotEqual(full['technical_analysis']['horizons']['long']['summary']['direction'], 'unavailable')

    def test_oversold_is_not_automatically_bullish(self):
        latest = pd.Series({'williams_r': -90, 'macd_hist': 1, 'macd': 2, 'ma_cross': 'above', 'cci': 0})
        self.assertEqual(interpret_indicators(latest, pd.Series({'williams_r': -95}))['williams']['direction'], 'bearish')
        latest['williams_r'] = -70
        self.assertEqual(interpret_indicators(latest, pd.Series({'williams_r': -90}))['williams']['direction'], 'bullish')
        latest['williams_r'] = -10
        self.assertEqual(interpret_indicators(latest, pd.Series({'williams_r': -15}))['williams']['direction'], 'bullish')
        latest['williams_r'] = -30
        self.assertEqual(interpret_indicators(latest, pd.Series({'williams_r': -10}))['williams']['direction'], 'bearish')

    def test_conflict_is_neutral_and_missing_data_is_not_neutral(self):
        signals = {key: {'direction': direction, 'reason': 'test'} for key, direction in zip(('williams', 'macd', 'ma', 'cci'), ('bullish', 'bullish', 'bearish', 'bearish'))}
        self.assertEqual(summarize_signals(signals)['direction'], 'neutral')
        signals['cci']['direction'] = 'bullish'
        self.assertEqual(summarize_signals(signals)['direction'], 'bullish')
        signals['ma']['direction'] = 'unavailable'
        self.assertEqual(summarize_signals(signals)['direction'], 'unavailable')

    def test_horizon_analysis_is_causal_and_json_safe(self):
        import json
        history = make_history(100, 0.5)
        truncated = latest_indicators(history.iloc[:220])
        modified = history.copy()
        modified.loc[220:, 'close'] = 99999
        self.assertEqual(truncated, latest_indicators(modified.iloc[:220]))
        json.dumps(truncated, allow_nan=False)
        flat = make_history(100, 0, days=260)
        flat[['high', 'low']] = 100.0
        json.dumps(latest_indicators(flat), allow_nan=False)

    def test_existing_numeric_snapshot_gains_horizon_analysis(self):
        from backend.routers.analysis import daily_analysis
        history = make_history(100, 0.5, days=260)
        snapshot = {'date': str(history.date.iloc[219].date()), 'results': [{'symbol': 'TEST', 'williams_r': -10}]}
        with patch('backend.routers.analysis.load_analysis_results', return_value=snapshot), patch('backend.routers.analysis.pd.read_parquet', return_value=history), patch('pathlib.Path.exists', return_value=True):
            result = daily_analysis()['results'][0]
        expected = latest_indicators(history.iloc[:220])['technical_analysis']
        self.assertEqual(result['technical_analysis'], expected)

    def test_cci_boundaries_and_macd_crossing_explanations(self):
        latest = pd.Series({'williams_r': -50, 'macd_hist': 0.1, 'macd': -2, 'ma_cross': 'equal', 'cci': 100})
        previous = pd.Series({'williams_r': -50, 'macd_hist': -0.1})
        signals = interpret_indicators(latest, previous)
        self.assertEqual(signals['williams']['direction'], 'neutral')
        self.assertEqual(signals['cci']['direction'], 'neutral')
        self.assertEqual(signals['macd']['direction'], 'bullish')
        self.assertIn('金叉', signals['macd']['reason'])
        self.assertIn('零轴下方', signals['macd']['reason'])
        latest['cci'] = -100
        latest['macd_hist'] = -0.1
        previous['macd_hist'] = 0.1
        signals = interpret_indicators(latest, previous)
        self.assertEqual(signals['cci']['direction'], 'neutral')
        self.assertEqual(signals['macd']['direction'], 'bearish')
        self.assertIn('死叉', signals['macd']['reason'])
