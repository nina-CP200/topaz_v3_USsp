from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import numpy as np
import pandas as pd


LOOKBACK = 20
SMA_LENGTH = 50
ATR_LENGTH = 14
VOLUME_LENGTH = 20
COOLDOWN_DAYS = 5
ATR_MULTIPLIER = 1.5
MIN_ATR_PCT = 0.012
MAX_ATR_PCT = 0.085
VOLUME_MULTIPLIER = 1.05


@dataclass
class ScoreBreakdown:
    signal_score: float
    trend_score: float
    volume_score: float
    volatility_score: float
    risk_penalty: float
    raw_score: float
    composite_score: float
    reasons: List[str]

    @property
    def relative_strength_score(self) -> float:
        return self.volume_score

    @property
    def momentum_score(self) -> float:
        return self.volatility_score

    @property
    def entry_score(self) -> float:
        return self.signal_score


def _safe_return(close: pd.Series, window: int) -> float:
    if len(close) <= window or close.iloc[-window] == 0:
        return 0.0
    return float(close.iloc[-1] / close.iloc[-window] - 1)


def _atr(history: pd.DataFrame, length: int = ATR_LENGTH) -> pd.Series:
    high = history["high"]
    low = history["low"]
    close = history["close"]
    prev_close = close.shift(1)
    true_range = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return true_range.rolling(length).mean()


def _days_since_prior_bullish_sweep(history: pd.DataFrame, lookback: int = LOOKBACK) -> int | None:
    if len(history) < lookback + 2:
        return None

    lows = history["low"]
    opens = history["open"]
    closes = history["close"]
    structure_lows = lows.shift(1).rolling(lookback).min()
    prior = history.iloc[:-1].copy()
    prior_structure_lows = structure_lows.iloc[:-1]
    sweeps = (
        (prior["low"] < prior_structure_lows)
        & (prior["close"] > prior_structure_lows)
        & (prior["close"] > prior["open"])
    )
    sweep_indexes = np.flatnonzero(sweeps.fillna(False).to_numpy())
    if len(sweep_indexes) == 0:
        return None
    return int((len(history) - 1) - sweep_indexes[-1])


def build_cross_section_features(
    histories: Dict[str, pd.DataFrame],
    benchmark_history: pd.DataFrame,
) -> pd.DataFrame:
    rows = []

    for symbol, history in histories.items():
        if history is None or len(history) < max(LOOKBACK + 2, SMA_LENGTH, ATR_LENGTH + 2):
            continue

        close = history["close"]
        open_ = history["open"]
        high = history["high"]
        low = history["low"]
        volume = history.get("volume", pd.Series([0] * len(history)))

        latest_close = float(close.iloc[-1])
        latest_open = float(open_.iloc[-1])
        prev_close = float(close.iloc[-2]) if len(close) >= 2 else latest_close
        structure_low = low.shift(1).rolling(LOOKBACK).min().iloc[-1]
        structure_high = high.shift(1).rolling(LOOKBACK).max().iloc[-1]
        sma = close.rolling(SMA_LENGTH).mean().iloc[-1]
        ma200 = close.rolling(200).mean().iloc[-1] if len(close) >= 200 else close.rolling(60).mean().iloc[-1]
        atr_value = _atr(history).iloc[-1]
        atr_pct = float(atr_value / latest_close) if latest_close and pd.notna(atr_value) else 0.0
        avg_volume = volume.rolling(VOLUME_LENGTH).mean().iloc[-1] if len(volume) >= VOLUME_LENGTH else 0
        volume_ratio = float(volume.iloc[-1] / avg_volume) if avg_volume else 0.0
        days_since_signal = _days_since_prior_bullish_sweep(history)

        bullish_sweep = bool(
            pd.notna(structure_low)
            and low.iloc[-1] < structure_low
            and latest_close > structure_low
            and latest_close > latest_open
        )
        bearish_sweep = bool(
            pd.notna(structure_high)
            and high.iloc[-1] > structure_high
            and latest_close < structure_high
            and latest_close < latest_open
        )
        trend_filter = bool(pd.notna(sma) and latest_close > sma)
        volatility_filter = bool(MIN_ATR_PCT <= atr_pct <= MAX_ATR_PCT)
        volume_filter = bool(volume_ratio >= VOLUME_MULTIPLIER)
        cooldown_pass = days_since_signal is None or days_since_signal > COOLDOWN_DAYS
        active_long_signal = bool(bullish_sweep and trend_filter and volatility_filter and volume_filter and cooldown_pass)

        entry_price = latest_close if bullish_sweep else None
        stop_loss = None
        tp1 = None
        tp2 = None
        tp3 = None
        if entry_price and atr_value and pd.notna(atr_value):
            stop_loss = float(entry_price - atr_value * ATR_MULTIPLIER)
            risk = entry_price - stop_loss
            tp1 = float(entry_price + risk)
            tp2 = float(entry_price + risk * 2)
            tp3 = float(entry_price + risk * 3)

        rows.append({
            "symbol": symbol,
            "current_price": latest_close,
            "change_pct": float((latest_close / prev_close - 1) * 100) if prev_close else 0.0,
            "ma20": float(close.rolling(20).mean().iloc[-1]),
            "ma50": float(sma),
            "ma200": float(ma200),
            "ret_20": _safe_return(close, 20),
            "structure_low": float(structure_low) if pd.notna(structure_low) else None,
            "structure_high": float(structure_high) if pd.notna(structure_high) else None,
            "atr": float(atr_value) if pd.notna(atr_value) else 0.0,
            "atr_pct": atr_pct,
            "volume_ratio": volume_ratio,
            "bullish_sweep": bullish_sweep,
            "bearish_sweep": bearish_sweep,
            "trend_filter": trend_filter,
            "volatility_filter": volatility_filter,
            "volume_filter": volume_filter,
            "cooldown_pass": cooldown_pass,
            "active_long_signal": active_long_signal,
            "days_since_signal": days_since_signal,
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "tp1": tp1,
            "tp2": tp2,
            "tp3": tp3,
        })

    return pd.DataFrame(rows)


def score_stock(row: pd.Series) -> ScoreBreakdown:
    reasons: List[str] = []

    bullish_sweep = bool(row.get("bullish_sweep", False))
    bearish_sweep = bool(row.get("bearish_sweep", False))
    trend_filter = bool(row.get("trend_filter", False))
    volatility_filter = bool(row.get("volatility_filter", False))
    volume_filter = bool(row.get("volume_filter", False))
    cooldown_pass = bool(row.get("cooldown_pass", False))

    signal_score = 0.0
    if bullish_sweep:
        signal_score += 50
        reasons.append("Bullish liquidity sweep")
    else:
        reasons.append("No bullish sweep today")

    trend_score = 15.0 if trend_filter else 0.0
    if trend_filter:
        reasons.append("Trend filter passed")

    volume_score = 10.0 if volume_filter else 0.0
    if volume_filter:
        reasons.append("Volume confirmation")

    volatility_score = 10.0 if volatility_filter else 0.0
    if volatility_filter:
        reasons.append("ATR filter passed")

    if cooldown_pass:
        cooldown_score = 5.0
        if bullish_sweep:
            reasons.append("Cooldown clear")
    else:
        cooldown_score = 0.0
        reasons.append("Cooldown active")

    risk_penalty = 0.0
    if bearish_sweep:
        risk_penalty += 25
        reasons.append("Bearish sweep risk")
    if row.get("atr_pct", 0) > MAX_ATR_PCT:
        risk_penalty += 10
        reasons.append("ATR too wide")

    raw_score = signal_score + trend_score + volume_score + volatility_score + cooldown_score - risk_penalty
    composite_score = max(0.0, min(100.0, raw_score))

    return ScoreBreakdown(
        signal_score=round(signal_score, 2),
        trend_score=round(trend_score, 2),
        volume_score=round(volume_score, 2),
        volatility_score=round(volatility_score, 2),
        risk_penalty=round(risk_penalty, 2),
        raw_score=round(raw_score, 2),
        composite_score=round(composite_score, 2),
        reasons=reasons[:6],
    )


def get_advice_from_score(
    composite_score: float,
    qqq_above_ma200: bool = True,
    active_long_signal: bool = False,
) -> str:
    if active_long_signal and qqq_above_ma200 and composite_score >= 85:
        return "建议买入"
    if active_long_signal and qqq_above_ma200:
        return "可以关注"
    if composite_score >= 65:
        return "可以关注"
    if composite_score >= 35:
        return "建议观望"
    return "建议回避"


def suggest_position(
    composite_score: float,
    qqq_above_ma200: bool = True,
    active_long_signal: bool = False,
    max_per_stock: float = 0.08,
) -> float:
    if not active_long_signal or not qqq_above_ma200 or composite_score < 85:
        return 0.0
    scaled = min(1.0, max(0.0, (composite_score - 85) / 15))
    return round(min(max_per_stock, max_per_stock * (0.5 + scaled * 0.5)), 3)


def risk_level_from_score(score: float) -> str:
    if score >= 85:
        return "Low"
    if score >= 65:
        return "Medium"
    if score >= 35:
        return "Elevated"
    return "High"
