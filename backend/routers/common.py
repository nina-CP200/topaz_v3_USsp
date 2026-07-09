from __future__ import annotations

import os

from topaz_us.strategy import risk_level_from_score, suggest_position
from topaz_us.utils.utils import load_stock_list_from_json

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
NASDAQ100_STOCK_LIST = os.path.join(PROJECT_ROOT, "config", "nasdaq100_stocks.json")


def _load_sector_map():
    stock_list = load_stock_list_from_json(NASDAQ100_STOCK_LIST)
    return {symbol: sector for symbol, _, sector in stock_list}


_sector_map = None


def _get_sector(symbol: str) -> str:
    global _sector_map
    if _sector_map is None:
        _sector_map = _load_sector_map()
    return _sector_map.get(symbol.upper(), "Unknown")


def patch_results(results: list, regime: str = "sideways", qqq_above_ma200: bool = True) -> list:
    patched = []
    for item in results:
        r = dict(item)
        if "sector" not in r or not r.get("sector"):
            r["sector"] = _get_sector(r.get("symbol", ""))
        if "industry" not in r or not r.get("industry"):
            r["industry"] = r.get("sector", "Unknown")
        if "composite_score" not in r or r.get("composite_score") is None:
            r["composite_score"] = round(r.get("probability", 0.5) * 100, 2)
        if "reasons" not in r:
            r["reasons"] = []
        if "position_pct" not in r:
            r["position_pct"] = suggest_position(
                r.get("composite_score", 0),
                qqq_above_ma200,
                bool(r.get("active_long_signal", False)),
            )
        if "predicted_return" not in r:
            r["predicted_return"] = round((r.get("composite_score", 50) - 50) / 10, 2)
        if "risk_level" not in r:
            r["risk_level"] = risk_level_from_score(r.get("composite_score", 0))
        patched.append(r)
    return patched
