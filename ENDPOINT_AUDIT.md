# DSE Quant v2 — Endpoint Audit

Purpose: document what each API endpoint actually returns, in what format,
with what quality. Every entry is based on a **live probe** saved under
`audit/raw/` (git-ignored). This file is the source of truth for schema design
in Module 0 and pipeline design in Module 1.
Legend:

- ✅ usable — clean, parseable, sufficient coverage
- ⚠️ unreliable — usable with caveats (rate-limited, sparse, needs headers, etc.)
- ❌ blocked — cannot use (auth required, geo-blocked, gone)

---

## Summary table

| #   | Endpoint                                          | Method | Status    | Format    | Verdict   | Notes                    |
| --- | ------------------------------------------------- | ------ | --------- | --------- | --------- | ------------------------ |
| 1   | `https://stocknow.com.bd/api/v1/sectors`          | GET    | 200       | JSON      | ✅        | 23 sectors. See entry 1. |
| 2   | `https://provider.bullbd.com/shares/get-names-tv` | GET    | (pending) | (pending) | (pending) | See entry 2.             |

---

## Entry 1 — stocknow.com.bd /api/v1/sectors

- **URL:** `https://stocknow.com.bd/api/v1/sectors`
- **Method:** GET
- **Headers required:** none (plain request worked, no User-Agent needed)
- **HTTP status:** 200 OK
- **Content-Type:** application/json
- **Body size:** 861 bytes
- **Raw file:** `audit/raw/20261005-172911__stocknow.com.bd__api_v1_sectors__da39a3ee.json`

### Structure

Top-level: JSON **object**, 23 keys. Each key is a stringified id; each value is
`{"id": <int>, "name": "<string>"}`.

### Fields

| Field | Type | Notes                         |
| ----- | ---- | ----------------------------- |
| id    | int  | Sector id, ranges 1–22 and 25 |
| name  | str  | Sector name                   |

### Sectors returned (as-is)

1 Bank, 2 Cement, 3 Ceramics Sector, 4 Corporate Bond, 5 Debenture,
6 Engineering, 7 Financial Institutions, 8 Food & Allied, 9 Fuel & Power,
10 Insurance, 11 IT Sector, 12 Jute, 25 Life Insurance, 13 Miscellaneous,
14 Mutual Funds, 15 Paper & Printing, 16 Pharmaceuticals & Chemicals,
17 Services & Real Estate, 18 Tannery Industries, 19 Telecommunication,
20 Textile, 21 Travel & Leisure, 22 Treasury Bond

### Data quality

- ✅ Clean JSON, no nulls, no duplicates.
- ⚠️ Keys are **not in numeric order** (25 appears between 12 and 13). Parse by
  iterating, not by assuming order.
- ⚠️ 23 sectors returned, not 22 as the CONTEXT.md note said. The note is
  off by one; the API returns 23 including "Life Insurance" (id 25) as a
  separate entry from "Insurance" (id 10). Confirm whether CONTEXT.md should
  be updated to 23.
- Note: contains non-equity sectors (Corporate Bond, Debenture, Mutual Funds,
  Treasury Bond). These will need to be filtered out of the equity universe
  during Module 1 — they are not swing-trade candidates for H1–H3.

### Verdict

✅ **Usable.** Authoritative sector taxonomy. Will be loaded into a `sectors`
table in Module 1 and used for sector classification throughout.

---

## Entry 2 — provider.bullbd.com /shares/get-names-tv

- **URL:** `https://provider.bullbd.com/shares/get-names-tv`
- **Method:** GET
- **Headers required:** none
- **HTTP status:** 200 OK
- **Content-Type:** application/json; charset=utf-8
- **Body size:** 53,733 bytes
- **Raw file:** `audit/raw/20261005-175452__provider.bullbd.com__shares_get-names-tv__da39a3ee.json`

### Structure

Top-level: JSON **array**, length **536**. Each element: `code`, `name`, `sector`, `type`, `category`.

### Fields

| Field    | Type       | Nulls | Notes                               |
| -------- | ---------- | ----- | ----------------------------------- |
| code     | str        | 0     | Unique (0 duplicates). Natural key. |
| name     | str / null | 130   | Full name.                          |
| sector   | str / null | 130   | 22 distinct non-null sector names.  |
| type     | str / null | 33    | See distribution below.             |
| category | str / null | 33    | See distribution below.             |

### Type distribution (536 total)

| type   | count | routing decision                                            |
| ------ | ----- | ----------------------------------------------------------- |
| EQ     | 359   | Equities — swing universe candidate                         |
| GOVDBT | 71    | Government bonds — exclude from equities                    |
| MF     | 37    | Mutual funds — exclude                                      |
| IDX    | 24    | **Indices** — route to `index_data` table, not equity table |
| CB     | 12    | Corporate bonds — exclude                                   |
| null   | 33    | Mixed — inspect (see below)                                 |

### Type = IDX breakdown (24 rows)

All 24 have `name = null`, `sector = null`. Codes:

- Broad/derived indices: `DSEX`, `DS30`, `DSES`
- 22 sector-level indices: `Bank`, `Cement`, `Ceramics Sector`, `Corporate Bond`, `Engineering`, `Financial Institutions`, `Food & Allied`, `Fuel & Power`, `Insurance`, `IT Sector`, `Jute`, `Life Insurance`, `Miscellaneous`, `Mutual Funds`, `Paper & Printing`, `Pharmaceuticals & Chemicals`, `Services & Real Estate`, `Tannery Industries`, `Telecommunication`, `Textile`, `Travel & Leisure`
- ⚠️ **Note:** the code field for sector indices is the _sector name string_, not a ticker. That's why they show up as `code` = "Bank", "Cement", etc.

### Type = null breakdown (33 rows)

Mixed bag. Groups:

- Bonds/debentures: `1STBSRS`, `1STICB`–`8THICB`, `ACIZCBOND`, `BRACSCBOND`, `CBLPBOND`, `MBPLCPBOND`, `UCB2PBOND`
- Legacy synthetic indices: `DGENX`, `BXSYNTH`
- Mutual funds: `AIMS1STMF`, `GRAMEEN1`, `ICB1STNRB`, `ICB2NDNRB`, `ICBISLAMIC`, `NLI1STMF`, `SEBL1STMF`
- **Real equities BullBD fails to classify:** `BDSERVICE`, `GLAXOSMITH`, `MODERNDYE`, `MONNOSTAF`, `SAVAREFR`, `SPPCL`, `UNITEDAIR`, and `CDSET` (possibly not an equity — verify)

### Category distribution (536 total)

A=304, Z=123, B=74, N=2, null=33.

### Data quality

- ✅ Zero duplicate codes.
- ⚠️ 130 rows have null name+sector. Includes the 33 null-type rows plus 97 others — verify count breakdown later.
- ⚠️ `type` is **not authoritative** for equity classification. At least 7–8 real equities are in the null-type bucket. Module 1 should combine `type='EQ'` with an explicit allow-list of unclassified real equities.
- ⚠️ `type='IDX'` rows are indices and must be routed to a separate `index_data` table, not `instruments`. Their `code` field is a display name (e.g. "Fuel & Power"), not a short ticker.
- ⚠️ Non-equity instruments (GOVDBT, MF, CB, and most null-type) must be filtered out before any equity screening.

### Verdict

✅ **Usable** as instrument master, with these Module 1 rules:

- **Equities:** `type='EQ'` **plus** manual allow-list of ~7 unclassified equities.
- **Indices:** `type='IDX'` → `index_data` table. Broad = `DSEX`, `DS30`, `DSES`; sector indices keyed by name.
- **Exclude:** `GOVDBT`, `MF`, `CB`, and non-equity nulls.
- **Category** kept as filterable attribute; do NOT exclude Z at load time.

---

## Entry 3 — stocknow.com.bd /api/v1/instruments

- **URL:** `https://stocknow.com.bd/api/v1/instruments`
- **Method:** GET
- **Headers required:** none
- **HTTP status:** 200 OK
- **Content-Type:** application/json
- **Body size:** 349,198 bytes
- **Raw file:** `audit/raw/20261005-180632__stocknow.com.bd__api_v1_instruments__da39a3ee.json`

### Structure

Top-level: JSON **object**, **473 keys**. Each key is a ticker code (or, for sector
indices, a sector name string); each value is a flat daily-snapshot object.

### Fields (per instrument)

| Field                         | Type | Meaning                                                                | Nulls      |
| ----------------------------- | ---- | ---------------------------------------------------------------------- | ---------- |
| sector_id                     | int  | FK to `/api/v1/sectors`; **23 = Index bucket, not listed in /sectors** | 22         |
| code                          | str  | Ticker                                                                 | 0          |
| name                          | str  | Full name                                                              | 1          |
| spot                          | num  | Live price (0 after-hours)                                             | 0          |
| category                      | str  | A / B / Z / SME / N / ""                                               | 33         |
| open, high, low, close        | num  | Today's OHLC                                                           | 9,10,10,10 |
| 7d, 15d, 30d, 90d, 180d, 365d | num  | Price N calendar days ago (not MAs)                                    | 9 each     |
| ycp                           | num  | Yesterday's close                                                      | 9          |
| trades                        | int  | Today's trade count                                                    | 9          |
| volume                        | int  | Today's share volume (**raw shares**)                                  | 9          |
| value                         | num  | Today's trade value (**millions BDT — CONFIRMED**)                     | 9          |
| yearly_high, yearly_low       | num  | 52-week range                                                          | 12         |
| floor                         | num  | Current floor price (0 = none); **NOT historical**                     | 49         |
| nv                            | num  | Probably NAV (funds) — **UNVERIFIED**                                  | 20         |
| new_value                     | num  | **UNVERIFIED**                                                         | 70         |
| sme                           | int  | SME board flag (0/1)                                                   | 0          |
| analysisTitle                 | str  | Bangla commentary — **ignore for quant**                               | 49         |
| updated_at                    | str  | 'YYYY-MM-DD HH:MM:SS' — last update                                    | 0          |

### `value` unit — CONFIRMED

`implied_price = value * 1e6 / volume` gives plausible DSE prices:

- ACI → 181.15, BATBC → 221.30, BEXIMCO → 20.07, BRACBANK → 64.85,
  GP → 240.45, SQURPHARMA → 217.50
  **`value` is in millions of BDT.** Matches BullBD `vl`.

### Category distribution (473)

A=213, Z=125, B=74, **SME=20**, N=5, ""=3, null=33.
Disagrees with endpoint #2 (A=304, Z=123, B=74, N=2, null=33). Stocknow
splits SME out; BullBD does not. Module 1 must reconcile.

### Sector linkage

Present `sector_id`s: {1..22, 23, 25, None}.

- **Orphan `sector_id = 23`** — belongs to `DSEX`, `DS30`, `DSES` (indices).
  `/api/v1/sectors` does not list id 23. **Data-quality flag on endpoint #1.**
- **`sector_id = None`** — 22 sector-index rows keyed by sector name (e.g.
  key = "Bank"). These duplicate the sector indices already present elsewhere.

### Dead/suspended instruments (10 rows)

Filter by `updated_at` staleness. All 10 stale rows have `updated_at = 2025-04-30`:
DEBARACEM, DEBBDLUGG, DEBBDWELD, DEBBDZIPP, DEBBXDENIM, DEBBXFISH, DEBBXKNI,
DEBBXTEX, Debenture (literal key), MTBPBOND.
Two of these (DEBBXDENIM, DEBBXKNI) have **stale non-null 7d–365d values**
(1450, 900) — would poison naive features. **Staleness filter is mandatory.**

### Universe vs endpoint #2 (BullBD names)

- in both: 444
- only in stocknow (29): mostly debentures + a handful of equities
  (`ACHIASF`, `AMPL`, `AOPLC`, `APEXWEAV`, `BDPAINTS`, `CRAFTSMAN`, `HIMADRI`,
  `KBSEED`, `KFL`, `MAMUNAGRO`, `MASTERAGRO`, `MKFOOTWEAR`) + the malformed
  key `"Debenture"`
- only in BullBD (92): bonds, MFs, unclassified equities (`CDSET`,
  `MODERNDYE`, `SLIPLC`, `SPPCL`)
  **Conclusion: neither endpoint alone is complete. Module 1 must union.**

### Data quality

- ✅ Clean JSON, all documented fields present on most rows.
- ⚠️ Two sector-index representations (ticker-keyed with sector_id=23 vs
  name-keyed with sector_id=None) — dedupe needed.
- ⚠️ `updated_at` is the primary freshness signal. Use it as a hard filter
  in Module 1 (drop anything not updated within last N trading days).
- ⚠️ Malformed placeholder row `code="Debenture"` (all nulls except trades/volume/value = 0).
- ⚠️ `floor` is current, not historical — useless for backtest floor detection.
- ⚠️ `nv`, `new_value` semantics unknown — **do not use in features until verified.**
- ⚠️ `category` disagrees with endpoint #2 on A/SME — Module 1 must reconcile.

### Verdict

✅ **Usable** as the daily snapshot source. This is the primary source for:

- today's OHLCV (cross-check with endpoint #4 `get-once`)
- historical price offsets (7/15/30/90/180/365d) — but these are **calendar days,
  not trading days** — verify
- 52-week high/low
- category, sector_id, SME flag
  **Not** the source for:
- historical daily bars (that's endpoints #6, #7)
- floor-period detection (use DSEX + known BSEC dates)
- anything relying on `nv`/`new_value` until semantics are verified

---
## Entry 4 — provider.bullbd.com /shares/get-once
- **URL:** `https://provider.bullbd.com/shares/get-once`
- **Method:** GET
- **Headers required:** none
- **HTTP status:** 200 OK
- **Content-Type:** application/json; charset=utf-8
- **Body size:** 150,500 bytes
- **Raw file:** `audit/raw/20261005-181655__provider.bullbd.com__shares_get-once__da39a3ee.json`
### Structure
Top-level: JSON **array**, length **503**. One object per currently-active instrument.
### Fields (per instrument)
| Field | Type | Meaning | Nulls | Verified? |
|-------|------|---------|-------|-----------|
| c | str | Ticker code | 0 | ✅ |
| q | str | **Composite: `{category}-{type}`** (e.g. `A-EQ`, `Z-EQ`, `A-MF`, `A-IDX`, `A-GOVDBT`, `A-CB`, `N-CB`) | 0 | ✅ |
| o | num | Open (today) | 0 | ✅ |
| h | num | High (today) | 0 | ✅ |
| l | num | Low (today) | 0 | ✅ |
| ltp | num | Last traded price; **0 if no trade** | 0 | ✅ |
| sp | num | Snapshot price (used when ltp=0) | 0 | ✅ |
| cp | num | **Closing price — use this as today's close** | 0 | ✅ |
| ycp | num | Yesterday's close | 0 | ✅ |
| price_change | num | Abs price change today | 0 | ✅ |
| price_change_per | num | % price change today | 0 | ✅ |
| tr | int | Trade count today | 0 | ✅ |
| v | int | Volume today (raw shares) | 0 | ✅ |
| vl | num | **Value today (millions BDT — CONFIRMED)** | 0 | ✅ |
| t | str | ISO 8601 UTC timestamp ("...Z"); DSE = UTC+6 | 0 | ✅ |
| changed | bool | Moved today? | 37 null | ✅ |
| halt | str | `''` normal, `halt:l` / `~halt:l` halted, null unstated | 24 null | ✅ |
| vn | num | Unverified (likely NAV for funds) | 0 | ❌ |
| trn | int | Unverified | 0 | ❌ |
| vln | num | Unverified (≈ vl/v ratio?) | 0 | ❌ |
| tradedAfterSec | int | Unverified — seconds since some reference | 0 | ❌ |
| changeNew | num | Unverified | 0 | ❌ |
### Type agreement with endpoint #2
`q.split('-', 1)` gives (category, type). Type distribution from `q`:
EQ=359, GOVDBT=71, MF=37, IDX=24, CB=12. **Exactly matches BullBD `/shares/get-names-tv` counts.**
Category from `q`: A, B, Z, N — **does NOT include SME** (stocknow's SME=20 are folded into A or B here).
### `vl` unit — CONFIRMED
`implied = vl * 1e6 / v` matches `ltp` for ACI (181.15 vs 181), BEXIMCO (20.07 vs 19.9),
GP (240.45 vs 240.2), SQURPHARMA (217.50 vs 217.6), BATBC (221.30 vs 221),
BRACBANK (64.85 vs 65). **`vl` is in millions of BDT.**
### `cp` vs `ltp`
When `ltp > 0`, `cp == ltp`. When no trade occurred (`ltp = 0`), `cp = sp`.
**Use `cp` as the daily close.** `ltp` can legitimately be 0.
### `halt` values
`''` = 469 (normal), `null` = 24, `halt:l` = 8, `~halt:l` = 2.
The 10 halted rows include real equities: `FAREASTFIN`, `FASFIN`, `ILFSL`,
`PREMIERLEA` (all Z), `TECHNODRUG` (A), plus 3 T-bonds, 1 MF, 1 CB.
### Timestamps
`t` is ISO 8601 **UTC** ("...Z"). DSE operates in UTC+6 (BST).
One stale row (`ABBLPBOND`, `t = 2026-06-10`) shows `get-once` is not a strict
"updated today" filter — some suspended rows persist. **Freshness filter needed.**
### Universe vs other endpoints
- get-once: 503
- stocknow instruments: 473
- bullbd names: 536
- **in all 3: 431**
- **only in get-once: 0** — get-once ⊂ (stocknow ∪ names)
- **in names not get-once: 33** — the dead/unclassified set (1STICB family,
  BDSERVICE, CDSET, GLAXOSMITH, MODERNDYE, MONNOSTAF, SAVAREFR, etc.)
### Data quality
- ✅ Zero nulls on all price/volume/timestamp fields.
- ✅ Field names compact but unambiguous.
- ⚠️ `vn`, `trn`, `vln`, `tradedAfterSec`, `changeNew` — **do not use until verified.**
- ⚠️ `q` is derived; parse to (category, type), don't store as-is.
- ⚠️ `t` is UTC — convert to BST (or store UTC + tz) consistently in Module 1.
- ⚠️ `get-once` excludes the 33 dead codes — useful as a live filter but
  **not** as the historical universe definition.
- ⚠️ 24 null-`halt` rows + 10 non-empty-`halt` rows — filter for live trading.
### Verdict
✅ **Usable** as the primary live-snapshot endpoint. This is the fastest way
to get today's OHLCV + trades for the whole market in a single call.
**Daily sync (Module 1) should use this.**
Not the source for:
- historical daily bars (endpoints #6, #7)
- historical snapshots (this is "now" only)
- dead/delisted instruments (use endpoints #2/#3 for those)
---
## Entry 5 — provider.bullbd.com /eod/get-eop-data-by-code?code=DSEX
- **URL:** `https://provider.bullbd.com/eod/get-eop-data-by-code?code=DSEX`
- **Method:** GET
- **Headers required:** none
- **HTTP status:** 200 OK
- **Content-Type:** application/json; charset=utf-8
- **Body size:** 4,425 bytes (invariant)
- **Raw file:** `audit/raw/20261005-195456__provider.bullbd.com__eod_get-eop-data-by-code__4c36c9f0.json`
- **Also tested:** `?code=ACI`, `?code=DSEX&period=1`, `?code=DSEX&limit=500`,
  `?code=DSEX&from=2014-01-01` — **all return identical shape and identical
  body for the same code. Query params `period`, `limit`, `from` are silently ignored.**
### Structure
Top-level: JSON **object**, 14 keys. Keys are **period lengths in days**:
`1, 5, 7, 10, 15, 18, 22, 30, 45, 60, 90, 125, 255, 365`.
Each value is a **rolling-window aggregate ending today** — NOT a time series.
### Fields (per period window)
| Field | Meaning |
|-------|---------|
| code | Ticker (same across all periods) |
| o | Open at start of window |
| c | Close at end of window (= today's close) |
| h | Highest high across window |
| l | Lowest low across window |
| t | Sum of trades across window |
| v | Sum of volume across window |
| vl | Sum of value across window (millions BDT) |
| d | Date of the window end (always today, ISO Z) |
| ltp | Last traded price (= today) |
| price_change | Change over the window |
| price_change_per | % change over the window |
| ycp | Close at start of window |
| period | Window length (matches the key) |
| avg_value | vl / period |
| avg_volume | v / period |
| avg_trade | t / period |
| avg_close | Mean close across window |
### Verdict
❌ **Not usable as a historical time-series source.** Returns rolling aggregates
as of *now*, with 14 fixed windows. Query parameters do not change the response.
**Usable only for:**
- ⚠️ **Sanity-check** — compare our independently-computed rolling features
  against these 14 windows for today. This is a legitimate use and worth doing
  once in Module 2.
- **NOT for feature construction** — as-of semantics of these windows are opaque
  (e.g. is "5" trading days or calendar days? confirmed only that `avg_value`
  = vl/5 for `period=5`, so it's a mechanical divisor, not a calendar). Using
  these to build features introduces leakage risk we can't audit.
**Implication for Module 1:**
DSEX daily history must come from a different endpoint. Candidates:
- Endpoint #6: `stocknow.com.bd/api/v1/instruments/DSEX/history`
- Endpoint #7: `provider.bullbd.com/shares/get-one-for-tv2?code=DSEX`
Those are audited next.
---
