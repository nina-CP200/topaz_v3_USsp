from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter

from backend.routers.common import PROJECT_ROOT

router = APIRouter()
DATA_DIR = Path(PROJECT_ROOT) / "data" / "raw"
BASELINE_FILE = DATA_DIR / "moon_portfolio_baseline.json"
OVERLAY_FILE = DATA_DIR / "moon_portfolio_momentum_overlay.json"


def _read_backtest(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        with path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
        summary = payload.get("summary", {})
        if "portfolio_return_pct" not in summary:
            return None
        return {
            "source": path.name,
            "summary": summary,
            "daily_exposure": payload.get("daily_exposure", []),
        }
    except (OSError, json.JSONDecodeError):
        return None


@router.get("/latest")
def latest_research():
    baseline = _read_backtest(BASELINE_FILE)
    overlay = _read_backtest(OVERLAY_FILE)
    return {
        "available": baseline is not None,
        "baseline": baseline,
        "momentum_overlay": overlay,
        "message": "Run the Moon portfolio backtest and save its baseline result to data/raw/moon_portfolio_baseline.json." if baseline is None else "",
    }
