# Topaz US

Topaz US is a local FastAPI + React research dashboard for NASDAQ 100 daily liquidity-sweep entry scanning. The first version is long-only, uses free `yfinance` daily data, benchmarks market risk with `QQQ`, and does not use machine learning.

## Strategy

- Universe: static `config/nasdaq100_stocks.json`
- Benchmark: `QQQ`
- Data: daily OHLCV from `yfinance`
- Cache: `data/raw/us_history/*.parquet`
- Holding horizon: several days to several weeks
- Direction: long-only

The strategy name is `Topaz US Liquidity Entry Signals`.

Each stock receives:

- `bullish_sweep`: today low pierces the prior 20-day structure low, then closes back above that structure low with close > open
- `trend_filter`: close is above SMA50
- `volume_filter`: volume is above 20-day average volume by a small confirmation factor
- `volatility_filter`: ATR as a percent of price is neither too quiet nor too wide
- `cooldown_pass`: avoids repeated signals in the same ticker within a short window
- `risk_penalty`: bearish sweep or excessive ATR risk

When a bullish sweep is present, the system calculates:

- `entry_price`: signal close
- `stop_loss`: entry minus ATR x 1.5
- `tp1/tp2/tp3`: 1R / 2R / 3R targets

`composite_score` is normalized to `0-100`. Active buy signals require the sweep and all filters to pass. If `QQQ` is below MA200, the system will not produce active buy signals.

Advice rules:

- Active signal and score `>= 85`: 建议买入
- Active signal below buy threshold or score `>= 65`: 可以关注
- `35-65`: 建议观望
- `< 35`: 建议回避

Single-stock position cap is `8%`.

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

If Yahoo Finance returns rate-limit errors, configure a local proxy in `config/.env`:

```bash
TOPAZ_YF_PROXY=http://127.0.0.1:7897
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
