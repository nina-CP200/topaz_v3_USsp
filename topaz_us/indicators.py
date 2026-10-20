"""Daily technical indicators for the stock scanner (no model predictions)."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd


HORIZON_PROFILES = {
    "short": {"label": "短期", "window": "约 1–4 周", "williams": 14, "macd": (6, 13, 5), "ma": (5, 20), "cci": 14},
    "medium": {"label": "中期", "window": "约 1–3 个月", "williams": 14, "macd": (12, 26, 9), "ma": (20, 50), "cci": 20},
    "long": {"label": "长期", "window": "约 3–12 个月", "williams": 60, "macd": (26, 52, 18), "ma": (50, 200), "cci": 60},
}
ANALYSIS_VERSION = 1


def build_indicator_frame(history: pd.DataFrame, *, williams=14, macd=(12, 26, 9), ma=(20, 50), cci=20) -> pd.DataFrame:
    frame = history.sort_values("date").reset_index(drop=True).copy()
    close = frame["close"]
    window_high = frame["high"].rolling(williams).max()
    window_low = frame["low"].rolling(williams).min()
    frame["williams_r"] = -100 * (window_high - close) / (window_high - window_low).replace(0, np.nan)
    frame["macd"] = close.ewm(span=macd[0], adjust=False, min_periods=macd[1]).mean() - close.ewm(span=macd[1], adjust=False, min_periods=macd[1]).mean()
    frame["macd_signal"] = frame["macd"].ewm(span=macd[2], adjust=False, min_periods=macd[2]).mean()
    frame["macd_hist"] = frame["macd"] - frame["macd_signal"]
    # Preserve legacy internal column names for the default medium profile.
    frame["ma20"] = close.rolling(ma[0]).mean()
    frame["ma50"] = close.rolling(ma[1]).mean()
    spread = frame["ma20"] - frame["ma50"]
    valid = spread.notna() & spread.shift(1).notna()
    frame["ma_cross"] = np.select(
        [valid & (spread > 0) & (spread.shift(1) <= 0), valid & (spread < 0) & (spread.shift(1) >= 0), valid & (spread > 0), valid & (spread < 0), valid & (spread == 0)],
        ["golden_cross", "death_cross", "above", "below", "equal"], default="unavailable",
    )
    typical = (frame["high"] + frame["low"] + close) / 3
    mean = typical.rolling(cci).mean()
    deviation = typical.rolling(cci).apply(lambda values: np.abs(values - values.mean()).mean(), raw=True)
    frame["cci"] = (typical - mean) / (0.015 * deviation.replace(0, np.nan))
    return frame


def latest_indicators(history: pd.DataFrame, market_entry_allowed: bool | None = None) -> dict:
    if history.empty:
        return {}
    latest = build_indicator_frame(history).iloc[-1]
    result = {}
    for key in ("williams_r", "macd", "macd_signal", "macd_hist", "ma20", "ma50", "cci"):
        value = float(latest[key])
        result[key] = round(value, 4) if math.isfinite(value) else None
    result["ma_cross"] = latest["ma_cross"]
    result["technical_analysis"] = build_technical_analysis(history)
    result["moon_analysis"] = build_moon_assessment(history, market_entry_allowed)
    return result


def _finite(value) -> bool:
    return value is not None and pd.notna(value) and math.isfinite(float(value))


def _signal(direction: str, reason: str) -> dict:
    return {"direction": direction, "reason": reason}


def interpret_indicators(latest: pd.Series, previous: pd.Series) -> dict:
    """Explicit display heuristics; never a prediction or order instruction."""
    signals = {}
    w, prev_w = latest["williams_r"], previous.get("williams_r")
    if not _finite(w):
        signals["williams"] = _signal("unavailable", "回看窗口不足或最高价与最低价相同。")
    elif _finite(prev_w) and prev_w <= -80 < w:
        signals["williams"] = _signal("bullish", "当日向上离开 −80 超卖区，出现反弹触发。")
    elif _finite(prev_w) and prev_w >= -20 > w:
        signals["williams"] = _signal("bearish", "当日向下离开 −20 超买区，出现转弱触发。")
    else:
        direction = "bullish" if w > -50 else "bearish" if w < -50 else "neutral"
        reason = "处于区间上半部，价格位置偏强。" if w > -50 else "处于区间下半部，价格位置偏弱。" if w < -50 else "位于 −50 中线，方向中性。"
        if w >= -20:
            reason += "仍在超买区，超买本身不等于看跌。"
        elif w <= -80:
            reason += "仍在超卖区，尚未确认向上离开。"
        signals["williams"] = _signal(direction, reason)

    hist, prev_hist = latest["macd_hist"], previous.get("macd_hist")
    if not _finite(hist):
        signals["macd"] = _signal("unavailable", "MACD 或信号线预热数据不足。")
    else:
        direction = "bullish" if hist > 0 else "bearish" if hist < 0 else "neutral"
        reason = "DIF 高于 DEA，动量偏多。" if hist > 0 else "DIF 低于 DEA，动量偏空。" if hist < 0 else "DIF 与 DEA 重合，方向中性。"
        if _finite(prev_hist) and prev_hist <= 0 < hist:
            reason = "当日 DIF 上穿 DEA，出现 MACD 金叉。"
        elif _finite(prev_hist) and prev_hist >= 0 > hist:
            reason = "当日 DIF 下穿 DEA，出现 MACD 死叉。"
        reason += "DIF 在零轴上方。" if latest["macd"] > 0 else "DIF 在零轴下方。" if latest["macd"] < 0 else "DIF 位于零轴。"
        signals["macd"] = _signal(direction, reason)

    cross = latest["ma_cross"]
    directions = {"golden_cross": "bullish", "above": "bullish", "death_cross": "bearish", "below": "bearish", "equal": "neutral"}
    reasons = {"golden_cross": "当日较快 SMA 上穿较慢 SMA，出现均线金叉。", "above": "较快 SMA 高于较慢 SMA，趋势偏多；当日无新交叉。", "death_cross": "当日较快 SMA 下穿较慢 SMA，出现均线死叉。", "below": "较快 SMA 低于较慢 SMA，趋势偏空；当日无新交叉。", "equal": "两条 SMA 相等，方向中性。"}
    signals["ma"] = _signal(directions.get(cross, "unavailable"), reasons.get(cross, "均线或前一交易日数据不足。"))

    cci = latest["cci"]
    if not _finite(cci):
        signals["cci"] = _signal("unavailable", "CCI 窗口不足或平均偏差为零。")
    elif cci > 100:
        signals["cci"] = _signal("bullish", "CCI 高于 +100，按趋势规则解读为强势动量。")
    elif cci < -100:
        signals["cci"] = _signal("bearish", "CCI 低于 −100，按趋势规则解读为弱势动量。")
    else:
        signals["cci"] = _signal("neutral", "CCI 位于 −100 至 +100，尚无强趋势确认。")
    return signals


def summarize_signals(signals: dict) -> dict:
    counts = {direction: sum(item["direction"] == direction for item in signals.values()) for direction in ("bullish", "bearish", "neutral", "unavailable")}
    if counts["unavailable"]:
        return {"direction": "unavailable", "reason": f"{4 - counts['unavailable']}/4 项可用，等待完整数据再给出周期结论。", "counts": counts}
    direction = "bullish" if counts["bullish"] >= 3 else "bearish" if counts["bearish"] >= 3 else "neutral"
    reason = f"{counts['bullish']} 项看涨、{counts['bearish']} 项看跌、{counts['neutral']} 项中性。"
    reason += "至少三项同向。" if direction != "neutral" else "未达到三项同向，信号分歧或方向不明。"
    return {"direction": direction, "reason": reason, "counts": counts}


def build_technical_analysis(history: pd.DataFrame) -> dict:
    horizons = {}
    for key, profile in HORIZON_PROFILES.items():
        frame = build_indicator_frame(history, **{field: profile[field] for field in ("williams", "macd", "ma", "cci")})
        latest = frame.iloc[-1]
        previous = frame.iloc[-2] if len(frame) > 1 else pd.Series(dtype=object)
        values = {}
        for field, column in (("williams_r", "williams_r"), ("macd", "macd"), ("macd_signal", "macd_signal"), ("macd_hist", "macd_hist"), ("ma_fast", "ma20"), ("ma_slow", "ma50"), ("cci", "cci")):
            values[field] = round(float(latest[column]), 4) if _finite(latest[column]) else None
        values["ma_cross"] = latest["ma_cross"]
        signals = interpret_indicators(latest, previous)
        horizons[key] = {"label": profile["label"], "window": profile["window"], "parameters": {field: profile[field] for field in ("williams", "macd", "ma", "cci")}, "values": values, "signals": signals, "summary": summarize_signals(signals)}
    return {"version": ANALYSIS_VERSION, "as_of": str(pd.Timestamp(frame.iloc[-1]["date"]).date()), "bars": len(frame), "horizons": horizons}


MOON_ANALYSIS_VERSION = 1


def build_moon_assessment(history: pd.DataFrame, market_entry_allowed: bool | None = None) -> dict:
    """Explain the existing daily Moon rules separately from horizon voting."""
    from topaz_us.strategy import SLOW_TMA_LENGTH, build_signal_frame

    base = {"version": MOON_ANALYSIS_VERSION, "market_entry_allowed": market_entry_allowed}
    if history.empty or len(history) < SLOW_TMA_LENGTH + 2:
        return {**base, **_signal("unavailable", "日线历史不足，尚不能完整判断 Moon 趋势与形态。"), "label": "数据不足", "setup": "none", "triggered": False}
    latest = build_signal_frame(history).iloc[-1]
    accumulation = bool(latest["accumulation_entry"])
    expansion = bool(latest["expansion_add_entry"])
    triggered = bool(latest["moon_buy_signal"])
    setup = "both" if accumulation and expansion else "accumulation" if accumulation else "expansion" if expansion else "none"
    base.update({"setup": setup, "triggered": triggered, "as_of": str(pd.Timestamp(latest["date"]).date())})
    if bool(latest["bearish_sweep"]):
        return {**base, **_signal("bearish", "价格冲破前期高点后回落，并收出阴线；流动性扫盘退出预警优先于入场形态。"), "label": "退出预警"}
    if bool(latest["below_structure"]):
        return {**base, **_signal("bearish", "收盘价跌破前期结构低点，Moon 吸筹结构转弱。"), "label": "结构转弱"}
    if accumulation or expansion:
        shape = "回调吸筹与放量突破同时成立" if setup == "both" else "价格回到吸筹区，修复动能与压力条件通过" if accumulation else "价格放量突破前期高点，趋势排列与剩余动能条件通过"
        if market_entry_allowed is False:
            return {**base, **_signal("neutral", shape + "；QQQ 未通过市场门槛，暂不构成有效建仓信号。"), "label": "等待市场"}
        label = "吸筹与突破" if setup == "both" else "吸筹" if accumulation else "突破"
        reason = shape + ("；当日首次触发该轮形态。" if triggered else "；形态继续成立，当日不是新的首次触发。")
        if market_entry_allowed is None:
            reason += "尚未提供市场门槛状态，执行前需核对。"
        return {**base, **_signal("bullish", reason), "label": label + ("触发" if triggered else "延续")}
    if bool(latest["bull_order"]):
        return {**base, **_signal("neutral", "趋势排列偏多，但回调吸筹与放量突破均未满足，继续等待形态。"), "label": "等待形态"}
    return {**base, **_signal("neutral", "当前没有满足 Moon 条件的回调吸筹或放量突破形态。"), "label": "暂无形态"}
