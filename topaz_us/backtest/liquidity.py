from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from topaz_us.data.us_provider import PROJECT_ROOT, get_index_history, get_history_data, load_us_stock_list
from topaz_us.strategy import (
    ATR_LENGTH,
    ATR_MULTIPLIER,
    COOLDOWN_DAYS,
    LOOKBACK,
    MAX_ATR_PCT,
    MIN_ATR_PCT,
    SMA_LENGTH,
    VOLUME_LENGTH,
    VOLUME_MULTIPLIER,
    _atr,
)


DEFAULT_STOCK_LIST = PROJECT_ROOT / "config" / "nasdaq100_stocks.json"


@dataclass(frozen=True)
class BacktestConfig:
    days: int = 300
    max_holding_days: int = 10
    max_symbols: int | None = None
    use_cache: bool = True


@dataclass(frozen=True)
class Trade:
    symbol: str
    signal_date: str
    entry_date: str
    exit_date: str
    entry_price: float
    exit_price: float
    stop_loss: float
    target_price: float
    return_pct: float
    holding_days: int
    exit_reason: str


def _prepare_history(history: pd.DataFrame) -> pd.DataFrame:
    prepared = history.copy().sort_values("date").reset_index(drop=True)
    prepared["date"] = pd.to_datetime(prepared["date"]).dt.tz_localize(None)
    prepared["sma"] = prepared["close"].rolling(SMA_LENGTH).mean()
    prepared["atr"] = _atr(prepared, ATR_LENGTH)
    prepared["avg_volume"] = prepared["volume"].rolling(VOLUME_LENGTH).mean()
    return prepared


def _prepare_benchmark(benchmark: pd.DataFrame) -> pd.Series:
    prepared = benchmark.copy().sort_values("date").reset_index(drop=True)
    prepared["date"] = pd.to_datetime(prepared["date"]).dt.tz_localize(None)
    prepared["ma200"] = prepared["close"].rolling(200).mean()
    above_ma200 = prepared["close"] > prepared["ma200"]
    return pd.Series(above_ma200.to_numpy(), index=prepared["date"]).fillna(False)


def _is_active_signal(history: pd.DataFrame, index: int, last_bullish_sweep_index: int | None) -> tuple[bool, bool]:
    row = history.iloc[index]
    structure_low = history["low"].iloc[index - LOOKBACK:index].min()
    bullish_sweep = bool(
        row["low"] < structure_low
        and row["close"] > structure_low
        and row["close"] > row["open"]
    )
    if not bullish_sweep:
        return False, False

    atr_pct = float(row["atr"] / row["close"]) if row["close"] and pd.notna(row["atr"]) else np.nan
    avg_volume = float(row["avg_volume"]) if pd.notna(row["avg_volume"]) else 0.0
    volume_ratio = float(row["volume"] / avg_volume) if avg_volume else 0.0
    cooldown_pass = last_bullish_sweep_index is None or index - last_bullish_sweep_index > COOLDOWN_DAYS

    active = bool(
        row["close"] > row["sma"]
        and MIN_ATR_PCT <= atr_pct <= MAX_ATR_PCT
        and volume_ratio >= VOLUME_MULTIPLIER
        and cooldown_pass
    )
    return True, active


def _simulate_trade(history: pd.DataFrame, symbol: str, signal_index: int, max_holding_days: int) -> Trade | None:
    if signal_index + 1 >= len(history):
        return None

    signal = history.iloc[signal_index]
    entry = history.iloc[signal_index + 1]
    entry_price = float(entry["open"])
    if not np.isfinite(entry_price) or entry_price <= 0:
        return None

    stop_loss = float(signal["close"] - signal["atr"] * ATR_MULTIPLIER)
    if not np.isfinite(stop_loss) or stop_loss <= 0:
        return None
    risk = float(signal["close"] - stop_loss)
    if risk <= 0:
        return None
    target_price = float(signal["close"] + risk)

    last_index = min(len(history) - 1, signal_index + max_holding_days)
    exit_index = last_index
    exit_price = float(history.iloc[last_index]["close"])
    exit_reason = "time_exit"

    for current_index in range(signal_index + 1, last_index + 1):
        bar = history.iloc[current_index]
        hit_stop = float(bar["low"]) <= stop_loss
        hit_target = float(bar["high"]) >= target_price
        if hit_stop:
            exit_index = current_index
            exit_price = stop_loss
            exit_reason = "stop_loss"
            break
        if hit_target:
            exit_index = current_index
            exit_price = target_price
            exit_reason = "target_1r"
            break

    return_pct = (exit_price / entry_price - 1) * 100
    return Trade(
        symbol=symbol,
        signal_date=str(pd.Timestamp(signal["date"]).date()),
        entry_date=str(pd.Timestamp(entry["date"]).date()),
        exit_date=str(pd.Timestamp(history.iloc[exit_index]["date"]).date()),
        entry_price=round(entry_price, 4),
        exit_price=round(float(exit_price), 4),
        stop_loss=round(stop_loss, 4),
        target_price=round(target_price, 4),
        return_pct=round(float(return_pct), 4),
        holding_days=int(exit_index - signal_index),
        exit_reason=exit_reason,
    )


def generate_trades(
    symbol: str,
    history: pd.DataFrame,
    qqq_above_ma200: pd.Series,
    max_holding_days: int,
) -> list[Trade]:
    prepared = _prepare_history(history)
    min_index = max(LOOKBACK, SMA_LENGTH, ATR_LENGTH, VOLUME_LENGTH, 200)
    trades: list[Trade] = []
    last_bullish_sweep_index: int | None = None

    for index in range(min_index, len(prepared) - 1):
        signal_date = pd.Timestamp(prepared.iloc[index]["date"]).normalize()
        bullish_sweep, active_signal = _is_active_signal(prepared, index, last_bullish_sweep_index)
        if bullish_sweep:
            if bool(qqq_above_ma200.get(signal_date, False)) and active_signal:
                trade = _simulate_trade(prepared, symbol, index, max_holding_days)
                if trade is not None:
                    trades.append(trade)
            last_bullish_sweep_index = index

    return trades


def summarize_trades(trades: Iterable[Trade], benchmark_history: pd.DataFrame) -> dict:
    trade_list = list(trades)
    returns = pd.Series([trade.return_pct / 100 for trade in trade_list], dtype=float)
    if returns.empty:
        return {
            "trade_count": 0,
            "benchmark_return_pct": _benchmark_return(benchmark_history),
            "message": "No active long signals in this sample.",
        }

    wins = returns[returns > 0]
    losses = returns[returns < 0]
    equity = (1 + returns).cumprod()
    drawdown = equity / equity.cummax() - 1
    profit_factor = float(wins.sum() / abs(losses.sum())) if not losses.empty else None
    exits = pd.Series([trade.exit_reason for trade in trade_list]).value_counts().to_dict()

    return {
        "trade_count": len(trade_list),
        "win_rate_pct": round(float((returns > 0).mean() * 100), 2),
        "avg_return_pct": round(float(returns.mean() * 100), 2),
        "median_return_pct": round(float(returns.median() * 100), 2),
        "best_trade_pct": round(float(returns.max() * 100), 2),
        "worst_trade_pct": round(float(returns.min() * 100), 2),
        "profit_factor": round(profit_factor, 2) if profit_factor is not None else None,
        "trade_sequence_return_pct": round(float((equity.iloc[-1] - 1) * 100), 2),
        "trade_sequence_max_drawdown_pct": round(float(drawdown.min() * 100), 2),
        "avg_holding_days": round(float(np.mean([trade.holding_days for trade in trade_list])), 2),
        "exit_reasons": exits,
        "benchmark_return_pct": _benchmark_return(benchmark_history),
        "first_signal_date": min(trade.signal_date for trade in trade_list),
        "last_signal_date": max(trade.signal_date for trade in trade_list),
    }


def _benchmark_return(history: pd.DataFrame) -> float | None:
    if history is None or len(history) < 2:
        return None
    start = float(history.iloc[0]["close"])
    end = float(history.iloc[-1]["close"])
    if start <= 0:
        return None
    return round(float((end / start - 1) * 100), 2)


def run_backtest(config: BacktestConfig, stock_list_file: str | Path = DEFAULT_STOCK_LIST) -> dict:
    stocks = load_us_stock_list(stock_list_file)
    if config.max_symbols:
        stocks = stocks[: config.max_symbols]

    benchmark_history = get_index_history("QQQ", days=config.days)
    if benchmark_history is None or len(benchmark_history) < 220:
        raise RuntimeError("QQQ history is too short for the MA200 market filter.")

    qqq_above_ma200 = _prepare_benchmark(benchmark_history)
    trades: list[Trade] = []
    skipped: list[str] = []

    for symbol, _, _ in stocks:
        history = get_history_data(symbol, days=config.days, use_cache=config.use_cache)
        if history is None or len(history) < 220:
            skipped.append(symbol)
            continue
        trades.extend(generate_trades(symbol, history, qqq_above_ma200, config.max_holding_days))

    trades.sort(key=lambda trade: (trade.entry_date, trade.symbol))
    summary = summarize_trades(trades, benchmark_history)
    summary["symbols_tested"] = len(stocks) - len(skipped)
    summary["symbols_skipped"] = skipped
    summary["config"] = asdict(config)
    return {
        "summary": summary,
        "trades": [asdict(trade) for trade in trades],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest Topaz US Liquidity Entry Signals.")
    parser.add_argument("--days", type=int, default=300)
    parser.add_argument("--max-holding-days", type=int, default=10)
    parser.add_argument("--max-symbols", type=int, default=None)
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    result = run_backtest(
        BacktestConfig(
            days=args.days,
            max_holding_days=args.max_holding_days,
            max_symbols=args.max_symbols,
            use_cache=not args.no_cache,
        )
    )
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
