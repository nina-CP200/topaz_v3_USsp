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
  strategy.py             Moon accumulation entry and liquidity exit scoring
  indicators.py           Williams %R, MACD, SMA crossover, and CCI for the scanner
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

The shared `build_signal_frame()` function is the source of truth for daily analysis and the Moon/liquidity backtest. Keep new entry or exit rules there so the dashboard and research results cannot silently drift apart.

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

The portfolio backtest uses a 12% single-stock allocation cap and a 70% gross exposure cap by default. Its output includes `annual_results`, which reports each calendar year's portfolio return, QQQ return, relative return, drawdown, average invested capital, and trade count. The annual rows are slices of one continuous simulation, so positions and equity can carry across a year boundary. A year marked `warmup_only` only contains indicator warm-up data and should not be treated as an active strategy year.

## Updating Scanner Indicators

The scanner's displayed indicators and directional explanations are calculated in `topaz_us/indicators.py`. `HORIZON_PROFILES` defines separate short/medium/long daily-bar parameters. `interpret_indicators()` produces per-indicator directions and reasons, and `summarize_signals()` applies the explicit three-of-four agreement rule. Missing any signal makes the summary unavailable. `latest_indicators()` includes all three profiles under `technical_analysis`, alongside the original medium-profile numeric fields. `build_indicator_frame()` sorts daily OHLCV bars by date and produces causal series; `latest_indicators()` returns the latest values rounded to four decimal places and converts undefined numeric values to `None` for JSON. Empty history returns an empty dictionary.

Keep these layers aligned when changing a parameter or field:

- `topaz_us/indicators.py`: formulas and crossover states.
- `topaz_us/analysis/daily.py`: adds indicator values to each stock in new analysis snapshots.
- `backend/routers/analysis.py`: supplements old snapshots from the local parquet cache through the saved analysis date.
- `backend/schemas.py` and `frontend/src/api/index.ts`: nullable numeric fields and crossover state.
- `frontend/src/pages/Stocks.tsx`: conclusion labels, hover explanations, Moon assessment, and period detail tabs.
- `docs/INDICATORS.md`: calculation and API contract.

The four-indicator horizon calculation is independent of `build_signal_frame()` and does not change strategy scoring or backtest rules. Keep the MACD display convention explicit: its histogram is `DIF − DEA`, without the factor of two used by some platforms. MA20 and MA50 here are simple averages, distinct from the strategy's 21/55/144 TMA.

Old-snapshot supplementation happens in the daily GET response only. Do not use later bars or fetch live quotes to fill an old record. Preserve its date and file; absent data must remain visibly unavailable. Legacy snapshots are not persistently migrated, so changing indicator parameters also changes their calculated display on subsequent reads. Bump `ANALYSIS_VERSION` when changing profiles or interpretation rules, and `MOON_ANALYSIS_VERSION` when changing Moon interpretation. The API skips supplementation only when both versions and the saved Moon QQQ gate state match. `build_moon_assessment()` reuses `strategy.build_signal_frame()`; keep exit warnings and structure weakness ahead of entry setups, and distinguish a first trigger from a continuing setup. Moon needs the same full trend warm-up as cross-section scoring and is not included in the horizon vote.

Run the focused offline checks:

```bash
uv run python -m unittest tests.test_indicators -v
cd frontend
npm run build
npm run lint
```

If the virtual environment already has the runtime dependencies, `.venv/bin/python -m unittest tests.test_indicators -v` is an alternative from the repository root. The suite uses `unittest`; pytest is not required. The scanner presents conclusions, not raw technical values; numbers remain in the API for calculation and compatibility. The removed strategy research UI and API must not be reintroduced when changing navigation. Offline backtest scripts and stored results remain available.

The indicator tests cover formulas, crossing-day behavior, undefined ranges, causality, the old-snapshot date cutoff, profile parameters and directions, reversal trigger handling, mixed/unavailable summaries, JSON safety, and long-horizon warm-up.

`make check` includes Python compilation, unit tests, and the frontend build. Run frontend lint separately; it is not part of that target.

## Updating The Universe

The first version uses a static file:

```text
config/nasdaq100_stocks.json
```

Update it manually when NASDAQ 100 constituents change. Keep each item shaped as:

```json
{"code": "AAPL", "name": "Apple", "sector": "Information Technology"}
```

## Watchlist Changes

Keep `backend/routers/watchlist.py`, the watchlist client functions in `frontend/src/api/index.ts`, and `Stocks` favorites controls aligned. The watchlist storage API returns a `symbols` array. Additions outside the configured universe are validated by `get_history_data()`. `GET /api/watchlist/search?q=...` merges local matches with US equity/ETF search results from yfinance; upstream failure returns a warning and local matches. `GET /api/watchlist/analysis` computes price, four-indicator horizons and Moon assessments for external favorites, with explicit failed-symbol reporting. This separate path does not write the daily NASDAQ snapshot or produce portfolio allocations. Use per-symbol mutations rather than replacing the whole list, and keep the atomic-write and error-preservation behavior. The current lock covers a single backend process.

Run `uv run python -m unittest tests.test_watchlist -v` for persistence, normalization, duplicate handling, removal, input validation, corrupt-file protection, and failed-write checks. Tests use a temporary directory. For browser verification, check add/remove in both list and drawer, the watchlist-only route, reload persistence, empty states, and failed reads/writes. Do not leave synthetic favorites in the user's saved list after testing.

## Runtime Files

These are intentionally ignored by Git:

- `data/raw/us_history/*.parquet`
- `data/raw/latest_analysis_results.json`
- `data/raw/analysis_status.json`
- `data/raw/portfolio.json`
- `data/raw/watchlist.json`
- `data/raw/slack_configs.json`
- `frontend/dist/`
- `frontend/node_modules/`
- `.venv/`
