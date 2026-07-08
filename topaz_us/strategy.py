from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import numpy as np
import pandas as pd


@dataclass
class ScoreBreakdown:
    trend_score: float
    relative_strength_score: float
    momentum_score: float
    entry_score: float
    risk_penalty: float
    raw_score: float
    composite_score: float
    reasons: List[str]


def _pct_rank(values: pd.Series) -> pd.Series:
    return values.rank(pct=True).fillna(0.0)


def _safe_return(close: pd.Series, window: int) -> float:
    if len(close) <= window or close.iloc[-window] == 0:
        return 0.0
    return float(close.iloc[-1] / close.iloc[-window] - 1)


def build_cross_section_features(
    histories: Dict[str, pd.DataFrame],
    benchmark_history: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    qqq_close = benchmark_history["close"] if benchmark_history is not None and not benchmark_history.empty else pd.Series(dtype=float)
    qqq_ret_20 = _safe_return(qqq_close, 20)
    qqq_ret_60 = _safe_return(qqq_close, 60)

    for symbol, history in histories.items():
        if history is None or len(history) < 60:
            continue
        close = history["close"]
        volume = history.get("volume", pd.Series([0] * len(history)))
        last = history.iloc[-1]
        prev_close = close.iloc[-2] if len(close) >= 2 else close.iloc[-1]

        ma20 = close.rolling(20).mean().iloc[-1]
        ma50 = close.rolling(50).mean().iloc[-1]
        ma200 = close.rolling(200).mean().iloc[-1] if len(close) >= 200 else close.rolling(60).mean().iloc[-1]
        ret_20 = _safe_return(close, 20)
        ret_60 = _safe_return(close, 60)
        ret_120 = _safe_return(close, 120)
        vol_20 = close.pct_change().rolling(20).std().iloc[-1] * np.sqrt(252)
        drawdown_60 = close.iloc[-1] / close.tail(60).max() - 1
        distance_ma20 = close.iloc[-1] / ma20 - 1 if ma20 else 0.0
        high_20_prev = close.shift(1).rolling(20).max().iloc[-1]
        low_20_prev = history["low"].shift(1).rolling(20).min().iloc[-1] if "low" in history else np.nan
        avg_volume_20 = volume.rolling(20).mean().iloc[-1] if len(volume) >= 20 else 0

        rows.append({
            "symbol": symbol,
            "current_price": float(close.iloc[-1]),
            "change_pct": float((close.iloc[-1] / prev_close - 1) * 100) if prev_close else 0.0,
            "ma20": float(ma20),
            "ma50": float(ma50),
            "ma200": float(ma200),
            "ret_20": ret_20,
            "ret_60": ret_60,
            "ret_120": ret_120,
            "rel_20": ret_20 - qqq_ret_20,
            "rel_60": ret_60 - qqq_ret_60,
            "vol_20": float(vol_20) if pd.notna(vol_20) else 0.0,
            "drawdown_60": float(drawdown_60),
            "distance_ma20": float(distance_ma20),
            "breakout_20": bool(close.iloc[-1] > high_20_prev) if pd.notna(high_20_prev) else False,
            "near_ma20": bool(abs(distance_ma20) <= 0.025),
            "reclaim_ma20": bool(len(close) >= 2 and close.iloc[-2] < ma20 and close.iloc[-1] > ma20),
            "liquidity_sweep": bool(
                pd.notna(low_20_prev)
                and "low" in history
                and history["low"].iloc[-1] < low_20_prev
                and close.iloc[-1] > prev_close
                and avg_volume_20
                and volume.iloc[-1] > avg_volume_20 * 1.15
            ),
        })

    features = pd.DataFrame(rows)
    if features.empty:
        return features

    features["rs_rank"] = (_pct_rank(features["rel_20"]) + _pct_rank(features["rel_60"])) / 2
    features["momentum_rank"] = (
        _pct_rank(features["ret_20"]) * 0.35
        + _pct_rank(features["ret_60"]) * 0.40
        + _pct_rank(features["ret_120"]) * 0.25
    )
    return features


def score_stock(row: pd.Series) -> ScoreBreakdown:
    reasons: List[str] = []
    price = row["current_price"]

    trend_score = 0.0
    if price > row["ma20"]:
        trend_score += 8
        reasons.append("Price above MA20")
    if price > row["ma50"]:
        trend_score += 7
        reasons.append("Price above MA50")
    if price > row["ma200"]:
        trend_score += 8
        reasons.append("Price above MA200")
    if row["ma20"] > row["ma50"]:
        trend_score += 5
        reasons.append("MA20 above MA50")
    if row["ma50"] > row["ma200"]:
        trend_score += 4
        reasons.append("MA50 above MA200")

    relative_strength_score = float(row.get("rs_rank", 0.0)) * 24
    momentum_score = float(row.get("momentum_rank", 0.0)) * 24

    entry_score = 0.0
    if row.get("near_ma20") and row.get("ret_20", 0) > 0:
        entry_score += 5
        reasons.append("Constructive pullback near MA20")
    if row.get("reclaim_ma20"):
        entry_score += 6
        reasons.append("Reclaimed MA20")
    if row.get("breakout_20"):
        entry_score += 7
        reasons.append("20-day breakout")
    if row.get("liquidity_sweep"):
        entry_score += 6
        reasons.append("Bullish liquidity sweep")
    entry_score = min(entry_score, 16)

    risk_penalty = 0.0
    if row.get("vol_20", 0) > 0.60:
        risk_penalty += 10
        reasons.append("High 20-day volatility")
    elif row.get("vol_20", 0) > 0.45:
        risk_penalty += 5
        reasons.append("Elevated 20-day volatility")
    if row.get("distance_ma20", 0) > 0.12:
        risk_penalty += 8
        reasons.append("Extended above MA20")
    elif row.get("distance_ma20", 0) > 0.08:
        risk_penalty += 4
        reasons.append("Slightly extended above MA20")
    if row.get("drawdown_60", 0) < -0.18:
        risk_penalty += 8
        reasons.append("Deep recent drawdown")
    elif row.get("drawdown_60", 0) < -0.10:
        risk_penalty += 4
        reasons.append("Recent drawdown pressure")

    raw_score = trend_score + relative_strength_score + momentum_score + entry_score - risk_penalty
    composite_score = max(0.0, min(100.0, raw_score))
    if not reasons:
        reasons.append("Mixed trend quality")

    return ScoreBreakdown(
        trend_score=round(trend_score, 2),
        relative_strength_score=round(relative_strength_score, 2),
        momentum_score=round(momentum_score, 2),
        entry_score=round(entry_score, 2),
        risk_penalty=round(risk_penalty, 2),
        raw_score=round(raw_score, 2),
        composite_score=round(composite_score, 2),
        reasons=reasons[:6],
    )


def get_advice_from_score(composite_score: float, qqq_above_ma200: bool = True) -> str:
    if not qqq_above_ma200 and composite_score >= 75:
        return "可以关注"
    if composite_score >= 75:
        return "建议买入"
    if composite_score >= 65:
        return "可以关注"
    if composite_score >= 50:
        return "建议观望"
    return "建议回避"


def suggest_position(composite_score: float, qqq_above_ma200: bool = True, max_per_stock: float = 0.08) -> float:
    if not qqq_above_ma200 or composite_score < 75:
        return 0.0
    scaled = (composite_score - 75) / 25
    return round(min(max_per_stock, max_per_stock * (0.5 + scaled * 0.5)), 3)


def risk_level_from_score(score: float) -> str:
    if score >= 75:
        return "Low"
    if score >= 65:
        return "Medium"
    if score >= 50:
        return "Elevated"
    return "High"
