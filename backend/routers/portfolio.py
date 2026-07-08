from __future__ import annotations

import json
import os

from fastapi import APIRouter, HTTPException

from backend.routers.common import PROJECT_ROOT
from backend.schemas import PortfolioAnalyzeRequest, PortfolioSave
from topaz_us.data.api import get_stock_data
from topaz_us.portfolio import analyze_portfolio as _analyze_portfolio
from topaz_us.utils.utils import load_stock_list_from_json

router = APIRouter()

PORTFOLIO_FILE = os.path.join(PROJECT_ROOT, "data", "raw", "portfolio.json")
NASDAQ100_STOCK_LIST = os.path.join(PROJECT_ROOT, "config", "nasdaq100_stocks.json")


def _load_holdings() -> list[dict]:
    if not os.path.exists(PORTFOLIO_FILE):
        return []
    with open(PORTFOLIO_FILE, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "holdings" in data:
        return data["holdings"]
    return []


def _save_holdings(holdings: list[dict]):
    os.makedirs(os.path.dirname(PORTFOLIO_FILE), exist_ok=True)
    with open(PORTFOLIO_FILE, "w", encoding="utf-8") as f:
        json.dump(holdings, f, ensure_ascii=False, indent=2)


def _lookup_stock_name(symbol: str) -> str:
    ticker = symbol.strip().upper()
    for code, name, _ in load_stock_list_from_json(NASDAQ100_STOCK_LIST):
        if code == ticker:
            return name
    try:
        data = get_stock_data(ticker, "US")
        if data and data.get("name"):
            return data["name"]
    except Exception:
        pass
    return ticker


@router.get("")
def get_portfolio():
    holdings = _load_holdings()
    name_map = {code: name for code, name, _ in load_stock_list_from_json(NASDAQ100_STOCK_LIST)}
    for h in holdings:
        ticker = h.get("symbol", "").strip().upper()
        h["symbol"] = ticker
        if not h.get("name"):
            h["name"] = name_map.get(ticker, "") or _lookup_stock_name(ticker)
    return {"holdings": holdings}


@router.put("")
def save_portfolio(data: PortfolioSave):
    holdings = []
    for h in data.holdings:
        item = h.model_dump()
        item["symbol"] = item["symbol"].strip().upper()
        if not item.get("name"):
            item["name"] = _lookup_stock_name(item["symbol"])
        holdings.append(item)
    _save_holdings(holdings)
    return {"message": "Portfolio saved", "count": len(holdings)}


@router.post("/analyze")
def analyze(req: PortfolioAnalyzeRequest):
    if not req.holdings:
        raise HTTPException(status_code=400, detail="Portfolio is empty")

    normalized = []
    for h in req.holdings:
        normalized.append({
            "code": h.symbol.strip().upper(),
            "name": h.name,
            "shares": h.shares,
            "cost": h.cost,
        })
    return _analyze_portfolio(normalized)
