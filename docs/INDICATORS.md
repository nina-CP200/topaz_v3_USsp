# Scanner Indicator Reference

The market scanner (`/stocks`) displays Williams %R, MACD, MA crossover, and CCI from daily OHLCV data. It does not display ML predictions or confidence. Each indicator now includes a directional interpretation and explanation in three daily-bar parameter profiles. These values support manual inspection; signal status, stock rank, decision candidates, position sizing, and the text report continue to use the existing Moon Accumulation + Liquidity Exit strategy.

Implementation: `topaz_us/indicators.py`. All windows count input trading bars, not calendar days. Calculations sort bars by date and use only current and preceding bars.

## Short, Medium, and Long Horizons

These are application-defined observation windows, not forecasts or universally standardized settings. All three use **daily bars**, with different lookback parameters; they are not resampled weekly or monthly candles.

| Profile | Observation window | Williams %R | MACD fast / slow / signal | SMA fast / slow | CCI |
| --- | --- | --- | --- | --- | --- |
| Short (`short`) | About 1–4 weeks | 14 | 6 / 13 / 5 | 5 / 20 | 14 |
| Medium (`medium`) | About 1–3 months | 14 | 12 / 26 / 9 | 20 / 50 | 20 |
| Long (`long`) | About 3–12 months | 60 | 26 / 52 / 18 | 50 / 200 | 60 |

The table includes all three horizon summaries. Its period selector controls which profile's four indicator conclusions appear in the columns. The default is medium, preserving the original display parameters. Each stock's detail drawer has three tabs, with the summary, four individual conclusions and written reasons. The drawer also shows the actual last eligible bar date and bar count.

The numeric fields at the top level of a stock result remain the medium-profile values for compatibility. Profile-specific values, interpretations, parameters, and summaries live in `technical_analysis.horizons.short`, `.medium`, and `.long`. `technical_analysis` includes `version`, `as_of` (actual latest eligible bar date), and `bars`. Each horizon contains `label`, `window`, `parameters`, `values`, `signals`, and `summary`. Profile values use `ma_fast` and `ma_slow`; `parameters.ma` supplies their lengths. The numeric values and crossover states remain available in the API; the scanner renders their interpretations instead of raw values.

## Direction Rules

Each signal contains `direction` (`bullish`, `bearish`, `neutral`, or `unavailable`) and a Chinese `reason`. Rules are evaluated on unrounded values; serialization then rounds the numeric display. A near-zero value can therefore round to zero while retaining its original sign in the interpretation.

- **Williams %R:** Crossing upward from ≤ −80 to > −80 produces a bullish rebound signal; crossing downward from ≥ −20 to < −20 produces a bearish weakening signal. These events take precedence over position within the range. Otherwise > −50 is bullish, < −50 bearish, and exactly −50 neutral. The explanation identifies overbought (≥ −20) and oversold (≤ −80) conditions without automatically treating them as reversal signals.
- **MACD:** Positive `DIF − DEA` is bullish, negative bearish, and zero neutral. The explanation highlights a crossing on the analysis bar and identifies whether DIF is above or below zero. This is a momentum signal; it does not require DIF and DEA both to be on the same side of zero.
- **MA:** A golden cross or fast SMA above slow SMA is bullish; a death cross or fast SMA below slow SMA is bearish. Equal averages are neutral. Missing current or preceding spread is unavailable.
- **CCI:** > +100 is bullish and < −100 bearish under this application's trend interpretation. The inclusive range −100 to +100 is neutral. It is not interpreted as an automatic mean-reversion signal.

A horizon summary is bullish if at least three of four indicators are bullish, bearish if at least three are bearish, and otherwise neutral / mixed. If any indicator is unavailable, the whole horizon summary is unavailable and reports its coverage count. The summary includes counts for all four directions and a written reason. Indicators share price inputs, so agreement is a rule-based description, not four independent confirmations or an estimated success probability. These rules have not been validated as a separate trading strategy.

Direction references: [Fidelity Williams %R](https://www.fidelity.com/learning-center/trading-investing/williams-indicator), [Fidelity MACD](https://www.fidelity.com/learning-center/trading-investing/technical-analysis/technical-indicator-guide/macd), and [Fidelity CCI](https://www.fidelity.com/learning-center/trading-investing/technical-analysis/technical-indicator-guide/cci). Horizon parameters, the Williams midpoint interpretation, and the three-of-four summary are this application's explicit heuristics.

## Medium-Profile Formulas and Parameters

The following table describes the default medium profile. Other profiles substitute the lengths listed above into the same formulas.

| Indicator | Calculation | API fields |
| --- | --- | --- |
| Williams %R (14) | `−100 × (HH14 − close) / (HH14 − LL14)` | `williams_r` |
| MACD (12/26/9) | `DIF = EMA12(close) − EMA26(close)`; `DEA = EMA9(DIF)`; histogram = `DIF − DEA` | `macd`, `macd_signal`, `macd_hist` |
| MA crossover (20/50) | Compare SMA20(close) and SMA50(close) on the current and preceding bars | `ma20`, `ma50`, `ma_cross` |
| CCI (20) | `(TP − SMA20(TP)) / (0.015 × MD20)`; `TP = (high + low + close) / 3` | `cci` |

`HH14` and `LL14` are the highest high and lowest low over the current 14-bar window. `MD20` is the mean absolute deviation of the 20 typical prices from their window mean; it is not standard deviation or the mean of rolling deviations.

MACD uses pandas exponential windows with `adjust=False`. Both price EMAs require the profile's slow EMA length before output; DEA requires the profile's signal length of valid DIF values. For the medium profile, these are 26 and 9. The displayed histogram is **not multiplied by two**. Comparisons with charting platforms should account for their EMA initialization and histogram convention.

The reference levels shown in the detail notes are −80 / −20 for Williams %R and −100 / +100 for CCI. They are explanatory reference levels, not new automatic entry or exit rules.

## MA Crossover States

Let `spread = SMA20 − SMA50`. A state requires valid spreads on both the current and preceding bars.

| API value | Condition | Internal state meaning |
| --- | --- | --- |
| `golden_cross` | Previous spread ≤ 0 and current spread > 0 | 当日金叉 |
| `death_cross` | Previous spread ≥ 0 and current spread < 0 | 当日死叉 |
| `above` | Positive spread without a crossing on this bar | MA20 > MA50 |
| `below` | Negative spread without a crossing on this bar | MA20 < MA50 |
| `equal` | Current spread = 0 | 均线持平 |
| `unavailable` | Current or previous spread is missing | 数据不足 |

“当日” refers to the analysis bar, which can be historical. A crossing is marked on that bar only; subsequent bars show the current relationship. SMA20/SMA50 are distinct from the strategy's 21/55/144 TMA and QQQ MA200 market gate.

## API and Display Contract

`GET /api/analysis/daily` includes these optional fields on each item in `results`:

```json
{
  "williams_r": -73.0015,
  "macd": 3.6915,
  "macd_signal": 4.13,
  "macd_hist": -0.4384,
  "ma20": 201.25,
  "ma50": 198.5,
  "ma_cross": "above",
  "cci": -18.325
}
```

This is an illustrative API field example, not a current quote. Numeric fields are rounded to four decimal places by the backend and retained for calculation and compatibility. The scanner table and detail drawer display only technical conclusions and explanations, without the raw indicator values or their numeric sorting controls. Stock prices, daily price changes, dates, and observation windows remain visible.

For the medium profile, rolling windows require a full window. Williams %R first becomes available after 14 bars, CCI after 20, MA50 after 50, a crossover state after 51, and DEA/histogram after 34. Flat windows with a zero Williams price range or zero CCI deviation produce an undefined value. Non-finite numeric results become JSON `null`, and the corresponding unavailable signal displays `数据不足` rather than a raw numeric placeholder. An empty history produces no indicator fields. The long-profile summary requires at least 201 bars for both current and previous SMA50/SMA200 spreads; shorter histories can still provide short- and medium-profile analysis.

The table opens on the full universe and the medium indicator profile, with ticker/name search and sector filters. Existing strategy-status filters are also available. Its summary includes the saved analysis timestamp and filtered/total stock counts. The timestamp belongs to the saved analysis; it is not a live-price timestamp.

## Moon Accumulation Assessment

`moon_analysis` is a separate named daily assessment, with `version`, `direction`, `label`, `reason`, `setup` (`none`, `accumulation`, `expansion`, or `both`), `triggered`, `market_entry_allowed`, and an optional actual bar date `as_of`. It reuses `topaz_us.strategy.build_signal_frame()` rather than approximating Moon from the four displayed indicators. At least 146 daily bars are required, matching the strategy's cross-section warm-up.

Priority order:

1. A bearish liquidity sweep gives `退出预警` / bearish, even if an entry setup also exists.
2. A close below the prior structure low gives `结构转弱` / bearish.
3. An accumulation or expansion setup with a closed QQQ gate gives `等待市场` / neutral.
4. An eligible setup gives `吸筹触发`, `突破触发`, or `吸筹与突破触发` on its first bar; continuing setups use `延续` instead of `触发`. Direction is bullish, describing the setup rather than promising returns. If no gate was supplied, its explanation explicitly says the gate still needs checking.
5. A bullish TMA order without a setup gives `等待形态` / neutral; otherwise `暂无形态` / neutral.
6. Incomplete history gives `数据不足` / unavailable before evaluating setup states.

Moon appears in a separate table column and detail section. It is the same daily strategy assessment regardless of the selected short/medium/long profile, and it does not change the four-indicator agreement threshold. The strategy research page and API have been removed; command-line backtests and saved result files are retained.

## Existing Snapshots

New analysis runs calculate the indicators from each stock's history and save them with the other results. For snapshots lacking the current `technical_analysis.version` or `moon_analysis.version`, or when the Moon saved QQQ gate differs from the snapshot gate, the daily API supplements the response from `data/raw/us_history/<symbol>.parquet`:

1. Read local cached history for the symbol.
2. Retain only bars whose calendar date is on or before the saved analysis date.
3. Calculate the latest eligible values and add them to the response.

Supplementation does not contact the data provider, persist the added fields, or change the snapshot timestamp. It uses the latest eligible cached bar, which may precede the snapshot date. If the snapshot date or cache is missing, no eligible bars remain, or the supported read/validation errors occur, unavailable values remain visible. Numeric-only snapshots also receive the three-period analysis. A snapshot already carrying both current assessment versions and the matching Moon gate is used as saved; run a new analysis to regenerate a partial or damaged current-version record.

The displayed values for old snapshots depend on the currently available cached history and formulas. This is a compatibility view, not a versioned historical migration. Use **刷新分析** to create a new saved analysis; a page reload only rereads the existing record.

## Verification

```bash
uv run python -m unittest tests.test_indicators -v
```

Offline tests cover formula values, crossing-day behavior, flat-window handling, absence of look-ahead, the original-date cutoff for old snapshots, distinct profile parameters, bullish/bearish histories, oversold/overbought interpretation, mixed and incomplete summaries, JSON safety, and the 201-bar minimum for long MA analysis. Frontend build and lint commands are documented in the [Frontend Guide](../frontend/README.md).
