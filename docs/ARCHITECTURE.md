# Architecture

Topaz US has three layers.

## 1. Domain Package

`topaz_us/` contains market data access, scoring, analysis, reports, and portfolio logic. It is intentionally independent from FastAPI and React where possible.

Key files:

- `topaz_us/data/us_provider.py`: fetches and normalizes yfinance OHLCV data, then caches parquet files.
- `topaz_us/data/regime.py`: classifies QQQ market state and MA200 risk filter.
- `topaz_us/strategy.py`: calculates trend quality, relative strength, momentum, entry quality, risk penalty, advice, and position sizing.
- `topaz_us/analysis/daily.py`: orchestrates a full NASDAQ 100 run and writes latest results.

## 2. API Layer

`backend/` exposes the local FastAPI app.

Important routes:

- `/api/market/overview`: QQQ state and thresholds
- `/api/market/history`: QQQ daily bars
- `/api/analysis/daily`: latest saved analysis
- `/api/analysis/refresh`: background analysis run
- `/api/analysis/report`: text report preview
- `/api/portfolio/analyze`: current portfolio diagnostics

The API reads from and writes to `data/raw/`. That directory is runtime state, not source.

## 3. Frontend

`frontend/` is a React + Vite + Ant Design dashboard. It consumes the API through `frontend/src/api/index.ts`.

The frontend expects scores on a `0-100` scale and advice labels in Chinese:

- `建议买入`
- `可以关注`
- `建议观望`
- `建议回避`

## Data Flow

```text
config/nasdaq100_stocks.json
        |
        v
topaz_us.analysis.daily
        |
        +-- yfinance -> data/raw/us_history/*.parquet
        |
        +-- topaz_us.strategy scoring
        |
        v
data/raw/latest_analysis_results.json
        |
        v
backend FastAPI routes
        |
        v
frontend dashboard
```

## Design Boundaries

- The first version is long-only.
- No machine learning is used.
- No intraday data is used.
- No paid data API is required.
- NASDAQ 100 membership is static and manually maintained.

