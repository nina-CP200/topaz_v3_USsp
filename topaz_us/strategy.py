from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import numpy as np
import pandas as pd


# Moon Accumulation entry framework.  Liquidity sweeps remain exit/risk signals.
LOOKBACK = 20
SMA_LENGTH = 50
ATR_LENGTH = 14
ATR_MULTIPLIER = 1.5
COOLDOWN_DAYS = 5
VOLUME_LENGTH = 20
MIN_ATR_PCT = 0.012
MAX_ATR_PCT = 0.085
VOLUME_MULTIPLIER = 1.10
FAST_TMA_LENGTH = 21
MEDIUM_TMA_LENGTH = 55
SLOW_TMA_LENGTH = 144
STRUCTURE_LOOKBACK = 50
EXPANSION_LOOKBACK = 30
VOLUME_BASELINE_LENGTH = 50


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


def _tma(source: pd.Series, length: int) -> pd.Series:
    first_length = int(np.ceil(length / 2.0))
    second_length = int(np.floor(length / 2.0) + 1)
    return source.rolling(first_length).mean().rolling(second_length).mean()


def _dmi(history: pd.DataFrame, length: int = 14, adx_smoothing: int = 14) -> tuple[pd.Series, pd.Series, pd.Series]:
    up_move = history["high"].diff()
    down_move = -history["low"].diff()
    plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=history.index)
    minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=history.index)
    atr = _atr(history, length)
    plus_di = 100 * plus_dm.ewm(alpha=1 / length, adjust=False, min_periods=length).mean() / atr
    minus_di = 100 * minus_dm.ewm(alpha=1 / length, adjust=False, min_periods=length).mean() / atr
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = dx.ewm(alpha=1 / adx_smoothing, adjust=False, min_periods=adx_smoothing).mean()
    return plus_di, minus_di, adx


def build_signal_frame(history: pd.DataFrame) -> pd.DataFrame:
    """Build the causal daily indicators shared by analysis and backtests."""
    frame = history.copy().sort_values("date").reset_index(drop=True)
    close = frame["close"]
    atr = _atr(frame)
    fast_tma = _tma(close, FAST_TMA_LENGTH)
    medium_tma = _tma(close, MEDIUM_TMA_LENGTH)
    slow_tma = _tma(close, SLOW_TMA_LENGTH)
    macd_fast = close.ewm(span=12, adjust=False, min_periods=26).mean()
    macd_slow = close.ewm(span=26, adjust=False, min_periods=26).mean()
    macd_line = macd_fast - macd_slow
    macd_signal = macd_line.ewm(span=9, adjust=False, min_periods=9).mean()
    di_plus, di_minus, adx = _dmi(frame)

    frame["atr"] = atr
    frame["ret_20"] = close.pct_change(20)
    frame["fast_tma"] = fast_tma
    frame["medium_tma"] = medium_tma
    frame["slow_tma"] = slow_tma
    frame["rsi"] = _rsi(close)
    frame["macd_hist"] = macd_line - macd_signal
    frame["di_plus"] = di_plus
    frame["di_minus"] = di_minus
    frame["adx"] = adx
    frame["volume_ratio"] = frame["volume"] / frame["volume"].rolling(VOLUME_BASELINE_LENGTH).mean()
    frame["structure_low"] = frame["low"].rolling(STRUCTURE_LOOKBACK).min()
    frame["liquidity_structure_high"] = frame["high"].shift(1).rolling(LOOKBACK).max()
    frame["expansion_trigger"] = frame["high"].shift(1).rolling(EXPANSION_LOOKBACK).max()
    frame["fast_slope"] = fast_tma.diff()
    frame["medium_slope"] = medium_tma.diff()
    frame["bull_order"] = (fast_tma > medium_tma) & (medium_tma > slow_tma)
    frame["reorienting"] = (frame["fast_slope"] > 0) & (frame["medium_slope"] >= 0) & (close > slow_tma)
    frame["below_structure"] = close < frame["structure_low"].shift(1)

    dist_fast = (close - fast_tma) / atr.replace(0, np.nan)
    frame["repair_pressure"] = (
        np.where(dist_fast > 0, dist_fast * 13.0, 8.0)
        + np.where(frame["rsi"] > 70, 18.0, 0.0)
        + np.where(frame["fast_slope"] < 0, 15.0, 0.0)
        + np.where(close < fast_tma, 10.0, 0.0)
    ).clip(0.0, 100.0)
    frame["repair_progress"] = (
        np.where(close > frame["structure_low"], 45.0, 15.0)
        + np.where(frame["fast_slope"] > 0, 20.0, 0.0)
        + np.where(frame["medium_slope"] >= 0, 15.0, 0.0)
        + np.where(frame["macd_hist"] > frame["macd_hist"].shift(1), 10.0, 0.0)
        + np.where(frame["di_plus"] >= frame["di_minus"] * 0.75, 10.0, 0.0)
    ).clip(0.0, 100.0)
    frame["energy_left"] = (100.0 - frame["repair_pressure"] + np.where(frame["bull_order"], 15.0, 0.0)).clip(0.0, 100.0)
    frame["accumulation_low"] = np.maximum(frame["structure_low"], close - atr * 1.10)
    frame["accumulation_high"] = np.minimum(fast_tma, close + atr * 0.45)
    frame["accumulation_entry"] = (
        (close >= frame["accumulation_low"])
        & (close <= frame["accumulation_high"])
        & (frame["repair_progress"] > 60)
        & (frame["repair_pressure"] < 75)
        & ~frame["below_structure"]
    )
    frame["expansion_add_entry"] = (
        (close > frame["expansion_trigger"])
        & frame["bull_order"]
        & (frame["energy_left"] > 35)
        & (frame["volume_ratio"] > VOLUME_MULTIPLIER)
    )
    frame["moon_setup_active"] = frame["accumulation_entry"] | frame["expansion_add_entry"]
    # A setup can remain valid over several bars. Enter once at its onset,
    # rather than repeatedly re-entering the same pullback every day.
    previous_setup = frame["moon_setup_active"].shift(1, fill_value=False).astype(bool)
    frame["moon_buy_signal"] = frame["moon_setup_active"] & ~previous_setup
    frame["bearish_sweep"] = (
        (frame["high"] > frame["liquidity_structure_high"])
        & (close < frame["liquidity_structure_high"])
        & (close < frame["open"])
    )
    return frame


def _rsi(close: pd.Series, length: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / length, adjust=False, min_periods=length).mean()
    loss = -delta.clip(upper=0).ewm(alpha=1 / length, adjust=False, min_periods=length).mean()
    relative_strength = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + relative_strength))


def build_cross_section_features(
    histories: Dict[str, pd.DataFrame],
    benchmark_history: pd.DataFrame,
) -> pd.DataFrame:
    rows = []

    for symbol, history in histories.items():
        if history is None or len(history) < SLOW_TMA_LENGTH + 2:
            continue
        signals = build_signal_frame(history)
        latest = signals.iloc[-1]
        previous = signals.iloc[-2]
        latest_close = float(latest["close"])
        atr_value = float(latest["atr"]) if pd.notna(latest["atr"]) else 0.0
        atr_pct = atr_value / latest_close if latest_close and atr_value else 0.0
        moon_buy_signal = bool(latest["moon_buy_signal"])

        entry_price = latest_close if moon_buy_signal else None
        stop_loss = entry_price - atr_value * ATR_MULTIPLIER if entry_price else None
        rows.append({
            "symbol": symbol,
            "current_price": latest_close,
            "change_pct": float((latest_close / previous["close"] - 1) * 100) if previous["close"] else 0.0,
            "ma20": float(signals["close"].rolling(20).mean().iloc[-1]),
            "ma50": float(signals["close"].rolling(SMA_LENGTH).mean().iloc[-1]),
            "ma200": float(signals["close"].rolling(200).mean().iloc[-1]) if len(signals) >= 200 else float(signals["close"].rolling(60).mean().iloc[-1]),
            "ret_20": _safe_return(signals["close"], 20),
            "structure_low": float(latest["structure_low"]) if pd.notna(latest["structure_low"]) else None,
            "structure_high": float(latest["liquidity_structure_high"]) if pd.notna(latest["liquidity_structure_high"]) else None,
            "atr": atr_value,
            "atr_pct": atr_pct,
            "volume_ratio": float(latest["volume_ratio"]) if pd.notna(latest["volume_ratio"]) else 0.0,
            "bullish_sweep": False,
            "bearish_sweep": bool(latest["bearish_sweep"]),
            "liquidity_exit_signal": bool(latest["bearish_sweep"]),
            "trend_filter": bool(latest["bull_order"]),
            "volatility_filter": bool(MIN_ATR_PCT <= atr_pct <= MAX_ATR_PCT),
            "volume_filter": bool(latest["volume_ratio"] >= VOLUME_MULTIPLIER),
            "cooldown_pass": True,
            "accumulation_entry": bool(latest["accumulation_entry"]),
            "expansion_add_entry": bool(latest["expansion_add_entry"]),
            "moon_setup_active": bool(latest["moon_setup_active"]),
            "moon_buy_signal": moon_buy_signal,
            "active_long_signal": moon_buy_signal,
            "repair_pressure": float(latest["repair_pressure"]),
            "repair_progress": float(latest["repair_progress"]),
            "entry_price": entry_price,
            "stop_loss": float(stop_loss) if stop_loss and stop_loss > 0 else None,
            "tp1": None,
            "tp2": None,
            "tp3": None,
        })

    return pd.DataFrame(rows)


def score_stock(row: pd.Series) -> ScoreBreakdown:
    reasons: List[str] = []
    accumulation_entry = bool(row.get("accumulation_entry", False))
    expansion_add_entry = bool(row.get("expansion_add_entry", False))
    trend_filter = bool(row.get("trend_filter", False))
    volume_filter = bool(row.get("volume_filter", False))
    volatility_filter = bool(row.get("volatility_filter", False))

    signal_score = 0.0
    if accumulation_entry and bool(row.get("moon_buy_signal", False)):
        signal_score += 60.0
        reasons.append("Accumulation-zone entry")
    if expansion_add_entry and bool(row.get("moon_buy_signal", False)):
        signal_score = max(signal_score, 55.0)
        reasons.append("Volume-backed expansion breakout")
    if not signal_score:
        reasons.append("No Moon entry setup today")

    trend_score = 15.0 if trend_filter else 0.0
    if trend_filter:
        reasons.append("21/55/144 TMA bullish order")

    volume_score = 10.0 if volume_filter else 5.0 if row.get("volume_ratio", 0) >= 1 else 0.0
    if volume_filter:
        reasons.append("Volume confirmation")

    volatility_score = 10.0 if volatility_filter else 0.0
    if volatility_filter:
        reasons.append("ATR range passed")

    risk_penalty = 0.0
    if bool(row.get("bearish_sweep", False)):
        risk_penalty += 25.0
        reasons.append("Bearish liquidity exit warning")
    if row.get("repair_pressure", 0.0) >= 80:
        risk_penalty += 15.0
        reasons.append("Extension pressure is elevated")
    if row.get("atr_pct", 0.0) > MAX_ATR_PCT:
        risk_penalty += 10.0
        reasons.append("ATR too wide")

    raw_score = signal_score + trend_score + volume_score + volatility_score - risk_penalty
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
