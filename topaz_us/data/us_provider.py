from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
HISTORY_DIR = RAW_DIR / "us_history"


def normalize_symbol(symbol: str) -> str:
    return symbol.strip().upper().replace(".", "-")


def load_us_stock_list(file_path: str | os.PathLike) -> List[Tuple[str, str, str]]:
    if not os.path.exists(file_path):
        return []
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    stocks = []
    for item in data:
        symbol = normalize_symbol(item.get("code", ""))
        if not symbol:
            continue
        stocks.append((symbol, item.get("name", symbol), item.get("sector", "")))
    return stocks


def _cache_path(symbol: str) -> Path:
    return HISTORY_DIR / f"{normalize_symbol(symbol)}.parquet"


def _normalize_history(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    normalized = df.copy()
    if isinstance(normalized.columns, pd.MultiIndex):
        normalized.columns = [col[0] for col in normalized.columns]
    normalized = normalized.reset_index()

    rename = {
        "Date": "date",
        "Datetime": "date",
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Adj Close": "adj_close",
        "Volume": "volume",
    }
    normalized = normalized.rename(columns=rename)
    keep = [c for c in ["date", "open", "high", "low", "close", "volume"] if c in normalized.columns]
    normalized = normalized[keep]
    if "date" not in normalized.columns or "close" not in normalized.columns:
        return pd.DataFrame()

    normalized["date"] = pd.to_datetime(normalized["date"]).dt.tz_localize(None)
    for col in ["open", "high", "low", "close", "volume"]:
        if col in normalized.columns:
            normalized[col] = pd.to_numeric(normalized[col], errors="coerce")
    normalized["symbol"] = normalize_symbol(symbol)
    normalized = normalized.dropna(subset=["date", "close"]).sort_values("date")
    return normalized.reset_index(drop=True)


def _download_history(symbol: str, period: str = "2y", interval: str = "1d") -> pd.DataFrame:
    import yfinance as yf

    ticker = normalize_symbol(symbol)
    df = yf.download(
        ticker,
        period=period,
        interval=interval,
        auto_adjust=True,
        progress=False,
        threads=False,
    )
    return _normalize_history(df, ticker)


def get_history_data(
    symbol: str,
    market: str = "US",
    days: int = 300,
    use_cache: bool = True,
) -> Optional[pd.DataFrame]:
    ticker = normalize_symbol(symbol)
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(ticker)

    if use_cache and path.exists():
        try:
            cached = pd.read_parquet(path)
            cached["date"] = pd.to_datetime(cached["date"])
            if len(cached) >= min(days, 30):
                return cached.tail(days).reset_index(drop=True)
        except Exception:
            pass

    history = _download_history(ticker, period="2y")
    if history.empty:
        return None
    if use_cache:
        history.to_parquet(path, index=False)
    return history.tail(days).reset_index(drop=True)


def get_stock_data(symbol: str, market: str = "US", name: str | None = None) -> Optional[Dict]:
    history = get_history_data(symbol, market=market, days=5)
    if history is None or len(history) < 1:
        return None

    latest = history.iloc[-1]
    prev_close = history.iloc[-2]["close"] if len(history) >= 2 else latest["close"]
    current_price = float(latest["close"])
    change_pct = (current_price / float(prev_close) - 1) * 100 if prev_close else 0.0
    return {
        "symbol": normalize_symbol(symbol),
        "name": name or normalize_symbol(symbol),
        "current_price": current_price,
        "prev_close": float(prev_close),
        "change": change_pct,
        "change_pct": change_pct,
        "open": float(latest.get("open", current_price)),
        "high": float(latest.get("high", current_price)),
        "low": float(latest.get("low", current_price)),
        "volume": float(latest.get("volume", 0)),
        "currency": "USD",
    }


def get_index_history(index_code: str = "QQQ", days: int = 300) -> Optional[pd.DataFrame]:
    return get_history_data(index_code, market="US", days=days)


def get_index_data(index_code: str = "QQQ") -> Optional[Dict]:
    data = get_stock_data(index_code, market="US", name=index_code)
    if not data:
        return None
    return {
        "code": index_code,
        "name": "Invesco QQQ Trust" if index_code == "QQQ" else index_code,
        "price": data["current_price"],
        "prev_close": data["prev_close"],
        "change_pct": data["change_pct"],
        "high": data["high"],
        "low": data["low"],
        "open": data["open"],
        "volume": data["volume"],
    }


def load_histories(
    symbols: Iterable[str],
    days: int = 300,
    use_cache: bool = True,
) -> Dict[str, pd.DataFrame]:
    histories = {}
    for symbol in symbols:
        history = get_history_data(symbol, days=days, use_cache=use_cache)
        if history is not None and len(history) >= 60:
            histories[normalize_symbol(symbol)] = history
    return histories

