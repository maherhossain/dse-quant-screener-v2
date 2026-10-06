# DSE Quant Screener v2 — Module Interfaces
Purpose: record the boundary of each module — what it consumes, what it produces,
and what it must NOT do. Keeps module chats independent and prevents scope creep.
This is a contract, not an implementation guide. Each module's chat can add
detail but must not silently change the contract; changes require a CONTEXT.md
decision-log entry.
---
## Module 0 — Foundation (this module)
**Produces (for all downstream modules):**
- `CONTEXT.md` — project context, hypotheses, research-integrity rules, data split, kill criteria
- `HANDOFF.md` — session-by-session state
- `ENDPOINT_AUDIT.md` — full audit of 11 endpoints, verdicts, data-quality flags
- `INTERFACES.md` — this file
- `sql/001_schema.sql` — initial DDL for 11 tables in `dse_quant_v2`
- `audit/endpoint_probe.py` — reusable endpoint probe (dev-only)
- Git repo with remote `origin` at `github.com/maherhossain/dse-quant-screener-v2`
**Consumes:**
- Nothing (it is the base layer)
**Does NOT:**
- Fetch and store bulk historical data (that's Module 1)
- Create any feature, signal, or backtest
**Status:** schema designed and applied. Interfaces defined (this file). Module 0 complete.
---
## Module 1 — Data Pipeline
**Consumes:**
- `ENDPOINT_AUDIT.md` — which endpoints to use for what
- `sql/001_schema.sql` — the schema to fill
- The 11 tables in `dse_quant_v2` (all empty at module start)
**Produces:**
- Populated reference tables: `sectors`, `instruments`, `indices`, `trading_calendar`
- Populated historical tables: `daily_bars`, `index_bars`
- Populated event tables: `corporate_actions`, `block_trades`
- Populated forward tables: `daily_snapshot`, `market_snapshot`
- Rows in `load_log` for every load event
- Data-quality report (new file: `DATA_QUALITY.md`) — coverage, gaps, source disagreements
- Loader scripts under `src/loaders/` (or similar layout)
**Contract to Module 2:**
- `daily_bars` covers the equity universe for 2013-01-28 → present, unadjusted, gap-filled
- `index_bars` covers DSEX/DS30/DSES + sector indices from each index's `valid_from` onward
- `corporate_actions`, `block_trades` populated as far as sources allow
- `trading_calendar` populated 2013-01-28 → today, with notes for gaps
- All rows have `source`/`source_provider` provenance
- All loads audited in `load_log`
**Does NOT:**
- Compute any feature (returns, MAs, ATR, IC, etc.)
- Apply any transformation beyond parsing and unit normalization
- Adjust prices for corporate actions (that's Module 2's decision)
- Filter universe by category/type beyond what is needed for loading
**Open items for Module 1 chat:**
- Backfill strategy: endpoint #7 first (1 call/instrument, fast), endpoint #6 for 2013-01-28 → 2014-03-01 gap
- Rate-limit policy (endpoint #6 requires ~7 calls per instrument for gap-fill)
- Reconciliation of `instruments` between endpoints #2 and #3 (24 rows differ)
- Handling of the ~7 unclassified real equities (manual allow-list)
- Populating `instruments.first_seen_date` / `last_seen_date` from `daily_bars`
- Verify `trading_calendar` week convention (DSE trades Sun–Thu)
- Daily sync script skeleton (Module 5 will extend it)
---
## Module 2 — Empirical Feature Discovery
**Consumes:**
- All tables populated by Module 1
- `CONTEXT.md` hypotheses (H1–H4) and feature-discovery rules
- The kill criteria (IC ≥ 0.02 on validation)
**Produces:**
- A library of candidate features (50–100), each defined in code
- Unconditional IC, conditional IC (by regime, sector, cap, liquidity), stability reports
- A curated list of **surviving features** on the validation set
- Populated `Data provenance` table in `CONTEXT.md` for each surviving feature
- Documentation of *when* each feature works (regime conditions, sector conditions)
- A file such as `FEATURE_CATALOG.md` with definitions and conditions of validity
**Contract to Module 3:**
- A validated feature set with names, formulas, and as-of rules
- No look-ahead: every feature computed only from data available at its decision timestamp
- Data provenance recorded for each feature
**Does NOT:**
- Build a trading signal or ranking (that's Module 3)
- Run a backtest (that's Module 4)
- Train any ML model (that's Module 6)
**Open items for Module 2 chat:**
- Regime definition — DSEX trend classification (bull / bear / sideways)
- Floor-period handling (2022-07 → 2023-12): exclude or handle specially
- H2 caveat: block-trade coverage only from 2023-06-21
- H4 regime filter: test only after H1/H2/H3 establish an underlying edge
- Adjustment policy for corporate actions
---
## Module 3 — Model Design
**Consumes:**
- Surviving feature set from Module 2
- The kill criteria (Sharpe ≥ 0.5 on validation)
**Produces:**
- A combined signal (weights or ranking rule) that uses only validated features
- Regime-awareness component (if it survives its own kill criterion)
- Position-sizing rules
- Signal definitions ready for backtest
**Contract to Module 4:**
- A deterministic function `signal(features, date) -> ranking/scores`
- Documented weights, thresholds, as-of rules
- Regime overlay rules (if used)
**Does NOT:**
- Execute trades or simulate fills
- Compute PnL (that's Module 4)
- Tune to the final test set (test set is touched once, in Module 4)
**Open items for Module 3 chat:**
- Weighting scheme (equal weight vs IC-weighted vs rank-based)
- Universe filters to apply at signal time
- Position sizing: fixed fraction, volatility-scaled, or ranking-tier based
- Regime overlay condition (enter/exit rules)
---
## Module 4 — Backtest Engine
**Consumes:**
- Signal from Module 3
- All historical data from Module 1
- Trading calendar
- Assumed transaction costs (composed from CONTEXT.md rules)
**Produces:**
- Event-driven backtest engine with realistic cost and slippage assumptions
- Walk-forward results across research / validation / final test
- Performance report: Sharpe, win rate, drawdown, turnover
- Trades log (schema to be defined in Module 4)
- Comparability against v1's failed backtest (mean 20-day fwd −1.20%, win rate 43.75%)
**Contract to Module 5:**
- A verified signal-generating pipeline with historical performance
- Position sizing rules validated out-of-sample
- Execution assumptions documented
**Does NOT:**
- Retrain or retune features
- Introduce new signals
- Optimize on the final test period
**Open items for Module 4 chat:**
- Slippage model (DSE liquidity constraints)
- Commission structure
- Rebalance cadence
- Position cap per sector / per instrument
---
## Module 5 — Live Deployment
**Consumes:**
- Signal-generating pipeline from Module 3
- Backtest-validated execution rules from Module 4
- Live endpoints #4 (get-once) and #10 (DSE official)
**Produces:**
- Daily post-market script that pulls the day's data and writes today's rankings
- Output files (CSV / JSON) for dashboard consumption
- Monitoring logs (via `load_log` + a new live-run log)
- Positions tracking (new table if needed)
**Does NOT:**
- Execute real trades (manual execution for now)
- Change signal logic
- Touch the historical database schema
**Open items for Module 5 chat:**
- Where outputs are written (filesystem path)
- What format the PHP dashboard expects
- Monitoring / alerting policy
- Recovery for missed runs (partial-row backfill from market_snapshot)
---
## Module 6 — ML/AI Layer (last, only if justified)
**Consumes:**
- Surviving feature set from Module 2
- Historical labels (forward returns from Module 1 data)
**Produces:**
- Trained ML model(s) on the validated feature set
- Out-of-sample performance report
- Decision: keep or drop based on improvement over Module 3 baseline
**Contract:**
- A model is kept only if it beats the Module 3 signal on validation by a documented margin
**Does NOT:**
- Introduce features not validated in Module 2
- Override the kill criteria
- Replace Module 3 unless it clearly outperforms
**Open items for Module 6 chat:**
- Model class selection (tree-based vs linear)
- Feature importance validation
- Explainability via SHAP
---
## Cross-module conventions
- **Reproducibility:** every module logs `git rev-parse HEAD` at the start of a run.
- **No silent exception swallowing.** Every `except` clause either re-raises or logs at ERROR level with context.
- **Logging:** Python `logging` module, format `'%(asctime)s [%(levelname)s] %(message)s'`.
- **DB access:** via `pandas.read_sql` or `mysql-connector-python`; credentials from `.env`.
- **No absolute paths in code.** Paths derived from `Path(__file__).resolve().parents[N]`.
- **One change at a time.** Verify after each.
- **Every module ends with a commit and a HANDOFF.md update.**
---
## How to open the next module's chat
At the top of each new module chat, paste:
1. `CONTEXT.md`
2. `HANDOFF.md`
3. `INTERFACES.md`
4. `ENDPOINT_AUDIT.md`
5. Any output files produced since the previous handoff
The first message should state which module and which sub-step is being started.
---
## Change log
- 2026-10-06: Initial version (Module 0 completion).
