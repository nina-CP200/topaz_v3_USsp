"""Local watchlist shared by browser sessions on this installation."""
from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo
import os
from pathlib import Path
import re
import tempfile
import threading

from fastapi import APIRouter, HTTPException, Query

from backend.routers.common import PROJECT_ROOT, NASDAQ100_STOCK_LIST
from topaz_us.data.us_provider import load_us_stock_list, normalize_symbol, get_history_data, _get_yfinance_proxy
from topaz_us.data.regime import classify_qqq_regime
from topaz_us.indicators import latest_indicators

router = APIRouter()
WATCHLIST_FILE = Path(PROJECT_ROOT) / "data" / "raw" / "watchlist.json"
_lock = threading.Lock()


def _load() -> list[str]:
    if not WATCHLIST_FILE.exists():
        return []
    try:
        data = json.loads(WATCHLIST_FILE.read_text(encoding="utf-8"))
        symbols = data["symbols"]
        if not isinstance(symbols, list) or any(not isinstance(symbol, str) or not re.fullmatch(r"[A-Z0-9][A-Z0-9-]{0,19}", symbol) for symbol in symbols):
            raise ValueError("Invalid watchlist")
        return list(dict.fromkeys(symbols))
    except (OSError, ValueError, TypeError, KeyError) as error:
        raise HTTPException(status_code=500, detail="自选列表读取失败，原文件已保留，请检查本地数据文件。") from error


def _save(symbols: list[str]):
    WATCHLIST_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=WATCHLIST_FILE.parent, delete=False) as handle:
            temporary = handle.name
            json.dump({"symbols": symbols}, handle, ensure_ascii=False, indent=2)
        os.replace(temporary, WATCHLIST_FILE)
    except OSError as error:
        raise HTTPException(status_code=500, detail="自选列表保存失败，请重试。") from error
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def _symbol(value: str) -> str:
    symbol = normalize_symbol(value)
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9-]{0,19}", symbol):
        raise HTTPException(status_code=422, detail="股票代码格式无效。")
    return symbol


@router.get("")
def get_watchlist():
    with _lock:
        return {"symbols": _load()}


@router.get("/search")
def search_symbols(q: str = Query(..., min_length=1, max_length=80)):
    query = q.strip()
    if not query:
        return {"results": []}
    local = [{"symbol": code, "name": name, "exchange": "NASDAQ"} for code, name, _ in load_us_stock_list(NASDAQ100_STOCK_LIST) if query.lower() in f"{code} {name}".lower()]
    try:
        import yfinance as yf
        response = yf.Search(query, max_results=15, news_count=0, lists_count=0, timeout=8, proxy=_get_yfinance_proxy())
        remote = []
        for item in response.quotes:
            if item.get("quoteType") not in {"EQUITY", "ETF"} or item.get("exchange") not in {"NMS", "NGM", "NCM", "NYQ", "ASE", "PCX", "BTS", "NAS", "NYS", "NYE"}:
                continue
            symbol = normalize_symbol(item.get("symbol", ""))
            if re.fullmatch(r"[A-Z0-9][A-Z0-9-]{0,19}", symbol):
                remote.append({"symbol": symbol, "name": item.get("longname") or item.get("shortname") or symbol, "exchange": item.get("exchDisp") or item.get("exchange", "")})
        return {"results": list({item["symbol"]: item for item in [*local, *remote]}.values())[:15]}
    except Exception:
        return {"results": local[:15], "warning": "在线搜索暂不可用。可以输入完整股票代码直接添加，系统会验证行情。"}


@router.get("/analysis")
def watchlist_analysis():
    with _lock:
        symbols = _load()
    universe = {code for code, _, _ in load_us_stock_list(NASDAQ100_STOCK_LIST)}
    custom = [symbol for symbol in symbols if symbol not in universe]
    results, failed = [], []
    if not custom:
        return {"results": results, "failed": failed}
    try:
        market = classify_qqq_regime(get_history_data("QQQ", days=300))
        gate = bool(market.get("qqq_above_ma200", False))
    except Exception:
        gate = None
    for symbol in custom:
        try:
            history = get_history_data(symbol, days=300)
            if history is None or history.empty:
                raise ValueError("No history")
            history = history.sort_values("date").reset_index(drop=True)
            close = float(history.iloc[-1]["close"])
            previous = float(history.iloc[-2]["close"]) if len(history) > 1 else close
            indicators = latest_indicators(history, gate)
            moon = indicators["moon_analysis"]
            results.append({**indicators, "symbol": symbol, "name": symbol, "sector": "自选标的", "industry": "自选标的", "current_price": round(close, 2), "change_pct": round((close / previous - 1) * 100, 2) if previous else 0,
                "analysis_date": datetime.now(ZoneInfo("Asia/Tokyo")).isoformat(timespec="minutes"), "rank": len(results) + 1, "composite_score": 0, "advice": "自选观察", "position_pct": 0, "risk_level": "unknown", "reasons": [moon["reason"]],
                "active_long_signal": bool(moon["triggered"] and moon["direction"] == "bullish" and gate is True), "bearish_sweep": moon["label"] == "退出预警", "signal_status": "Market Hold" if moon["label"] == "等待市场" else "No Signal"})
        except Exception:
            failed.append(symbol)
    return {"results": results, "failed": failed}


@router.put("/{symbol}")
def add_to_watchlist(symbol: str):
    symbol = _symbol(symbol)
    universe = {code for code, _, _ in load_us_stock_list(NASDAQ100_STOCK_LIST)}
    if symbol not in universe:
        try:
            history = get_history_data(symbol, days=300)
        except Exception as error:
            raise HTTPException(status_code=502, detail="行情验证暂时失败，请稍后重试。") from error
        if history is None or history.empty:
            raise HTTPException(status_code=400, detail="未找到可用行情，请核对完整股票代码。")
    with _lock:
        symbols = _load()
        if symbol not in symbols:
            symbols.append(symbol)
            _save(symbols)
        return {"symbols": symbols}


@router.delete("/{symbol}")
def remove_from_watchlist(symbol: str):
    symbol = _symbol(symbol)
    with _lock:
        symbols = _load()
        if symbol in symbols:
            symbols.remove(symbol)
            _save(symbols)
        return {"symbols": symbols}
