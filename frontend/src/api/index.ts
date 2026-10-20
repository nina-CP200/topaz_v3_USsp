import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

export interface MarketOverview {
  regime: string
  regime_description: string
  index_price: number
  index_change_pct: number
  index_high: number
  index_low: number
  index_open: number
  index_prev_close: number
  index_name: string
  sentiment_advance_ratio: number
  sentiment_up_count: number
  sentiment_down_count: number
  sentiment_limit_up: number
  sentiment_limit_down: number
  buy_threshold: number
  sell_threshold: number
  position_max: number
  qqq_above_ma200?: boolean
  qqq_ma20?: number
  qqq_ma50?: number
  qqq_ma200?: number
}

export interface KLineItem {
  date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
}

export type SignalDirection = 'bullish' | 'bearish' | 'neutral' | 'unavailable'
export type HorizonKey = 'short' | 'medium' | 'long'
export interface TechnicalSignal {
  direction: SignalDirection
  reason: string
}
export interface HorizonAnalysis {
  label: string
  window: string
  parameters: { williams: number; macd: [number, number, number]; ma: [number, number]; cci: number }
  values: { williams_r: number | null; macd: number | null; macd_signal: number | null; macd_hist: number | null; ma_fast: number | null; ma_slow: number | null; ma_cross: string; cci: number | null }
  signals: Record<'williams' | 'macd' | 'ma' | 'cci', TechnicalSignal>
  summary: TechnicalSignal & { counts: Record<SignalDirection, number> }
}
export interface TechnicalAnalysis {
  version: number
  as_of: string
  bars: number
  horizons: Record<HorizonKey, HorizonAnalysis>
}

export interface MoonAnalysis extends TechnicalSignal {
  version: number
  label: string
  setup: 'none' | 'accumulation' | 'expansion' | 'both'
  triggered: boolean
  market_entry_allowed: boolean | null
  as_of?: string
}

export interface StockResult {
  analysis_date?: string
  moon_analysis?: MoonAnalysis
  technical_analysis?: TechnicalAnalysis
  symbol: string
  name: string
  industry: string
  sector: string
  current_price: number
  change_pct: number
  williams_r?: number | null
  macd?: number | null
  macd_signal?: number | null
  macd_hist?: number | null
  ma20?: number | null
  ma50?: number | null
  ma_cross?: string
  cci?: number | null
  composite_score: number
  signal_status?: string
  bullish_sweep?: boolean
  bearish_sweep?: boolean
  trend_filter?: boolean
  volume_filter?: boolean
  volatility_filter?: boolean
  cooldown_pass?: boolean
  active_long_signal?: boolean
  entry_price?: number | null
  stop_loss?: number | null
  tp1?: number | null
  tp2?: number | null
  tp3?: number | null
  atr_pct?: number
  volume_ratio?: number
  reasons: string[]
  advice: string
  position_pct: number
  rank: number
  risk_level: string
  trend_score?: number
  signal_score?: number
  volume_score?: number
  volatility_score?: number
  relative_strength_score?: number
  momentum_score?: number
  entry_score?: number
  risk_penalty?: number
}

export interface DailyAnalysis {
  date: string
  market_regime: string
  advance_ratio: number
  recommended_position: number
  total_stocks: number
  strategy_name?: string
  benchmark?: string
  market_description?: string
  qqq_above_ma200?: boolean
  market_entry_allowed?: boolean
  market_momentum_state?: string
  market_position_cap?: number
  qqq_ma20?: number | null
  qqq_ma50?: number | null
  qqq_ma200?: number | null
  results: StockResult[]
}

export type DecisionAction = 'enter' | 'add' | 'hold' | 'reduce' | 'exit' | 'unavailable'

export interface DecisionCandidate {
  symbol: string
  name: string
  sector: string
  rank: number
  current_price: number
  change_pct?: number
  composite_score?: number
  target_pct: number
  target_value_usd: number
  entry_price?: number | null
  stop_loss?: number | null
  action: DecisionAction
  reasons: string[]
}

export interface DecisionHolding {
  symbol: string
  name: string
  sector?: string
  shares: number
  cost: number
  current_price?: number
  market_value_usd?: number
  current_pct?: number
  target_pct?: number
  target_value_usd?: number
  delta_value_usd?: number
  pnl_usd?: number
  pnl_pct?: number
  action: DecisionAction
  entry_price?: number | null
  stop_loss?: number | null
  composite_score?: number
  signal_status?: string
  reasons: string[]
}

export interface DailyDecision {
  has_analysis: boolean
  analysis_date: string | null
  strategy_name: string
  capital: { investable_capital_usd: number }
  market: {
    regime?: string
    description?: string
    entry_allowed?: boolean
    qqq_above_ma200?: boolean
    recommended_position_pct?: number
    advance_ratio?: number
    qqq_ma20?: number | null
    qqq_ma50?: number | null
    qqq_ma200?: number | null
  }
  portfolio: {
    current_value_usd: number
    current_pct: number
    target_value_usd: number
    target_pct: number
  }
  candidates: DecisionCandidate[]
  holdings: DecisionHolding[]
  exit_warnings: Array<{ symbol: string; name: string; is_holding: boolean; current_price?: number; reasons: string[] }>
  data_status: { status: string; message: string; stale: boolean }
}

export interface DecisionSettings {
  investable_capital_usd: number
}

export interface HoldingItem {
  symbol: string
  name?: string
  shares: number
  cost: number
}

export interface HoldingAnalysis {
  symbol: string
  name: string
  industry: string
  shares: number
  cost: number
  current_price: number
  market_value: number
  pnl: number
  pnl_pct: number
  change_today: number
  composite_score: number
  advice: string
  reasons: string[]
  rsi: number
  ret_5d: number
  ret_20d: number
}

export interface PortfolioAnalysis {
  holdings: HoldingAnalysis[]
  failed?: { code: string; reason: string }[]
  total_value: number
  total_cost: number
  total_pnl: number
  total_pnl_pct: number
  industry_allocation: Record<string, { value: number; pct: number; pnl: number; stocks: string[] }>
  regime: string
  buy_count: number
  sell_count: number
  loss_count: number
}

export async function getMarketOverview(): Promise<MarketOverview> {
  const r = await api.get('/market/overview')
  return r.data
}

export async function getMarketHistory(days = 60): Promise<{ data: KLineItem[] }> {
  const r = await api.get('/market/history', { params: { days } })
  return r.data
}

export async function getDailyAnalysis(): Promise<DailyAnalysis> {
  const r = await api.get('/analysis/daily')
  return r.data
}

export async function getDailyDecision(): Promise<DailyDecision> {
  const r = await api.get('/decision/daily')
  return r.data
}

export async function getDecisionSettings(): Promise<DecisionSettings> {
  const r = await api.get('/settings/decision')
  return r.data
}

export async function saveDecisionSettings(settings: DecisionSettings): Promise<DecisionSettings> {
  const r = await api.put('/settings/decision', settings)
  return r.data
}

export interface AnalysisReport {
  text: string
  error?: string
}

export async function getAnalysisReport(): Promise<AnalysisReport> {
  const r = await api.get('/analysis/report')
  return r.data
}

export interface SlackConfigItem {
  name: string
  token: string
  channel: string
}

export async function listSlackConfigs(): Promise<{ configs: SlackConfigItem[] }> {
  const r = await api.get('/settings/slack')
  return r.data
}

export async function saveSlackConfigs(configs: SlackConfigItem[]): Promise<{ message: string }> {
  const r = await api.put('/settings/slack', configs)
  return r.data
}

export interface SendSlackResult {
  message: string
  errors?: string[]
}

export async function sendSlackReport(config?: string): Promise<SendSlackResult> {
  const params = config ? { config } : {}
  const r = await api.post('/analysis/send-slack', null, { params })
  return r.data
}

export async function refreshAnalysis(): Promise<{ message: string }> {
  const r = await api.post('/analysis/refresh')
  return r.data
}

export interface AnalysisStatus {
  status: string
  progress: number
  message: string
}

export async function getAnalysisStatus(): Promise<AnalysisStatus> {
  const r = await api.get('/analysis/status')
  return r.data
}

export async function getPortfolio(): Promise<{ holdings: HoldingItem[] }> {
  const r = await api.get('/portfolio')
  return r.data
}

export async function savePortfolio(holdings: HoldingItem[]): Promise<{ message: string; count: number }> {
  const r = await api.put('/portfolio', { holdings })
  return r.data
}

export async function analyzePortfolio(holdings: HoldingItem[]): Promise<PortfolioAnalysis> {
  const r = await api.post('/portfolio/analyze', { holdings })
  return r.data
}


export interface Watchlist {
  symbols: string[]
}

export async function getWatchlist(): Promise<Watchlist> {
  const r = await api.get('/watchlist')
  return r.data
}

export async function addToWatchlist(symbol: string): Promise<Watchlist> {
  const r = await api.put(`/watchlist/${encodeURIComponent(symbol)}`)
  return r.data
}

export async function removeFromWatchlist(symbol: string): Promise<Watchlist> {
  const r = await api.delete(`/watchlist/${encodeURIComponent(symbol)}`)
  return r.data
}

export interface SymbolSearchResult {
  symbol: string
  name: string
  exchange: string
}

export async function searchWatchlistSymbols(query: string): Promise<{ results: SymbolSearchResult[]; warning?: string }> {
  const r = await api.get('/watchlist/search', { params: { q: query }, timeout: 15000 })
  return r.data
}

export async function getWatchlistAnalysis(): Promise<{ results: StockResult[]; failed: string[] }> {
  const r = await api.get('/watchlist/analysis', { timeout: 60000 })
  return r.data
}
