# DSE Quant Screener v2 - Data Quality Report

**Module 1 close | 2026-10-06**
**Git HEAD at close:** `0e10d938a9fcec0fd15db814d7755f5cce261456`
**Database:** `dse_quant_v2` on localhost MySQL 8.x

This document records the state of the data pipeline at the close of
Module 1, including row counts, coverage, known gaps, and open questions
that Module 2 must account for.

---

## 1. Table row counts

| Table             | Rows    | Notes                                                     |
| ----------------- | ------- | --------------------------------------------------------- |
| sectors           | 24      | 23 from endpoint #1 + 1 synthetic (id=23 "Index")         |
| instruments       | 563     | Union of endpoint #2 (536) and #3 (473)                   |
| indices           | 24      | 3 broad + 21 sector                                       |
| daily_bars        | 1403248 | Equity OHLCV from endpoint #7; archive floor 2014-03-02   |
| index_bars        | 127419  | 24 indices, OHLC from endpoint #7; broad turnover from #6 |
| corporate_actions | 3670    | Endpoint #8; sparse (roughly 1/yr/stock); 412 instruments |
| block_trades      | 28024   | Endpoint #9; coverage 2023-06-21 onward only; 355 instr   |
| trading_calendar  | 4602    | Derived from DSEX index_bars; 2014-03-02 to today         |
| load_log          | 2809    | Audit trail for every load event                          |
| daily_snapshot    | 0       | Forward-only; first populated in Module 5                 |
| market_snapshot   | 0       | Forward-only; first populated in Module 5                 |

---

## 2. Instrument universe (563 total)

### By type

| Type   | Count | Note                                                       |
| ------ | ----- | ---------------------------------------------------------- |
| EQ     | 388   | Equity swing universe (primary for Module 2)               |
| CB     | 28    | Corporate bonds - excluded                                 |
| MF     | 44    | Mutual funds - excluded                                    |
| GOVDBT | 71    | Government debt - excluded                                 |
| IDX    | 1     | DGENX only (legacy synthetic index, kept for completeness) |
| NULL   | 31    | Mixed; mostly bonds/debentures and dead codes              |

### EQ by category

| Category | Count |
| -------- | ----- |
| A        | 165   |
| B        | 74    |
| Z        | 125   |
| NULL     | 24    |

### EQ by SME flag

| is_sme | Count |
| ------ | ----- |
| 0      | 368   |
| 1      | 20    |

### Instrument reconciliation (endpoint #2 vs #3)

- In both: 420
- Only in endpoint #2: 91
- Only in endpoint #3: 52
- Rejected at load: `CDSET`, `Debenture` (malformed key)
- Manual type overrides applied: 8 real equities whose BullBD `type`
  was NULL (BDSERVICE, BXSYNTH, GLAXOSMITH, MODERNDYE, MONNOSTAF,
  SAVAREFR, SPPCL, UNITEDAIR)

---

## 3. Coverage and date ranges

### daily_bars

- Total bars: 1,403,248
- Distinct instruments: 367 of 388 EQ
- Date range: 1999-01-02 to 2026-10-06 (see section 6 for pre-2013 note)
- 21 EQ instruments have zero bars (empty payload from endpoint #7)

### index_bars

Per-index coverage, earliest to latest:

| Index                       | Bars | Min date   | Max date   |
| --------------------------- | ---- | ---------- | ---------- |
| DSEX                        | 2693 | 2014-03-02 | 2026-10-06 |
| DS30                        | 2605 | 2014-11-10 | 2026-10-06 |
| DSES                        | 2562 | 2014-11-10 | 2026-10-05 |
| Bank                        | 6531 | 2000-01-01 | 2026-10-06 |
| Cement                      | 6527 | 2000-01-01 | 2026-10-06 |
| Ceramics Sector             | 6470 | 2000-01-01 | 2026-10-06 |
| Corporate Bond              | 3866 | 2007-11-28 | 2026-10-06 |
| Engineering                 | 6539 | 2000-01-01 | 2026-10-06 |
| Financial Institutions      | 6488 | 2000-01-01 | 2026-10-06 |
| Food & Allied               | 6494 | 2000-01-01 | 2026-10-06 |
| Fuel & Power                | 6509 | 2000-01-01 | 2026-10-06 |
| Insurance                   | 6333 | 1999-12-29 | 2026-10-06 |
| IT Sector                   | 5663 | 2000-02-06 | 2026-10-06 |
| Jute                        | 4427 | 2007-01-03 | 2026-10-06 |
| Life Insurance              | 5197 | 1999-02-04 | 2026-10-06 |
| Miscellaneous               | 6513 | 2000-01-01 | 2026-10-06 |
| Mutual Funds                | 4310 | 2008-09-08 | 2026-10-06 |
| Paper & Printing            | 4242 | 2000-01-21 | 2026-10-06 |
| Pharmaceuticals & Chemicals | 6512 | 2000-01-01 | 2026-10-06 |
| Services & Real Estate      | 6504 | 2000-01-01 | 2026-10-06 |
| Tannery Industries          | 6524 | 2000-01-01 | 2026-10-06 |
| Telecommunication           | 4022 | 2009-11-15 | 2026-10-06 |
| Textile                     | 6501 | 2000-01-01 | 2026-10-06 |
| Travel & Leisure            | 3387 | 2012-07-02 | 2026-10-06 |

Broad indices only go back to 2014 due to endpoint #7 archive floor.
Sector indices extend further back (from ~2000) because endpoint #7's
per-code archive includes earlier data for those codes.

### corporate_actions

- Total rows: 3,670
- Distinct instruments with at least one event: 412 of 563
- Publish date range: 2013-10-27 to 2026-10-06
- Record date range (excluding sentinels): 1999-11-30 to 2026-10-30
- 151 instruments returned empty payload
- ~11 duplicate (instrument_id, news_id) pairs collapsed by upsert

### block_trades

- Total rows: 28,024
- Distinct instruments: 355 of 388 EQ
- Date range: 2023-06-21 to 2026-10-06
- Coverage floor is fixed by the source (BullBD began recording 2023-06-21)
- 33 EQ instruments returned empty payload

### trading_calendar

- Range: 2014-03-02 to 2026-10-06
- 2,693 trading days
- 1,310 weekend days (Fri/Sat)
- 599 non-trading weekdays (Mon-Thu; notes = "no DSEX bar")

---

## 4. Data-quality findings

### 4.1 OHLC constraint violations in source data

A small fraction of source rows have OHLC values that violate the
universal identity `high >= low`, `high >= open`, `high >= close`,
`low <= open`, `low <= close`. These rows are dropped at load time.

Approximate magnitudes:

- daily_bars: 666 rows dropped out of ~1.40M (~0.05%)
- index_bars: ~1,300 rows dropped across 24 indices (~1%)

Examples from index_bars (source values, not our bug):

- DSEX 2014-03-18: close < low
- DSES 2021-11-09: high ~2x surrounding days
- IT Sector 2000-01-28: high/low wildly divergent from open/close

Policy: silent drop, logged at WARNING level per instrument, counted in
`load_log.rows_skipped`. Recorded here per decision 2026-10-06.

### 4.2 Corporate-action null sentinels

Endpoint #8 uses multiple near-epoch sentinel values to signal "no date":

- 1969-12-31T18:00:00Z
- 1969-12-31T23:00:00Z
- 1970-01-01T00:00:00Z
- 1970-01-01T12:00:00Z

After the +1 day shift that `year_ended_on`, `agm_date`, and `record_date`
require, these land on 1970-01-01 or 1970-01-02. All are filtered to NULL
at load time. Verified after the 1g.1b fix: zero rows in any of the three
date columns fall at or below 1970-01-02.

### 4.3 Endpoint #8 duplicate news_ids

111 (instrument_id, news_id) collisions were observed in the source.
The unique key on corporate_actions collapsed them; only the latest
version of each news_id is stored. Rows inserted vs rows in table:
3,781 vs 3,670. Accepted per decision 2026-10-06.

### 4.4 DSEX gap-fill returned 0 bars

Endpoint #6 was expected to provide DSEX OHLC for 2013-01-28 through
2014-03-01 (the window before endpoint #7's archive floor). It returned
0 bars in that window. Unexplained. Deferred to end of Module 1 review.

Status at Module 1 close: unresolved. Consequences: DSEX history in
index_bars begins 2014-03-02, not 2013-01-28.

### 4.5 Endpoint #7 URL encoding

Codes containing spaces and special characters (e.g. `Food & Allied`,
`Pharmaceuticals & Chemicals`) must be URL-encoded before being placed
in the `code=` query parameter. Fixed during Module 1e. Without encoding,
the endpoint returns a payload lacking the expected OHLC keys.

### 4.6 Pre-2013 bars in daily_bars

Endpoint #7 returns per-instrument history extending to listing date.
For long-listed equities this reaches 1999-01-02, well before the study
start of 2013-01-28.

Decision (2026-10-06): keep pre-2013 bars in daily_bars. Module 2 must
filter by `trade_date >= '2013-01-28'` when computing features. The
loader is faithful to the source; filtering is downstream.

### 4.7 Pre-archive DSEX gap (2013-01-28 to 2014-03-01)

Related to 4.4. Even if the gap-fill succeeds in a future attempt, the
DSEX regime signal currently begins 2014-03-02.

The 2013-01-28 to 2014-03-01 window is not represented in
trading_calendar (which starts at the first DSEX bar). Module 2 must
not assume trading_calendar coverage extends to 2013-01-28.

### 4.8 Empty-payload instruments (21 EQ)

The following EQ instruments returned empty payloads from endpoint #7
for daily_bars. They exist in `instruments` but have zero bars:

ACHIASF, AMPL, AOPLC, APEXWEAV, BDPAINTS, BENGALBISC, BXSYNTH,
CRAFTSMAN, HIMADRI, KBSEED, KFL, MAMUNAGRO, MASTERAGRO, MKFOOTWEAR,
MOSTFAMETL, NIALCO, ORYZAAGRO, SADHESIVE, SLIPLC, WEBCOATS,
WONDERTOYS.

Note: this list is from the load log; exact membership may differ by
one or two entries. Module 2 must not assume every EQ instrument in
`instruments` has daily bars.

### 4.9 Sparse-coverage instruments

BDSERVICE has only 8 bars total (2012-03-20 to 2023-10-26), representing
a long-suspended stock with occasional trades. SLIPLC has 24 bars
(2026-04-06 to 2026-05-10). Module 2 must apply a minimum bar-count
universe filter before computing features.

### 4.10 Block-trade archive floor

Block-trade data begins 2023-06-21 across all tested instruments. This
is a source-level constraint, not a per-instrument one. H2 (block
activity) cannot be researched on 2013-2023 data. Module 2 must treat
H2 as a live-only hypothesis or replace it with a pre-2023 proxy.

### 4.11 DSE floor period (2022 Q3 - 2023 Q4)

The BSEC imposed a price floor from roughly July 2022 to late 2023.
This affects daily_bars between 2022-07 and 2023-12. Context already
excludes 2022 Q3 - 2023 Q4 from backtests. Module 2 must encode this
explicitly.

---

## 5. Endpoint usage summary

| Endpoint # | URL                                               | Feeds                             |
| ---------- | ------------------------------------------------- | --------------------------------- |
| 1          | stocknow.com.bd/api/v1/sectors                    | sectors                           |
| 2          | provider.bullbd.com/shares/get-names-tv           | instruments, indices (IDX subset) |
| 3          | stocknow.com.bd/api/v1/instruments                | instruments                       |
| 4          | provider.bullbd.com/shares/get-once               | (forward-only; Module 5)          |
| 6          | stocknow.com.bd/api/v1/instruments/{code}/history | index_bars turnover; gap-fill     |
| 7          | provider.bullbd.com/shares/get-one-for-tv2        | daily_bars, index_bars OHLC       |
| 8          | provider.bullbd.com/corporate-actions/...         | corporate_actions                 |
| 9          | provider.bullbd.com/shares/get-block-share        | block_trades                      |
| 10         | www.dse.com.bd/api/live/market                    | (forward-only; Module 5)          |

Endpoints #5 and #11/#12 were rejected per ENDPOINT_AUDIT.md.

---

## 6. Open questions carried into Module 2

1. DSEX gap-fill (2013-01-28 to 2014-03-01) - unresolved. Investigate
   before relying on DSEX regime features before 2014-03.

2. Minimum bar-count filter for the universe. What threshold? 500 bars?
   1,000? Depends on feature window requirements.

3. Floor-period handling. Exclude 2022-07 to 2023-12 outright? Flag and
   mask? Module 2 decides.

4. Corporate-action adjustment policy. daily_bars prices are unadjusted.
   Does Module 2 need dividend/split adjustment before computing returns?
   Likely yes for features that span record dates.

5. H2 (block activity) testability. Only 2023-06-21+ data exists. Confirm
   live-only status or identify a pre-2023 proxy.

6. Pre-2013 bars. Confirm Module 2 filters `trade_date >= '2013-01-28'`
   for all features. No exceptions unless justified.

7. Sector indices pre-2000. Several sector indices have bars back to
   2000, but the study start is 2013-01-28. Confirm Module 2 also
   filters index_bars.

---

## 7. Reproducibility

Every load records: run_id, started/finished timestamps, target table,
source provider and endpoint, scope date range, rows inserted/skipped/
failed, status, error message, git commit hash, hostname, and raw cache
file reference (in `load_log`).

Raw HTTP responses are cached under `audit/raw/` with a deterministic
filename: `{UTC timestamp}__{url_slug}__{sha256_prefix8}.json`.
The `audit/raw/` directory is git-ignored; raw payloads are machine-local.

---

_End of report. Next update at Module 2 close._
