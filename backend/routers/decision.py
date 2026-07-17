from __future__ import annotations

from fastapi import APIRouter

from backend.routers.analysis import get_status_snapshot
from backend.routers.common import patch_results
from backend.routers.portfolio import _load_holdings
from backend.routers.settings import load_decision_settings
from topaz_us.analysis.query import load_analysis_results
from topaz_us.decision import build_decision_snapshot

router = APIRouter()


@router.get("/daily")
def daily_decision():
    analysis = load_analysis_results()
    if analysis is not None:
        copied = dict(analysis)
        copied["results"] = patch_results(
            analysis.get("results", analysis.get("all_results", [])),
            analysis.get("market_regime", "sideways"),
            analysis.get("qqq_above_ma200", True),
        )
        analysis = copied
    settings = load_decision_settings()
    return build_decision_snapshot(
        analysis,
        _load_holdings(),
        settings["investable_capital_usd"],
        get_status_snapshot(),
    )
