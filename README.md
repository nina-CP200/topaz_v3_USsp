# Topaz US

Topaz US is a local FastAPI + React research dashboard for NASDAQ 100 daily trend-quality screening. The first version is long-only, uses free `yfinance` daily data, benchmarks market risk with `QQQ`, and does not use machine learning.

## Strategy

- Universe: static `config/nasdaq100_stocks.json`
- Benchmark: `QQQ`
- Data: daily OHLCV from `yfinance`
- Cache: `data/raw/us_history/*.parquet`
- Holding horizon: several days to several weeks
- Direction: long-only

The strategy name is `Topaz US Trend Quality`.

Each stock receives:

- `trend_score`: price above MA20/MA50/MA200 plus MA20 > MA50 and MA50 > MA200
- `relative_strength_score`: 20-day and 60-day returns versus `QQQ`
- `momentum_score`: 20-day, 60-day, and 120-day cross-sectional momentum
- `entry_score`: constructive pullback near MA20, MA20 reclaim, 20-day breakout, or bullish liquidity sweep
- `risk_penalty`: high 20-day volatility, overextension above MA20, or deep recent drawdown

`composite_score` is normalized to `0-100`.

Advice rules:

- `>= 75`: 建议买入
- `65-75`: 可以关注
- `50-65`: 建议观望
- `< 50`: 建议回避

Single-stock position cap is `8%`. If `QQQ` is below MA200, the system will not produce active buy signals.

## Run

```bash
./setup.sh
./start.sh
```

The app runs at `http://localhost:8000`.

Run analysis from the command line:

```bash
uv run python -m topaz_us.analysis.daily
```

Query the latest results:

```bash
uv run python -m topaz_us.analysis.query --top 10
uv run python -m topaz_us.analysis.query AAPL
```

## Development

For day-to-day development, use two terminals:

```bash
make dev-backend
make dev-frontend
```

Run all local checks:

```bash
make check
```

Project documentation:

- [Development Guide](docs/DEVELOPMENT.md)
- [Architecture](docs/ARCHITECTURE.md)

## API

- `GET /api/market/overview`
- `GET /api/market/history`
- `GET /api/analysis/daily`
- `POST /api/analysis/refresh`
- `GET /api/analysis/report`
- `GET /api/portfolio`
- `PUT /api/portfolio`
- `POST /api/portfolio/analyze`

## Notes

This project intentionally excludes old runtime data, old model files, and old market-specific caches. The NASDAQ 100 universe is static for v1 and should be manually reviewed when index constituents change.

For research only. Not investment advice.
