# Development Guide

This repository is arranged so the backend, strategy code, frontend, configuration, and runtime data stay separate.

## Layout

```text
topaz_us/                 Python domain package
  analysis/               Daily analysis and result query CLI
  data/                   yfinance provider, cache loading, QQQ regime helpers
  reports/                Slack report formatting
  utils/                  Small shared utilities
  portfolio.py            Portfolio analysis
  strategy.py             Topaz US Trend Quality scoring
backend/                  FastAPI app and routers
frontend/                 React + Vite dashboard
config/                   Static NASDAQ 100 universe
tests/                    Unit tests with offline fixtures
docs/                     Human-facing project documentation
scripts/                  Developer convenience scripts
data/                     Runtime cache and analysis output, ignored by Git
```

## First Setup

```bash
./setup.sh
```

This creates `.venv` when needed, installs Python dependencies with `uv`, and installs frontend dependencies with `npm install`.

## Development Servers

Run the backend and frontend in two terminals:

```bash
make dev-backend
make dev-frontend
```

Backend:

- API: `http://127.0.0.1:8000/api`
- Health: `http://127.0.0.1:8000/api/health`

Frontend:

- Vite dev server: `http://127.0.0.1:5173`
- API requests proxy to the FastAPI backend through `frontend/vite.config.ts`.

For a production-like local run:

```bash
NO_OPEN=1 ./start.sh
```

## Common Commands

```bash
make check      # Python compile, unit tests, frontend build
make analyze    # Run NASDAQ 100 analysis and write data/raw/latest_analysis_results.json
./portfolio.sh  # Analyze saved portfolio data
```

The analysis command depends on free Yahoo/yfinance access. If Yahoo rate-limits the machine, retry later, use existing cached parquet files under `data/raw/us_history`, or configure an explicit proxy:

```bash
cp config/.env.example config/.env
# edit config/.env
TOPAZ_YF_PROXY=http://127.0.0.1:7897
```

`TOPAZ_YF_PROXY` is passed to `yfinance` with `yf.set_config(proxy=...)`. The app also respects `YFINANCE_PROXY`, `YF_PROXY`, `HTTPS_PROXY`, `HTTP_PROXY`, and `ALL_PROXY`.

## Adding Strategy Work

Most scoring changes belong in `topaz_us/strategy.py`.

Keep these contracts stable unless the frontend and API schemas are updated together:

- `symbol`
- `name`
- `sector`
- `current_price`
- `change_pct`
- `composite_score`
- `advice`
- `reasons`
- `position_pct`
- `rank`

Offline tests should use fixtures or generated DataFrames. Do not make unit tests depend on live yfinance calls.

## Updating The Universe

The first version uses a static file:

```text
config/nasdaq100_stocks.json
```

Update it manually when NASDAQ 100 constituents change. Keep each item shaped as:

```json
{"code": "AAPL", "name": "Apple", "sector": "Information Technology"}
```

## Runtime Files

These are intentionally ignored by Git:

- `data/raw/us_history/*.parquet`
- `data/raw/latest_analysis_results.json`
- `data/raw/analysis_status.json`
- `data/raw/portfolio.json`
- `data/raw/slack_configs.json`
- `frontend/dist/`
- `frontend/node_modules/`
- `.venv/`
