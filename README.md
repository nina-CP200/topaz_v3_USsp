# Topaz US

Topaz US is a local FastAPI + React research dashboard for NASDAQ 100 daily trend-pullback and breakout scanning. The first version is long-only, uses free `yfinance` daily data, benchmarks market risk with `QQQ`, and does not use machine learning.

## Market Scanner

The `/stocks` page opens on the full stock universe and displays four daily technical indicators:

| Indicator | Parameters | Display |
| --- | --- | --- |
| Williams %R | 14 bars | Bullish, bearish, or neutral, with an explanation |
| MACD | EMA 12 / 26, signal EMA 9 | Momentum direction and crossing explanation |
| MA crossover | SMA 20 / 50 | Trend direction and crossing explanation |
| CCI | 20 bars, constant 0.015 | Strong, weak, or neutral momentum conclusion |

The table also shows short-, medium-, and long-horizon directional summaries. Switch profiles to see each indicator's bullish, bearish, neutral, or unavailable conclusion; hover for the reason. Raw technical indicator values are kept in the API, while the table and detail drawer present conclusions and explanations. Click a stock row for three analysis tabs with full explanations. The default medium profile uses the parameters above; short and long profiles use separate daily-bar parameters documented in the [Indicator Reference](docs/INDICATORS.md). Ticker/name search, sector filtering, signal-status filters, analysis refresh, and report preview remain available. The summary shows the saved analysis timestamp and filtered/total stock counts. ML predictions and confidence are not displayed.

A separate **Moon Accumulation** column and detail section explain the original daily strategy: accumulation or breakout trigger, continuation, waiting for a setup, market hold, structural weakness, or exit warning. Exit risk takes precedence; a closed QQQ gate prevents a setup being presented as an actionable entry. Moon is independent of the four-indicator horizon vote.

The scanner indicators and directional summaries are rule-based descriptions. Each horizon needs at least three of four signals in agreement for a bullish or bearish summary; mixed signals stay neutral and incomplete data stays unavailable. The observation windows are approximately 1–4 weeks, 1–3 months, and 3–12 months, all calculated from daily bars. They are not return predictions. The decision dashboard, status filters, rankings, and report preview still use the Moon Accumulation + Liquidity Exit strategy described below. Adding these four displayed indicators does not replace its entry, exit, or allocation rules.

Existing snapshots without the current technical-analysis or Moon assessment version are supplemented on read using local cached bars dated on or before the original analysis date. This does not download quotes, rewrite the saved snapshot, or advance its timestamp. Unavailable conclusions appear as `数据不足`; use **刷新分析** to generate a new snapshot when needed.

See [Indicator Reference](docs/INDICATORS.md) for formulas, API fields, crossover states, and compatibility details.

## Watchlist

Click the star beside a stock in the scanner, or use the favorite button in its detail drawer, to add or remove it from your watchlist. Use **仅看自选** in the scanner or open **我的自选** (`/watchlist`) from the sidebar. The watchlist shares the scanner's search, sector/status filters, technical conclusions, Moon assessment, and refresh controls.

Favorites are saved locally in `data/raw/watchlist.json` and survive page reloads and server restarts on the same installation. Use **搜索 / 添加标的** to search US stocks/ETFs by code or English name, or add a complete ticker directly. Outside-universe symbols are validated against available daily history and receive separate on-demand analysis. This does not expand the original NASDAQ decision candidate universe or change holdings and position sizing. Saved symbols without analysis remain in the list, with a notice and a removal action. Saving failures leave the displayed selection unchanged and offer a retry; read failures preserve the original file and disable changes until loading succeeds.

## Strategy

- Universe: static `config/nasdaq100_stocks.json`
- Benchmark: `QQQ`
- Data: daily OHLCV from `yfinance`
- Cache: `data/raw/us_history/*.parquet`
- Holding horizon: several days to several weeks
- Direction: long-only

The strategy name is `Topaz US Moon Accumulation + Liquidity Exit`.

Each stock receives:

- `accumulation_entry`: a measured pullback into the 21-period TMA zone while 50-day structure remains intact and repair momentum improves
- `expansion_add_entry`: a volume-backed close above the prior 30-day high with 21/55/144 TMA bullish alignment
- `moon_buy_signal`: a setup onset, emitted only once rather than on every bar that stays in the same zone
- `bearish_sweep`: a failed upside liquidity sweep, used as an exit warning
- `risk_penalty`: bearish sweep, excessive ATR, or extension pressure

When a Moon buy signal is present, the system calculates:

- `entry_price`: signal close
- `stop_loss`: entry minus ATR x 1.5

There are no fixed profit targets. The strategy holds until a bearish liquidity sweep, the initial ATR stop, or portfolio-level discretion.

`composite_score` is normalized to `0-100`. Active buy signals require an accumulation or expansion setup. If `QQQ` is below MA200, the system will not produce active buy signals.

Advice rules:

- Active signal and score `>= 85`: 建议买入
- Active signal below buy threshold or score `>= 65`: 可以关注
- `35-65`: 建议观望
- `< 35`: 建议回避

Single-stock position cap is `12%`. The default research portfolio caps gross invested capital at `70%`, leaving the remainder in cash.

## Run

```bash
./setup.sh
./start.sh
```

The app runs at `http://localhost:8000`.

Run analysis from the command line:

```bash
uv run python -m topaz_us.analysis.daily
uv run python -m topaz_us.backtest.moon_liquidity --days 500 --max-holding-days 40
```

Optional command-line backtests remain available for offline work. The strategy research page and its API have been removed; these files are no longer shown in the app:

```bash
uv run python -m topaz_us.backtest.moon_liquidity --portfolio --days 500 --max-holding-days 40 --position-size-pct 0.12 --target-exposure-pct 0.70 --output data/raw/moon_portfolio_baseline.json
uv run python -m topaz_us.backtest.moon_liquidity --portfolio --market-momentum-overlay --days 500 --max-holding-days 40 --position-size-pct 0.12 --target-exposure-pct 0.70 --output data/raw/moon_portfolio_momentum_overlay.json
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

For day-to-day development, start both services with:

```bash
./dev.sh
```

This starts FastAPI on `http://127.0.0.1:8000` and the Vite frontend on
`http://127.0.0.1:5173`. Press `Ctrl+C` once to stop both services. Override
ports with `BACKEND_PORT=8001 FRONTEND_PORT=5174 ./dev.sh` when needed.

Run all local checks:

```bash
make check
```

Project documentation:

- [Development Guide](docs/DEVELOPMENT.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Indicator Reference](docs/INDICATORS.md)
- [Frontend Guide](frontend/README.md)

## API

- `GET /api/market/overview`
- `GET /api/market/history`
- `GET /api/analysis/daily`
- `POST /api/analysis/refresh`
- `GET /api/analysis/status`
- `GET /api/analysis/report`
- `GET /api/decision/daily`
- `GET /api/watchlist/search?q=...`
- `GET /api/watchlist/analysis`
- `GET /api/watchlist`
- `PUT /api/watchlist/{symbol}`
- `DELETE /api/watchlist/{symbol}`
- `GET /api/portfolio`
- `PUT /api/portfolio`
- `POST /api/portfolio/analyze`
- `GET /api/settings/decision`
- `PUT /api/settings/decision`

## Notes

This project intentionally excludes old runtime data, old model files, and old market-specific caches. The NASDAQ 100 universe is static for v1 and should be manually reviewed when index constituents change.

For research only. Not investment advice.
