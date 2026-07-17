from __future__ import annotations
from pydantic import BaseModel
from typing import Optional


class HoldingItem(BaseModel):
    symbol: str
    name: str = ""
    shares: int
    cost: float


class PortfolioSave(BaseModel):
    holdings: list[HoldingItem]


class PortfolioAnalyzeRequest(BaseModel):
    holdings: list[HoldingItem]


class StockResultItem(BaseModel):
    symbol: str
    name: str
    industry: str
    current_price: float
    change_pct: float
    probability: float
    composite_score: float
    reasons: list[str]
    advice: str
    position_pct: float
    model_confidence: float
    rank: int
    predicted_return: float
    risk_level: str
    signal_status: str = "No Signal"
    active_long_signal: bool = False
    bearish_sweep: bool = False
    entry_price: float | None = None
    stop_loss: float | None = None
    trend_score: float | None = None
    signal_score: float | None = None
    volume_score: float | None = None
    volatility_score: float | None = None
    relative_strength_score: float | None = None
    momentum_score: float | None = None
    entry_score: float | None = None
    risk_penalty: float | None = None


class DailyAnalysisResult(BaseModel):
    date: str
    market_regime: str
    model_confidence: float
    advance_ratio: float
    recommended_position: float
    total_stocks: int
    results: list[StockResultItem]
    market_description: str = ""
    qqq_above_ma200: bool = False
    market_entry_allowed: bool = False
    market_momentum_state: str = "normal"
    market_position_cap: float = 1.0
    qqq_ma20: float | None = None
    qqq_ma50: float | None = None
    qqq_ma200: float | None = None


class MarketOverview(BaseModel):
    regime: str
    regime_description: str
    index_price: float
    index_change_pct: float
    index_high: float
    index_low: float
    index_open: float
    index_prev_close: float
    index_name: str
    sentiment_advance_ratio: float
    sentiment_up_count: int
    sentiment_down_count: int
    sentiment_limit_up: int
    sentiment_limit_down: int
    buy_threshold: float
    sell_threshold: float
    position_max: float


class HoldingAnalysis(BaseModel):
    symbol: str
    name: str
    industry: str
    shares: int
    cost: float
    current_price: float
    market_value: float
    pnl: float
    pnl_pct: float
    change_today: float
    composite_score: float
    advice: str
    reasons: list[str]
    rsi: float
    ret_5d: float
    ret_20d: float


class PortfolioAnalysisResult(BaseModel):
    holdings: list[HoldingAnalysis]
    total_value: float
    total_cost: float
    total_pnl: float
    total_pnl_pct: float
    industry_allocation: dict
    regime: str
    buy_count: int
    sell_count: int
    loss_count: int
