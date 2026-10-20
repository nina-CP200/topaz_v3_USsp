# Topaz US Frontend

React, TypeScript, Vite, Ant Design, and ECharts provide the local research dashboard. Requests use the `/api` base URL in `src/api/index.ts`.

## Run Locally

From the repository root, `./dev.sh` starts both the backend and frontend. Alternatively, run `make dev-backend` and `make dev-frontend` in separate terminals.

The default frontend address is `http://127.0.0.1:5173`, and the backend is `http://127.0.0.1:8000`. Vite proxies `/api` to the backend; configure `VITE_API_TARGET` when using a different backend address. `BACKEND_PORT` and `FRONTEND_PORT` configure the combined `dev.sh` launcher.

To run only the frontend from this directory:

```bash
npm install
npm run dev -- --host 127.0.0.1
```

For a production-like local run, `./start.sh` from the repository root builds the frontend and serves it through FastAPI on port 8000.

## Pages

| Route | Purpose |
| --- | --- |
| `/dashboard` | Daily decisions, QQQ market gate, candidate allocations, and urgent holding actions |
| `/stocks` | Full stock universe, four technical indicators, strategy-status filters, and stock details |
| `/portfolio` | Local holdings and portfolio analysis |
| `/settings` | Investable capital and other local settings |

The root route redirects to `/dashboard`; the retired `/research` and `/about` routes redirect to `/stocks`. The strategy research navigation, page, and API client have been removed.

## Market Scanner

`src/pages/Stocks.tsx` displays Williams %R, MACD, SMA crossover, and CCI with individual bullish/bearish/neutral labels and hover explanations. Three summary columns show short (about 1–4 weeks), medium (1–3 months), and long (3–12 months) analysis. A period selector switches the four indicator columns between separate daily-bar parameter profiles. The medium profile defaults to Williams %R (14), MACD (12/26/9), SMA20/SMA50, and CCI (20). It defaults to the full universe. Search, sector filters, strategy-status filters, report preview, and background analysis refresh remain available.

The indicator columns show conclusions only: bullish, bearish, neutral, or unavailable. Hover a conclusion for its explanation, or click a row for three period tabs with the full reasoning. The detail drawer also avoids raw technical values. Prices, daily price changes, timestamps, and observation windows remain visible. The drawer reports the actual last eligible bar date and available daily-bar count. A profile is bullish or bearish only with at least three agreeing indicators; otherwise it is mixed, or unavailable when any indicator is missing.

A separate Moon Accumulation column and detail section consume `moon_analysis` and show the original daily strategy's named conclusion: trigger, continuation, waiting for market/setup, structural weakness, or exit warning. Moon is shared across period tabs and is not added to the four-indicator vote. Its source is the same `build_signal_frame()` used by the strategy, with the saved QQQ market gate applied.

The summary shows the saved analysis timestamp and filtered/total counts. “当日金叉” and “当日死叉” refer to the analysis bar, not necessarily today's date. Reloading the page reads the saved snapshot; **刷新分析** starts a new backend analysis and polls `/api/analysis/status` for completion.

The scanner does not display ML predictions, model confidence, score breakdowns, suggested position sizes, or entry/stop prices. The decision dashboard and other strategy pages still use the existing Moon strategy. Backend compatibility fields may remain in old payloads without being part of the scanner's display contract.

See the [Indicator Reference](../docs/INDICATORS.md) for field names, formulas, formatting, and local-cache supplementation of old snapshots.

## Checks

Run from this directory:

```bash
npm run build
npm run lint
```

`build` runs TypeScript project checks and creates `dist/`. FastAPI serves that directory for the combined local app. `lint` runs ESLint separately. From the repository root, `make check` runs Python compilation, unit tests, and the frontend build; it does not include frontend lint.

After changing displayed fields, verify the `/stocks` table and detail drawer against the API, including unavailable conclusions, Moon risk/market-gate states, and the analysis timestamp. Keep types in `src/api/index.ts`, backend schemas, indicator calculations, and the parameter labels in sync.
