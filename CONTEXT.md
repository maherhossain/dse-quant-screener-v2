# DSE Quant Screener v2 — Project Context

## Project goal

Build a research-driven quantitative trading system for the Dhaka Stock Exchange (DSE)
that identifies swing-trading candidates over a 2–30 day horizon (primary: 10 trading days).
The system must be validated through rigorous backtesting before any deployment.
ML/AI is a late-stage enhancement, only after a validated feature set exists.

## The edge thesis

Detect accumulation before the crowd recognises a breakout. Specifically, look for:

- Volume/turnover behaviour: unusual accumulation without an obvious price breakout.
- Volatility compression: price range and ATR gradually contract.
- Liquidity + participation: increasing trades/ticket activity, not just one large transaction.
- Relative strength: stock holds up while the broader DSEX / its sector is weak.
- Base quality: repeated support, controlled pullbacks, price near the upper part of the base.
- Catalyst confirmation: breakout comes _after_ accumulation, not as the initial signal.

## The failure hypothesis for the previous system

The previous screener (v1) was essentially a high-beta momentum chaser with no market-regime
awareness. A multi-year backtest (36 dates across 2014–2026) showed:

- Mean 20-day forward return across 32 dates: −1.20%
- Win rate: 43.75%
- Worst date: −10.65%
- Performance collapsed in bear/correction regimes (Aug 2026, Oct 2015, Oct 2024, Apr 2025)

**Hypothesis for v2: the underlying signal may be fine; the failure may be lack of regime context.
This is a hypothesis to test, not an assumption. See H4.**

## Specific hypotheses (tested within the broader empirical search)

These are starting points, not the search itself. They will be tested alongside 50–100 other
candidate features in Module 2. Their value is that they encode domain knowledge, but they
should not receive preferential treatment during evaluation. If the data does not support them,
they are dropped like any other feature.

### H1 (primary): Sector + compression + near-52wk-high

Stocks in leading sectors, showing volatility compression, and trading near their 52-week high
outperform the market over the next 10 trading days.

### H2: Block activity + stability

Stocks with recent block-trade activity, combined with price stability and volume accumulation,
outperform over the next 20 trading days.

### H3: Small-cap volume expansion

Small-cap stocks with sudden volume expansion and price strength (filtered for liquidity)
outperform over the next 10 trading days.

### H4: Regime filter overlay

**Tested only after H1/H2/H3 establish whether an underlying signal has edge.**
Determine whether DSEX market-regime awareness improves signal performance, particularly by
reducing poor entries during bear/correction regimes, without materially harming bull-regime
performance. Treat market-regime awareness as a hypothesis to test, not an assumed solution.

## Target horizon and risk

- **Primary horizon:** 10 trading days forward return
- **Secondary horizons:** 5-day and 20-day forward returns
- **Trading range:** 5–20 days, maximum 30
- **Max drawdown tolerance:** 10%

## Data split (do not violate)

- **Research / development:** 2014 – 2020
- **Validation:** 2021 – 2023 (exclude 2022 Q3 – 2023 Q4 as floor period)
- **Final test (touch once, at the end):** 2024 – 2026

## Domain insights (encode and test, do not assume)

1. Retail/speculative money can move small and low-float stocks very quickly.
2. Volume matters more than price alone.
3. Accumulation often appears before the obvious breakout through compression, repeated
   support, and increasing activity.
4. Sector leadership matters strongly — a good stock in a weak sector can fail.
5. DSEX regime matters — high-beta stocks can look excellent during bullish periods but
   become dangerous in market declines.
6. Corporate actions/news can dominate technical signals — earnings, dividends, regulatory
   decisions, sponsor/director activity.
7. Liquidity is a major hidden risk — a backtest can look good on paper but be difficult
   to enter/exit in reality.
8. Near 52-week highs can be positive — strong stocks often continue rather than
   automatically mean-revert.
9. Block trades need interpretation — they may represent accumulation, but they can also be
   transfers or exits.
10. The DSE has structural inefficiencies — limited liquidity, uneven information flow,
    heterogeneous investor behaviour can create opportunities.

## Operating rules

- **The user runs all code.** The assistant writes code; the user executes and pastes outputs.
- **One change at a time.** After each fix, verify before moving on.
- **No deleting files without confirmation.**
- **No silent exception swallowing.** If a try/except is removed, say so.
- **Maintain the existing logging style** (Python `logging` module, format
  `'%(asctime)s [%(levelname)s] %(message)s'`).
- **Do not touch files not in scope for the current module.**
- **Git is installed.** Every module ends with a commit.
- **Module-based structure.** Each module has its own chat. Paste `CONTEXT.md` and the
  current `HANDOFF.md` at the top of each new chat.

## Research integrity rules

- **No look-ahead bias.** Every feature, signal, ranking, filter, and trade decision must use
  only information available at the decision timestamp. Forward returns are outcomes/labels
  only and must never enter feature calculation, ranking, filtering, or model training
  before the appropriate out-of-sample evaluation.
- **Feature validation.** Do not keep a feature merely because it is intuitively plausible.
  Each candidate feature must be evaluated against forward 5/10/20-day returns, preferably
  cross-sectionally and across different market regimes. Measure both predictive strength
  and stability.
- **No backtest optimization.** Do not repeatedly tune thresholds, weights, lookbacks, or
  feature combinations against the final validation/test period. Respect the data split.
- **Regime neutrality.** Treat market-regime awareness as a hypothesis to test, not an
  assumed solution. Measure whether it improves weak-regime performance without materially
  damaging strong-regime performance.
- **Incremental complexity.** Add a new feature, filter, or module only when its incremental
  value can be measured against a simpler baseline.
- **Reproducibility.** Every research result must record the dataset period, universe,
  feature definitions, parameters, filters, transaction assumptions, and evaluation
  methodology.
- **Baseline first.** Every major improvement must be compared against the previous verified
  baseline so we know whether it actually adds value.

## Feature discovery rules (Module 2 specific)

- **Empirical discovery over hypothesis confirmation.** The primary goal of Module 2 is to find
  what actually predicts DSE forward returns, not to confirm our priors. Candidate features are
  drawn from a broad space (momentum, volatility, volume, structure, relative strength, liquidity,
  sector, regime, fundamentals, corporate actions, block trades), not only from H1–H4.
- **Conditional validation.** Features must be tested not only for average IC but for IC
  conditional on regime (DSEX trend), sector, market cap, and liquidity. A feature that works
  only in specific conditions is more useful than one that works weakly everywhere — as long as
  the conditions are pre-specified and measurable in real time.
- **Multiple-comparison discipline.** When mining many features, the train/validation/test split
  is strict. Any feature that does not survive validation is dropped regardless of research-period
  strength. Pre-commit to IC ≥ 0.02 on validation.
- **Stability over peak.** A feature must work across multiple years, not just one. A feature
  with IC = 0.08 in one year and IC = −0.05 in another is not a feature; it is noise.
- **Record the conditions of validity.** For every surviving feature, document _when_ it works,
  not just _that_ it works. "Momentum works in bull regimes, fails in bear regimes" is a finding.
  "Momentum has IC = 0.03" is not sufficient.

## Kill criteria (pre-committed)

Before Module 2 begins, we pre-commit to these thresholds. If a hypothesis fails to
meet them on the **validation set**, it is dropped — no rationalisation.

- **Individual feature:** if Information Coefficient (IC) against 10-day forward returns
  is below 0.02 on the validation set, drop the feature.
- **Combined signal:** if Sharpe ratio is below 0.5 on the validation set, do not proceed
  to full backtest.
- **Regime filter:** if the improvement in Sharpe over no-regime-filter is below 0.3 on
  the validation set, do not keep the filter.
- **Complexity:** if a more complex model does not improve Sharpe by at least 0.2 over
  a simpler baseline on the validation set, keep the simpler model.

## Data provenance (per feature)

Every feature that survives Module 2 must be documented here before it enters the model.

| Feature name                          | Source table | Source column | Unit | As-of rule |
| ------------------------------------- | ------------ | ------------- | ---- | ---------- |
| (populated as features are validated) |              |               |      |            |

## Module structure

- **Module 0: Foundation** — CONTEXT.md, HANDOFF.md, git repo, endpoint audit, new DB schema, interfaces
- **Module 1: Data Pipeline** — historical backfill, daily sync, data quality, weekly aggregation
- **Module 2: Empirical Feature Discovery** — broad search across 50–100 candidate features; measure
  unconditional and conditional IC; validate survivors. H1/H2/H3 are tested _within_ this broader search,
  not in isolation. **Most important module.**
- **Module 3: Model Design** — combine empirically validated features, add regime awareness as one
  conditional discovery among many, define position sizing rules
- **Module 4: Backtest Engine** — event-driven backtester with realistic costs and walk-forward validation
- **Module 5: Live Deployment** — daily post-market script, output generator, monitoring
- **Module 6: ML/AI Layer (last)** — ML model on validated feature set, only kept if it outperforms

## Data sources (API endpoints)

- `https://provider.bullbd.com/shares/get-names-tv` — list of all tickers
- `https://provider.bullbd.com/eod/get-eop-data-by-code?code=DSEX` — DSEX end-of-day
- `https://provider.bullbd.com/shares/get-once` — live snapshot of all stocks (single call)
- `https://provider.bullbd.com/shares/get-one-for-tv2?code={CODE}` — historical chart data
- `https://provider.bullbd.com/corporate-actions/get-corporate-actions?share={CODE}` — corporate actions
- `https://provider.bullbd.com/shares/get-block-share?code={CODE}` — block trades
- `https://stocknow.com.bd/api/v1/instruments/{CODE}/history` — alternate historical OHLCV
- `https://stocknow.com.bd/api/v1/sectors` — 22 sector definitions
- `https://stocknow.com.bd/api/v1/instruments` — rich instrument snapshot (7/15/30/90/180/365d prices,
  yearly high/low, floor, category A/B/Z/SME, sector_id, block activity)
- `https://www.dse.com.bd/api/live/market` — official DSE live market (access may be restricted)

**Endpoint audit results (2026-10-05):** See `ENDPOINT_AUDIT.md` for full details.
Primary sources by purpose:

- **Bulk historical backfill (2014-03→present):** `provider.bullbd.com/shares/get-one-for-tv2?code={CODE}`
- **Gap-fill (2013-01-28→2014-03-01):** `stocknow.com.bd/api/v1/instruments/{CODE}/history?data2=true&resolution=1D&skip=N`
- **Live daily snapshot:** `provider.bullbd.com/shares/get-once`
- **Instrument master:** `provider.bullbd.com/shares/get-names-tv`
- **Corporate actions:** `provider.bullbd.com/corporate-actions/get-corporate-actions?share={CODE}`
- **Block trades:** `provider.bullbd.com/shares/get-block-share?code={CODE}` (2023-06-21+ only)
- **Live cross-check + breadth:** `www.dse.com.bd/api/live/market`

**Rejected:** `provider.bullbd.com/eod/get-eop-data-by-code` (rolling period aggregates only).

**Note on `trade_value`:** in BullBD data, `vl` is in **millions of BDT**. Every consumer must
be explicit about unit conversion.

**Note on DSE floor period:** the BSEC imposed a price floor from ~July 2022 to late 2023.

- 2022 Q4 – 2023 Q4: deep floor. Do NOT include in backtests.
- 2024 Q1 – Q2: partial floor. Borderline; handle carefully.
- 2024 Q3 onwards: recovered.
  **Study start:** 2013-01-28 (DSEX launch). Pre-2013 DSEX values are DGEN and must be discarded.

## Environment

- **OS:** Windows (paths use `\`)
- **Python:** 3.12 (`py` command). Use `py` exclusively.
- **MySQL:** localhost, user root, password empty, database name TBD.
- **Stack:** pandas, numpy, mysql-connector-python, pandas_ta, SQLAlchemy, scikit-learn, shap.
- **Frontend:** PHP dashboard (separate layer, out of scope for now).

## V1 reference

V1 project at `D:\laragon\www\dse-quant-screener\`. Key v1 findings:

- 17 tables, ~3.4M rows.
- `market_data` has daily OHLCV + trade_value + trades for 2014–2026 (2023 quality issues).
- `index_data` has DSEX daily data back to 2014.
- 36-date backtest: mean 20-day fwd return −1.20%, win rate 43.75%.

V1 backup tables to keep for reference:

- `screener_daily_ranks_backup_20261003`
- `screener_daily_ranks_newweights_20261003`
- `screener_daily_ranks_pre_study_20261003`

## Decisions log

- **2026-10-04:** v2 starts as new folder `dse-quant-screener-v2/`, not rebuild in place.
- **2026-10-04:** Module-based structure, each module has its own chat + CONTEXT.md + HANDOFF.md.
- **2026-10-04:** ML is Module 6, last stage, only after features are validated.
- **2026-10-04:** Target horizon: 10 trading days primary; 5 and 20 secondary.
- **2026-10-04:** Max drawdown tolerance: 10%.
- **2026-10-04:** Edge thesis = accumulation before breakout.
- **2026-10-05:** Adopted all research-integrity rules (anti-leakage, feature validation,
  no backtest optimization, regime neutrality, incremental complexity, reproducibility, baseline-first).
- **2026-10-05:** Adopted data split: 2014–2020 research, 2021–2023 validation, 2024–2026 final test.
- **2026-10-05:** Adopted pre-committed kill criteria (IC ≥ 0.02, Sharpe ≥ 0.5, etc.).
- **2026-10-05:** H4 (regime filter) tested only after H1/H2/H3 establish an underlying edge.
- **2026-10-05:** Module 2 revised from "hypothesis testing" to "empirical feature discovery."
  Broader search across 50–100 candidate features. H1–H4 tested within this search rather than
  in isolation. Conditional IC (by regime, sector, cap, liquidity) is a first-class finding,
  not a secondary analysis. This change avoids anchoring on possibly-wrong priors and lets the
  data determine which signals, and which conditions, actually matter.
- **2026-10-05:** Endpoint audit complete. 11 endpoints classified. Full details in ENDPOINT_AUDIT.md.
- **2026-10-05:** Study start date moved to **2013-01-28** (DSEX launch). DSEX archive
  before this date is DGEN, not DSEX. Individual stock bars may go back further but
  regime analysis uses DSEX from 2013-01-28. Data split revised accordingly:
  Research 2013-01-28→2020-12-31, Validation 2021-01-01→2023-12-31, Test 2024-01-01→2026-10-05.
- **2026-10-05:** Primary backfill strategy: **bullbd get-one-for-tv2** (endpoint #7,
  single call per instrument, 2014-03-02→present). Gap-fill via **stocknow history**
  (endpoint #6) for 2013-01-28→2014-03-01.
- **2026-10-05:** Daily live sync uses **bullbd get-once** (endpoint #4) as primary,
  **DSE official live market** (endpoint #10) as cross-check.
- **2026-10-05:** Volume unit conventions locked: `value`/`vl`/`turnover` in millions of BDT;
  `volume`/`v` in raw shares. DSEX/DS30/DSES volume definitions differ between sources:
  endpoint #6's index volume = whole-market; endpoint #7's index volume = constituent-only.
  **Use endpoint #6 for index volume; document per-source semantics in Module 1.**
- **2026-10-05:** Corporate actions (endpoint #8) sparse — ~1 event/stock/year since 2014.
  Used for filtering (ex-dividend windows), not as a primary feature.
- **2026-10-05:** Block trades (endpoint #9) coverage starts **2023-06-21**. H2 cannot
  be research-tested on 2013–2023. Decision deferred to Module 2:
  keep H2 as live-only signal, replace with proxy, or drop.
- **2026-10-05:** DSE official live market (endpoint #10) exposes 10-day rolling breadth
  history (`dailyTotals`). Forward-only; cannot backfill. Useful for Module 5 monitoring.
