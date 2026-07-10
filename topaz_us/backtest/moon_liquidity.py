from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from topaz_us.backtest.liquidity import _benchmark_return, _prepare_benchmark, summarize_trades
from topaz_us.data.us_provider import PROJECT_ROOT, get_history_data, get_index_history, load_us_stock_list
from topaz_us.strategy import ATR_MULTIPLIER, SLOW_TMA_LENGTH, build_signal_frame


DEFAULT_STOCK_LIST = PROJECT_ROOT / "config" / "nasdaq100_stocks.json"
COMMISSION_RATE = 0.0006


@dataclass(frozen=True)
class BacktestConfig:
    days: int = 500
    max_holding_days: int = 40
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
    target_price: float | None
    return_pct: float
    holding_days: int
    exit_reason: str
    entry_setup: str


def _prepare_history(history: pd.DataFrame) -> pd.DataFrame:
    prepared = build_signal_frame(history)
    prepared["date"] = pd.to_datetime(prepared["date"]).dt.tz_localize(None)
    return prepared


def _make_trade(
    history: pd.DataFrame,
    symbol: str,
    signal_index: int,
    max_holding_days: int,
) -> Trade | None:
    if signal_index + 1 >= len(history):
        return None

    signal = history.iloc[signal_index]
    entry_index = signal_index + 1
    entry_price = float(history.iloc[entry_index]["open"])
    atr = float(signal["atr"])
    if not np.isfinite(entry_price) or entry_price <= 0 or not np.isfinite(atr) or atr <= 0:
        return None

    # The pre-existing liquidity model's protective stop is kept unchanged.
    stop_loss = float(signal["close"] - atr * ATR_MULTIPLIER)
    if stop_loss <= 0:
        return None

    last_index = min(len(history) - 1, signal_index + max_holding_days)
    exit_index = last_index
    exit_price = float(history.iloc[last_index]["close"])
    exit_reason = "time_exit"

    for index in range(entry_index, last_index + 1):
        bar = history.iloc[index]
        if float(bar["low"]) <= stop_loss:
            exit_index = index
            exit_price = stop_loss
            exit_reason = "atr_stop"
            break
        if bool(bar["bearish_sweep"]):
            exit_index = index
            exit_price = float(bar["close"])
            exit_reason = "bearish_liquidity_sweep"
            break

    entry_setup = "accumulation" if bool(signal["accumulation_entry"]) else "expansion_breakout"
    return Trade(
        symbol=symbol,
        signal_date=str(pd.Timestamp(signal["date"]).date()),
        entry_date=str(pd.Timestamp(history.iloc[entry_index]["date"]).date()),
        exit_date=str(pd.Timestamp(history.iloc[exit_index]["date"]).date()),
        entry_price=round(entry_price, 4),
        exit_price=round(exit_price, 4),
        stop_loss=round(stop_loss, 4),
        target_price=None,
        return_pct=round(float((((exit_price * (1 - COMMISSION_RATE)) / (entry_price * (1 + COMMISSION_RATE))) - 1) * 100), 4),
        holding_days=int(exit_index - signal_index),
        exit_reason=exit_reason,
        entry_setup=entry_setup,
    )


def generate_trades(
    symbol: str,
    history: pd.DataFrame,
    qqq_above_ma200: pd.Series,
    max_holding_days: int,
) -> list[Trade]:
    prepared = _prepare_history(history)
    trades: list[Trade] = []
    min_index = max(200, SLOW_TMA_LENGTH)
    next_available_index = min_index

    for index in range(min_index, len(prepared) - 1):
        if index < next_available_index:
            continue
        signal_date = pd.Timestamp(prepared.iloc[index]["date"]).normalize()
        if not bool(qqq_above_ma200.get(signal_date, False)) or not bool(prepared.iloc[index]["moon_buy_signal"]):
            continue
        trade = _make_trade(prepared, symbol, index, max_holding_days)
        if trade is not None:
            trades.append(trade)
            next_available_index = index + trade.holding_days

    return trades


def summarize_moon_trades(trades: Iterable[Trade], benchmark_history: pd.DataFrame) -> dict:
    trade_list = list(trades)
    if not trade_list:
        return {
            "trade_count": 0,
            "benchmark_return_pct": _benchmark_return(benchmark_history),
            "message": "No Moon accumulation entries in this sample.",
        }
    summary = summarize_trades(trade_list, benchmark_history)
    # Trades overlap across symbols, so mechanically compounding them would
    # misrepresent a deployable portfolio return and drawdown.
    summary.pop("trade_sequence_return_pct", None)
    summary.pop("trade_sequence_max_drawdown_pct", None)
    summary["measurement"] = "Independent-trade statistics; not a portfolio equity curve."
    summary["commission_per_side_pct"] = round(COMMISSION_RATE * 100, 3)
    summary["entry_setups"] = pd.Series([trade.entry_setup for trade in trade_list]).value_counts().to_dict()
    return summary


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
    summary = summarize_moon_trades(trades, benchmark_history)
    summary["symbols_tested"] = len(stocks) - len(skipped)
    summary["symbols_skipped"] = skipped
    summary["config"] = asdict(config)
    return {"summary": summary, "trades": [asdict(trade) for trade in trades]}


def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest Moon accumulation entries with liquidity exits.")
    parser.add_argument("--days", type=int, default=500)
    parser.add_argument("--max-holding-days", type=int, default=40)
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
