# Architecture

Topaz US has three layers.

## 1. Domain Package

`topaz_us/` contains market data access, scoring, analysis, reports, and portfolio logic. It is intentionally independent from FastAPI and React where possible.

Key files:

- `topaz_us/data/us_provider.py`: fetches and normalizes yfinance OHLCV data, then caches parquet files.
- `topaz_us/data/regime.py`: classifies QQQ market state and MA200 risk filter.
- `topaz_us/strategy.py`: scans Moon accumulation pullbacks and expansion breakouts, then applies liquidity-sweep exit warnings, ATR protection, advice, and position sizing.
- `topaz_us/indicators.py`: calculates Williams %R (14), MACD (12/26/9), SMA20/SMA50 crossover states, and CCI (20) for display.
- `topaz_us/analysis/daily.py`: orchestrates a full NASDAQ 100 run, combines scores with display indicators, and writes latest results.

## 2. API Layer

`backend/` exposes the local FastAPI app.

Important routes:

- `/api/market/overview`: QQQ state and thresholds
- `/api/market/history`: QQQ daily bars
- `/api/analysis/daily`: latest saved analysis, with local-cache indicator supplementation for old records
- `/api/analysis/status`: background refresh status
- `/api/analysis/refresh`: background analysis run
- `/api/analysis/report`: text report preview
- `/api/decision/daily`: market gate, candidate allocations, and holding actions
- `/api/portfolio/analyze`: current portfolio diagnostics
- `/api/settings/decision`: investable capital settings

The API reads from and writes to `data/raw/`. That directory is runtime state, not source.

## 3. Frontend

`frontend/` is a React + Vite + Ant Design dashboard. It consumes the API through `frontend/src/api/index.ts`.

The frontend expects scores on a `0-100` scale and advice labels in Chinese:

- `建议买入`
- `可以关注`
- `建议观望`
- `建议回避`

The `/stocks` table and detail drawer display the four technical indicators, their bullish/bearish/neutral interpretations and reasons, and separate short/medium/long daily-bar analyses, with no ML prediction or confidence controls. The table defaults to the full universe and shows the saved analysis timestamp. Strategy status filters and rank remain based on Moon scoring. The decision and portfolio pages retain their existing strategy responsibilities. The strategy research page, navigation, API client, and backend route have been removed. Legacy `/research` and `/about` URLs redirect to the scanner; offline backtest code and saved files are retained.

The API retains nullable numeric fields for calculation and compatibility, but the scanner table and drawer display conclusions and explanatory text. Missing assessments show `数据不足`. A separate `moon_analysis` assessment names the original daily Moon setup or risk state, applies the QQQ gate, and remains outside the four-indicator vote. See [Indicator Reference](INDICATORS.md) for the full contract.

## Data Flow

```text
config/nasdaq100_stocks.json
        |
        v
topaz_us.analysis.daily
        |
        +-- yfinance -> data/raw/us_history/*.parquet
        |
        +-- topaz_us.strategy Moon entry / liquidity exit scoring
        |
        +-- topaz_us.indicators four scanner indicators
        |
        v
data/raw/latest_analysis_results.json
        |
        v
backend FastAPI routes
        +-- old records: local cached bars <= original analysis date
        |
        v
frontend dashboard
```

## Snapshot Compatibility

New analysis runs persist the four indicators and versioned three-horizon interpretations alongside existing strategy fields. `HORIZON_PROFILES` controls the daily-bar parameters; each horizon includes values, four explained signals, and a summary requiring at least three agreeing indicators. Incomplete coverage yields an unavailable summary. `as_of` reports the actual latest eligible bar date. The original top-level numeric fields remain the medium-profile values. For old snapshots lacking the current `technical_analysis.version` or `moon_analysis.version`, or with a changed saved Moon gate state, `GET /api/analysis/daily` reads each symbol's local parquet history, filters out bars after the snapshot's date, and computes the latest available indicator values. This operation enriches the response only: it does not update the snapshot file, change its timestamp, or fetch quotes. If history is absent or no eligible bars exist, the UI shows unavailable values.

The cutoff uses calendar dates because the input is daily OHLCV. If the cache ends before the snapshot date, the calculation uses its latest eligible bar. Cache history revisions can affect recomputed values; supplementation is not a permanently versioned historical record. The report route and decision snapshot continue to consume strategy data rather than this display-only enrichment.

Some older backend payloads still include compatibility fields such as `probability`, `predicted_return`, and `model_confidence`. They do not represent ML inference; the scanner's TypeScript contract and visible indicator view do not use them.

## Design Boundaries

- The first version is long-only.
- No machine learning is used.
- No intraday data is used.
- No paid data API is required.
- NASDAQ 100 membership is static and manually maintained.
