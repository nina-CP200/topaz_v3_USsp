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
from topaz_us.strategy import (
    ATR_MULTIPLIER,
    MAX_ATR_PCT,
    MIN_ATR_PCT,
    SLOW_TMA_LENGTH,
    VOLUME_MULTIPLIER,
    build_signal_frame,
)


DEFAULT_STOCK_LIST = PROJECT_ROOT / "config" / "nasdaq100_stocks.json"
COMMISSION_RATE = 0.0006


@dataclass(frozen=True)
class BacktestConfig:
    days: int = 500
    max_holding_days: int = 40
    max_symbols: int | None = None
    use_cache: bool = True


@dataclass(frozen=True)
class PortfolioBacktestConfig:
    days: int = 500
    max_holding_days: int = 40
    max_positions: int = 10
    position_size_pct: float = 0.08
    initial_capital: float = 100_000.0
    use_market_momentum_overlay: bool = False
    defensive_exposure_cap: float = 0.50
    risk_off_exposure_cap: float = 0.25
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


@dataclass
class OpenPosition:
    symbol: str
    signal_date: pd.Timestamp
    entry_date: pd.Timestamp
    entry_price: float
    shares: float
    stop_loss: float
    entry_setup: str
    entry_score: float
    signal_index: int


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


def _portfolio_entry_score(row: pd.Series) -> float:
    score = 60.0 if bool(row["accumulation_entry"]) else 55.0
    if bool(row["bull_order"]):
        score += 15.0
    volume_ratio = float(row["volume_ratio"]) if pd.notna(row["volume_ratio"]) else 0.0
    if volume_ratio >= VOLUME_MULTIPLIER:
        score += 10.0
    elif volume_ratio >= 1.0:
        score += 5.0
    atr_pct = float(row["atr"] / row["close"]) if row["close"] and pd.notna(row["atr"]) else 0.0
    if MIN_ATR_PCT <= atr_pct <= MAX_ATR_PCT:
        score += 10.0
    if float(row["repair_pressure"]) >= 80:
        score -= 15.0
    # Break ties with continuous measurements rather than ticker order.
    atr = float(row["atr"]) if pd.notna(row["atr"]) else 0.0
    tma_spread = (float(row["fast_tma"]) - float(row["medium_tma"])) / atr if atr else 0.0
    score += min(6.0, max(0.0, tma_spread))
    score += min(5.0, max(0.0, float(row["ret_20"]) * 100) * 0.25) if pd.notna(row["ret_20"]) else 0.0
    score += min(4.0, max(0.0, volume_ratio - 1.0) * 2.0)
    score += min(4.0, max(0.0, float(row["repair_progress"]) - 60.0) * 0.10)
    return max(0.0, score)


def _market_momentum_states(benchmark: pd.DataFrame) -> pd.Series:
    close = benchmark["close"]
    ret_5 = close.pct_change(5)
    ret_10 = close.pct_change(10)
    ret_20 = close.pct_change(20)
    states = pd.Series("normal", index=benchmark.index, dtype="object")
    defensive = (ret_5 < 0) & (ret_10 < 0)
    risk_off = defensive & (ret_20 < 0)
    states.loc[defensive] = "defensive"
    states.loc[risk_off] = "risk_off"
    return pd.Series(states.to_numpy(), index=benchmark["date"])


def run_portfolio_backtest(
    config: PortfolioBacktestConfig,
    stock_list_file: str | Path = DEFAULT_STOCK_LIST,
) -> dict:
    """Simulate a capped, equal-weight portfolio of the daily QQQ candidates."""
    if (
        config.max_positions < 1
        or not 0 < config.position_size_pct <= 1
        or not 0 <= config.risk_off_exposure_cap <= config.defensive_exposure_cap <= 1
        or config.initial_capital <= 0
    ):
        raise ValueError("Portfolio sizing parameters must be positive.")

    stocks = load_us_stock_list(stock_list_file)
    if config.max_symbols:
        stocks = stocks[: config.max_symbols]
    benchmark_history = get_index_history("QQQ", days=config.days)
    if benchmark_history is None or len(benchmark_history) < 220:
        raise RuntimeError("QQQ history is too short for the MA200 market filter.")
    qqq_above_ma200 = _prepare_benchmark(benchmark_history)
    benchmark_frame = benchmark_history.copy().sort_values("date").reset_index(drop=True)
    benchmark_frame["date"] = pd.to_datetime(benchmark_frame["date"]).dt.tz_localize(None).dt.normalize()
    benchmark_frame["ma200"] = benchmark_frame["close"].rolling(200).mean()
    qqq_ma_ready = pd.Series(benchmark_frame["ma200"].notna().to_numpy(), index=benchmark_frame["date"])
    qqq_closes = pd.Series(benchmark_frame["close"].to_numpy(), index=benchmark_frame["date"])
    market_momentum_states = _market_momentum_states(benchmark_frame)

    frames: dict[str, pd.DataFrame] = {}
    skipped: list[str] = []
    for symbol, _, _ in stocks:
        history = get_history_data(symbol, days=config.days, use_cache=config.use_cache)
        if history is None or len(history) < 220:
            skipped.append(symbol)
            continue
        frames[symbol] = _prepare_history(history)

    candidates_by_date: dict[pd.Timestamp, list[tuple[float, str, int]]] = {}
    for symbol, frame in frames.items():
        for index in range(max(200, SLOW_TMA_LENGTH), len(frame) - 1):
            signal = frame.iloc[index]
            signal_date = pd.Timestamp(signal["date"]).normalize()
            if (
                not bool(qqq_above_ma200.get(signal_date, False))
                or not bool(signal["moon_buy_signal"])
                or (config.use_market_momentum_overlay and market_momentum_states.get(signal_date) != "normal")
            ):
                continue
            entry_date = pd.Timestamp(frame.iloc[index + 1]["date"]).normalize()
            candidates_by_date.setdefault(entry_date, []).append((_portfolio_entry_score(signal), symbol, index))

    benchmark_dates = pd.to_datetime(benchmark_history["date"]).dt.tz_localize(None).dt.normalize()
    cash = float(config.initial_capital)
    positions: dict[str, OpenPosition] = {}
    pending_exits: dict[pd.Timestamp, set[str]] = {}
    pending_market_caps: dict[pd.Timestamp, tuple[float, str]] = {}
    trades: list[Trade] = []
    equity_curve: list[tuple[pd.Timestamp, float]] = []
    exposure_samples: list[float] = []
    daily_states: list[dict] = []
    max_positions_used = 0
    candidates_considered = 0
    candidates_rejected_capacity = 0

    def close_position(position: OpenPosition, date: pd.Timestamp, price: float, reason: str) -> None:
        nonlocal cash
        proceeds = position.shares * price * (1 - COMMISSION_RATE)
        cash += proceeds
        return_pct = (((price * (1 - COMMISSION_RATE)) / (position.entry_price * (1 + COMMISSION_RATE))) - 1) * 100
        trades.append(Trade(
            symbol=position.symbol,
            signal_date=str(position.signal_date.date()),
            entry_date=str(position.entry_date.date()),
            exit_date=str(date.date()),
            entry_price=round(position.entry_price, 4),
            exit_price=round(price, 4),
            stop_loss=round(position.stop_loss, 4),
            target_price=None,
            return_pct=round(float(return_pct), 4),
            holding_days=int((date - position.signal_date).days),
            exit_reason=reason,
            entry_setup=position.entry_setup,
        ))
        positions.pop(position.symbol, None)

    for date_index, date in enumerate(benchmark_dates):
        bars = {
            symbol: frame.loc[frame["date"] == date].iloc[0]
            for symbol, frame in frames.items()
            if (frame["date"] == date).any()
        }

        for symbol in pending_exits.pop(date, set()):
            position = positions.get(symbol)
            bar = bars.get(symbol)
            if position is not None and bar is not None:
                close_position(position, date, float(bar["open"]), "bearish_liquidity_sweep")

        pending_cap = pending_market_caps.pop(date, None)
        if pending_cap is not None:
            cap, reason = pending_cap
            gross_value = sum(position.shares * float(bars[position.symbol]["open"]) for position in positions.values() if position.symbol in bars)
            equity_at_open = cash + gross_value
            for position in sorted(positions.values(), key=lambda item: item.entry_score):
                if not equity_at_open or gross_value / equity_at_open <= cap:
                    break
                bar = bars.get(position.symbol)
                if bar is None:
                    continue
                gross_value -= position.shares * float(bar["open"])
                close_position(position, date, float(bar["open"]), reason)
                equity_at_open = cash + gross_value

        equity_at_open = cash + sum(position.shares * float(bars[position.symbol]["open"]) for position in positions.values() if position.symbol in bars)
        daily_candidates = sorted(candidates_by_date.get(date, []), reverse=True)
        candidates_considered += len(daily_candidates)
        for score, symbol, signal_index in daily_candidates:
            if symbol in positions:
                continue
            if len(positions) >= config.max_positions:
                candidates_rejected_capacity += 1
                continue
            bar = bars.get(symbol)
            if bar is None:
                continue
            allocation = min(equity_at_open * config.position_size_pct, cash)
            entry_price = float(bar["open"])
            if allocation <= 0 or entry_price <= 0:
                continue
            shares = allocation / (entry_price * (1 + COMMISSION_RATE))
            cash -= shares * entry_price * (1 + COMMISSION_RATE)
            signal = frames[symbol].iloc[signal_index]
            entry_setup = "accumulation" if bool(signal["accumulation_entry"]) else "expansion_breakout"
            positions[symbol] = OpenPosition(
                symbol=symbol,
                signal_date=pd.Timestamp(signal["date"]).normalize(),
                entry_date=date,
                entry_price=entry_price,
                shares=shares,
                stop_loss=float(signal["close"] - signal["atr"] * ATR_MULTIPLIER),
                entry_setup=entry_setup,
                entry_score=score,
                signal_index=signal_index,
            )

        for symbol, position in list(positions.items()):
            bar = bars.get(symbol)
            if bar is not None and float(bar["low"]) <= position.stop_loss:
                close_position(position, date, min(float(bar["open"]), position.stop_loss), "atr_stop")

        for symbol, position in list(positions.items()):
            bar = bars.get(symbol)
            if bar is None:
                continue
            symbol_frame = frames[symbol]
            row_indexes = symbol_frame.index[symbol_frame["date"] == date]
            if len(row_indexes) == 0:
                continue
            current_index = int(row_indexes[0])
            if current_index - position.signal_index >= config.max_holding_days:
                close_position(position, date, float(bar["close"]), "time_exit")
            elif bool(bar["bearish_sweep"]) and current_index + 1 < len(symbol_frame):
                exit_date = pd.Timestamp(symbol_frame.iloc[current_index + 1]["date"]).normalize()
                pending_exits.setdefault(exit_date, set()).add(symbol)

        market_momentum_state = market_momentum_states.get(date, "normal")
        if config.use_market_momentum_overlay and date_index + 1 < len(benchmark_dates):
            next_date = benchmark_dates.iloc[date_index + 1]
            if market_momentum_state == "risk_off":
                pending_market_caps[next_date] = (config.risk_off_exposure_cap, "market_momentum_risk_off")
            elif market_momentum_state == "defensive":
                existing = pending_market_caps.get(next_date)
                if existing is None or existing[0] > config.defensive_exposure_cap:
                    pending_market_caps[next_date] = (config.defensive_exposure_cap, "market_momentum_defensive")

        mark_to_market = cash + sum(position.shares * float(bars[position.symbol]["close"]) for position in positions.values() if position.symbol in bars)
        equity_curve.append((date, mark_to_market))
        invested_pct = (mark_to_market - cash) / mark_to_market if mark_to_market else 0.0
        exposure_samples.append(invested_pct)
        daily_states.append({
            "date": date,
            "holdings": len(positions),
            "invested_pct": invested_pct,
            "equity": mark_to_market,
            "qqq_close": float(qqq_closes.get(date, np.nan)),
            "qqq_ma200_ready": bool(qqq_ma_ready.get(date, False)),
            "qqq_above_ma200": bool(qqq_above_ma200.get(date, False)),
            "market_momentum_state": market_momentum_state,
        })
        max_positions_used = max(max_positions_used, len(positions))

    final_date = benchmark_dates.iloc[-1]
    final_bars = {
        symbol: frame.loc[frame["date"] == final_date].iloc[0]
        for symbol, frame in frames.items()
        if (frame["date"] == final_date).any()
    }
    for symbol, position in list(positions.items()):
        bar = final_bars.get(symbol)
        if bar is not None:
            close_position(position, final_date, float(bar["close"]), "end_of_sample")

    equity = pd.Series([value for _, value in equity_curve], dtype=float)
    drawdown = equity / equity.cummax() - 1
    flat_periods: list[dict] = []
    active_period: list[dict] = []
    for state in daily_states:
        is_flat = state["qqq_ma200_ready"] and state["holdings"] == 0
        if is_flat:
            active_period.append(state)
        elif active_period:
            blocked_days = sum(not item["qqq_above_ma200"] for item in active_period)
            blocked_dates = [str(item["date"].date()) for item in active_period if not item["qqq_above_ma200"]]
            allowed_dates = [str(item["date"].date()) for item in active_period if item["qqq_above_ma200"]]
            flat_periods.append({
                "start": str(active_period[0]["date"].date()),
                "end": str(active_period[-1]["date"].date()),
                "trading_days": len(active_period),
                "qqq_below_ma200_days": blocked_days,
                "qqq_below_ma200_dates": blocked_dates,
                "qqq_above_ma200_dates": allowed_dates,
                "reason": "QQQ below MA200" if blocked_days / len(active_period) >= 0.8 else "No open qualifying positions",
            })
            active_period = []
    if active_period:
        blocked_days = sum(not item["qqq_above_ma200"] for item in active_period)
        blocked_dates = [str(item["date"].date()) for item in active_period if not item["qqq_above_ma200"]]
        allowed_dates = [str(item["date"].date()) for item in active_period if item["qqq_above_ma200"]]
        flat_periods.append({
            "start": str(active_period[0]["date"].date()),
            "end": str(active_period[-1]["date"].date()),
            "trading_days": len(active_period),
            "qqq_below_ma200_days": blocked_days,
            "qqq_below_ma200_dates": blocked_dates,
            "qqq_above_ma200_dates": allowed_dates,
            "reason": "QQQ below MA200" if blocked_days / len(active_period) >= 0.8 else "No open qualifying positions",
        })

    low_exposure_periods: list[dict] = []
    active_period = []
    for state in daily_states:
        is_low_exposure = state["qqq_ma200_ready"] and state["invested_pct"] < 0.35
        if is_low_exposure:
            active_period.append(state)
        elif active_period:
            blocked_days = sum(not item["qqq_above_ma200"] for item in active_period)
            exposures = [item["invested_pct"] * 100 for item in active_period]
            low_exposure_periods.append({
                "start": str(active_period[0]["date"].date()),
                "end": str(active_period[-1]["date"].date()),
                "trading_days": len(active_period),
                "average_invested_pct": round(float(np.mean(exposures)), 2),
                "min_invested_pct": round(float(min(exposures)), 2),
                "qqq_below_ma200_days": blocked_days,
            })
            active_period = []
    if active_period:
        blocked_days = sum(not item["qqq_above_ma200"] for item in active_period)
        exposures = [item["invested_pct"] * 100 for item in active_period]
        low_exposure_periods.append({
            "start": str(active_period[0]["date"].date()),
            "end": str(active_period[-1]["date"].date()),
            "trading_days": len(active_period),
            "average_invested_pct": round(float(np.mean(exposures)), 2),
            "min_invested_pct": round(float(min(exposures)), 2),
            "qqq_below_ma200_days": blocked_days,
        })
    summary = summarize_moon_trades(trades, benchmark_history)
    summary.update({
        "measurement": "Daily marked-to-market portfolio equity curve.",
        "portfolio_return_pct": round((cash / config.initial_capital - 1) * 100, 2),
        "portfolio_max_drawdown_pct": round(float(drawdown.min() * 100), 2),
        "final_equity": round(cash, 2),
        "average_invested_pct": round(float(np.mean(exposure_samples) * 100), 2),
        "max_positions_used": max_positions_used,
        "candidates_considered": candidates_considered,
        "candidates_rejected_capacity": candidates_rejected_capacity,
        "market_momentum_overlay": config.use_market_momentum_overlay,
        "flat_periods": flat_periods,
        "low_exposure_periods": low_exposure_periods,
        "symbols_tested": len(frames),
        "symbols_skipped": skipped,
        "survivorship_bias_note": "Uses the current static NASDAQ 100/QQQ-like universe for the full period.",
        "config": asdict(config),
    })
    return {
        "summary": summary,
        "trades": [asdict(trade) for trade in trades],
        "daily_exposure": [
            {
                "date": str(state["date"].date()),
                "holdings": state["holdings"],
                "invested_pct": round(state["invested_pct"] * 100, 2),
                "equity": round(state["equity"], 2),
                "qqq_close": round(state["qqq_close"], 4),
                "qqq_ma200_ready": state["qqq_ma200_ready"],
                "qqq_above_ma200": state["qqq_above_ma200"],
                "market_momentum_state": state["market_momentum_state"],
            }
            for state in daily_states
        ],
    }


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
