import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from backend.routers import watchlist
from tests.test_us_strategy import make_history
from types import SimpleNamespace


class WatchlistTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'watchlist.json'
        self.patch = patch.object(watchlist, 'WATCHLIST_FILE', self.path)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.universe = patch.object(watchlist, 'load_us_stock_list', return_value=[('AAPL', 'Apple', ''), ('MSFT', 'Microsoft', '')])
        self.history = patch.object(watchlist, 'get_history_data', return_value=make_history(100, 0.5))
        self.history_mock = self.history.start()
        self.addCleanup(self.history.stop)
        self.universe.start()
        self.addCleanup(self.universe.stop)

    def test_add_persists_normalizes_and_deduplicates(self):
        self.assertEqual(watchlist.get_watchlist(), {'symbols': []})
        watchlist.add_to_watchlist(' aapl ')
        watchlist.add_to_watchlist('AAPL')
        watchlist.add_to_watchlist('msft')
        self.assertEqual(json.loads(self.path.read_text()), {'symbols': ['AAPL', 'MSFT']})
        self.assertEqual(watchlist.get_watchlist(), {'symbols': ['AAPL', 'MSFT']})

    def test_remove_is_idempotent_and_preserves_other_stocks(self):
        watchlist.add_to_watchlist('AAPL')
        watchlist.add_to_watchlist('MSFT')
        watchlist.remove_from_watchlist('aapl')
        watchlist.remove_from_watchlist('AAPL')
        self.assertEqual(watchlist.get_watchlist(), {'symbols': ['MSFT']})

    def test_invalid_or_unknown_symbol_cannot_change_file(self):
        watchlist.add_to_watchlist('AAPL')
        saved = self.path.read_text()
        self.history_mock.return_value = None
        for symbol in ('../secret', 'UNKNOWN'):
            with self.assertRaises(HTTPException):
                watchlist.add_to_watchlist(symbol)
        self.assertEqual(self.path.read_text(), saved)

    def test_corrupt_file_is_preserved_and_reports_failure(self):
        self.path.write_text('broken data')
        with self.assertRaises(HTTPException):
            watchlist.add_to_watchlist('AAPL')
        self.assertEqual(self.path.read_text(), 'broken data')

    def test_failed_atomic_write_retains_saved_list(self):
        watchlist.add_to_watchlist('AAPL')
        with patch.object(watchlist.os, 'replace', side_effect=OSError('write failed')):
            with self.assertRaises(HTTPException):
                watchlist.add_to_watchlist('MSFT')
        self.assertEqual(watchlist.get_watchlist(), {'symbols': ['AAPL']})
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_external_stock_can_be_added_and_analyzed(self):
        watchlist.add_to_watchlist('KO')
        self.assertEqual(watchlist.get_watchlist()['symbols'], ['KO'])
        result = watchlist.watchlist_analysis()
        self.assertEqual(result['failed'], [])
        row = result['results'][0]
        self.assertEqual(row['symbol'], 'KO')
        self.assertEqual(set(row['technical_analysis']['horizons']), {'short', 'medium', 'long'})
        self.assertIn('label', row['moon_analysis'])
        self.assertEqual(row['position_pct'], 0)

    def test_custom_analysis_does_not_expand_original_universe(self):
        watchlist.add_to_watchlist('AAPL')
        self.assertEqual(watchlist.watchlist_analysis(), {'results': [], 'failed': []})
        self.history_mock.assert_not_called()

    def test_search_includes_us_external_results_and_filters_other_markets(self):
        response = SimpleNamespace(quotes=[{'symbol': 'KO', 'longname': 'The Coca-Cola Company', 'quoteType': 'EQUITY', 'exchange': 'NYQ'}, {'symbol': 'VOD.L', 'quoteType': 'EQUITY', 'exchange': 'LSE'}])
        with patch('yfinance.Search', return_value=response):
            result = watchlist.search_symbols('Coca Cola')
        self.assertEqual([item['symbol'] for item in result['results']], ['KO'])

    def test_search_failure_keeps_local_results_and_explains_direct_add(self):
        with patch('yfinance.Search', side_effect=RuntimeError('offline')):
            result = watchlist.search_symbols('Apple')
        self.assertEqual(result['results'][0]['symbol'], 'AAPL')
        self.assertIn('warning', result)

    def test_unavailable_custom_history_stays_saved(self):
        watchlist.add_to_watchlist('KO')
        self.history_mock.return_value = None
        result = watchlist.watchlist_analysis()
        self.assertEqual(result['failed'], ['KO'])
        self.assertEqual(watchlist.get_watchlist()['symbols'], ['KO'])
