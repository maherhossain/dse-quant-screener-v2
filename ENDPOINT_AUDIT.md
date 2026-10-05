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

| #   | Endpoint                                                                           | Method | Status    | Format | Verdict | Notes                                                                      |
| --- | ---------------------------------------------------------------------------------- | ------ | --------- | ------ | ------- | -------------------------------------------------------------------------- |
| 1   | `https://stocknow.com.bd/api/v1/sectors`                                           | GET    | 200       | JSON   | ✅      | 23 sectors. See entry 1.                                                   |
| 2   | `https://provider.bullbd.com/shares/get-names-tv`                                  | GET    | 200       | JSON   | ✅      | 536 instruments, 5 types. See entry 2.                                     |
| 3   | `https://stocknow.com.bd/api/v1/instruments`                                       | GET    | 200       | JSON   | ✅      | 473 instruments, daily snapshot. See entry 3.                              |
| 4   | `https://provider.bullbd.com/shares/get-once`                                      | GET    | 200       | JSON   | ✅      | 503 live snapshots. See entry 4.                                           |
| 5   | `https://provider.bullbd.com/eod/get-eop-data-by-code?code=DSEX`                   | GET    | 200       | JSON   | ❌      | Rolling period aggregates only. See entry 5.                               |
| 6   | `https://stocknow.com.bd/api/v1/instruments/{CODE}/history`                        | GET    | 200       | JSON   | ✅      | **Primary historical source.** Columnar OHLCV, back to ~2002. See entry 6. |
| 7   | `https://provider.bullbd.com/shares/get-one-for-tv2?code={CODE}`                   | GET    | (pending) |        |         | See entry 7.                                                               |
| 8   | `https://provider.bullbd.com/corporate-actions/get-corporate-actions?share={CODE}` | GET    | (pending) |        |         | See entry 8.                                                               |
| 9   | `https://provider.bullbd.com/shares/get-block-share?code={CODE}`                   | GET    | (pending) |        |         | See entry 9.                                                               |
| 10  | `https://www.dse.com.bd/api/live/market`                                           | GET    | (pending) |        |         | See entry 10.                                                              |
| 11  | `https://stocknow.com.bd/api/v1/instruments/{CODE}/history?resolution=1W`          | GET    | 200       | JSON   | ✅      | Same as #6 but weekly. Covered in entry 6.                                 |
| 12  | `https://stocknow.com.bd/api/v1/instruments/{CODE}/history?resolution=1M`          | GET    | 200       | JSON   | ✅      | Same as #6 but monthly. Covered in entry 6.                                |

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

| Field            | Type | Meaning                                                                                               | Nulls   | Verified? |
| ---------------- | ---- | ----------------------------------------------------------------------------------------------------- | ------- | --------- |
| c                | str  | Ticker code                                                                                           | 0       | ✅        |
| q                | str  | **Composite: `{category}-{type}`** (e.g. `A-EQ`, `Z-EQ`, `A-MF`, `A-IDX`, `A-GOVDBT`, `A-CB`, `N-CB`) | 0       | ✅        |
| o                | num  | Open (today)                                                                                          | 0       | ✅        |
| h                | num  | High (today)                                                                                          | 0       | ✅        |
| l                | num  | Low (today)                                                                                           | 0       | ✅        |
| ltp              | num  | Last traded price; **0 if no trade**                                                                  | 0       | ✅        |
| sp               | num  | Snapshot price (used when ltp=0)                                                                      | 0       | ✅        |
| cp               | num  | **Closing price — use this as today's close**                                                         | 0       | ✅        |
| ycp              | num  | Yesterday's close                                                                                     | 0       | ✅        |
| price_change     | num  | Abs price change today                                                                                | 0       | ✅        |
| price_change_per | num  | % price change today                                                                                  | 0       | ✅        |
| tr               | int  | Trade count today                                                                                     | 0       | ✅        |
| v                | int  | Volume today (raw shares)                                                                             | 0       | ✅        |
| vl               | num  | **Value today (millions BDT — CONFIRMED)**                                                            | 0       | ✅        |
| t                | str  | ISO 8601 UTC timestamp ("...Z"); DSE = UTC+6                                                          | 0       | ✅        |
| changed          | bool | Moved today?                                                                                          | 37 null | ✅        |
| halt             | str  | `''` normal, `halt:l` / `~halt:l` halted, null unstated                                               | 24 null | ✅        |
| vn               | num  | Unverified (likely NAV for funds)                                                                     | 0       | ❌        |
| trn              | int  | Unverified                                                                                            | 0       | ❌        |
| vln              | num  | Unverified (≈ vl/v ratio?)                                                                            | 0       | ❌        |
| tradedAfterSec   | int  | Unverified — seconds since some reference                                                             | 0       | ❌        |
| changeNew        | num  | Unverified                                                                                            | 0       | ❌        |

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

| Field            | Meaning                                      |
| ---------------- | -------------------------------------------- |
| code             | Ticker (same across all periods)             |
| o                | Open at start of window                      |
| c                | Close at end of window (= today's close)     |
| h                | Highest high across window                   |
| l                | Lowest low across window                     |
| t                | Sum of trades across window                  |
| v                | Sum of volume across window                  |
| vl               | Sum of value across window (millions BDT)    |
| d                | Date of the window end (always today, ISO Z) |
| ltp              | Last traded price (= today)                  |
| price_change     | Change over the window                       |
| price_change_per | % change over the window                     |
| ycp              | Close at start of window                     |
| period           | Window length (matches the key)              |
| avg_value        | vl / period                                  |
| avg_volume       | v / period                                   |
| avg_trade        | t / period                                   |
| avg_close        | Mean close across window                     |

### Verdict

❌ **Not usable as a historical time-series source.** Returns rolling aggregates
as of _now_, with 14 fixed windows. Query parameters do not change the response.
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

## Entry 6 — stocknow.com.bd /api/v1/instruments/{CODE}/history

- **URL pattern:** `https://stocknow.com.bd/api/v1/instruments/{CODE}/history?data2=true&resolution=1D&skip=N`
- **Method:** GET
- **Query params required:** `data2=true`, `resolution`, `skip` — **without them, response is empty HTML (0 bytes)**
- **HTTP status:** 200 OK
- **Content-Type:** application/json
- **Resolutions tested:** `1D`, `1W`, `1M` — all work
- **Sample raw files:**
  - `audit/raw/20261005-200130__stocknow.com.bd__api_v1_instruments_DSEX_history__faaa84c2.json` (DSEX skip=0)
  - `audit/raw/20261005-200425__stocknow.com.bd__api_v1_instruments_ACI_history__faaa84c2.json` (ACI skip=0)
  - `audit/raw/20261005-201708__stocknow.com.bd__api_v1_instruments_DSEX_history__e6b492ee.json` (DSEX skip=5500)

### Structure — **columnar, 6 arrays**

Top-level: JSON array of 6 arrays, all same length (up to 400 bars per page):
| Index | Field | Unit | Verified |
|-------|-------|------|----------|
| 0 | **open** | price | ✅ matches snapshot `open` |
| 1 | **high** | price | ✅ matches snapshot `high` |
| 2 | **low** | price | ✅ matches snapshot `low` |
| 3 | **close** | price | ✅ matches snapshot `close` |
| 4 | **volume** | raw shares | ✅ matches snapshot `volume` |
| 5 | **timestamp** | UTC midnight of trading day | ✅ ISO date recoverable |
**⚠️ Earlier misread:** I initially thought index 0 = close, 3 = open. That was wrong.
The correct mapping is **0=open, 1=high, 2=low, 3=close, 4=volume, 5=timestamp.**

### Pagination

- `skip=0` = most recent 400 bars
- `skip=N` = skip N most-recent bars, then return next 400 (going backward in time)
- Pages have **zero overlap** (verified with skip=0 and skip=1000)
- Empty pages return `[[],[],[],[],[],[]]` (19 bytes)

### Coverage (as of 2026-10-05)

| Instrument      | Oldest bar                        | Notes                                              |
| --------------- | --------------------------------- | -------------------------------------------------- |
| DSEX            | 2003-01-01 (1D)                   | **Pre-2013 data is DGEN, not DSEX** — see below    |
| ACI             | 2002-03-18 (1D)                   | Older companies have pre-2003 history              |
| ROBI            | Recent listing                    | Archive is per-instrument, bounded by listing date |
| DS30            | (pending)                         |                                                    |
| DSES            | (pending)                         |                                                    |
| Total DSEX bars | ~5,750 (from skip=0 to skip=5500) |                                                    |

### ⚠️ **CRITICAL: DSEX pre-2013 is contaminated**

DSEX was officially launched on **2013-01-28** with a rebased value of ~3,000.
The endpoint returns **pre-2013 values of 6,000–8,900** for "DSEX" — these
are **DGEN (DSE General Index)** values, not DSEX.
Detected by timestamp discontinuity:

- 2010-10 → 2012-11: values 6,000–8,700 (DGEN peak and crash)
- 2013-01-28 → present: DSEX baseline ~3,000
  **Rule for Module 1:** DSEX bars with date < 2013-01-28 must be **dropped**,
  or relabeled `DGEN`. Do NOT use as DSEX regime signal.

### Cross-check vs v1 `dse_quant_screener.index_data` (2025-02-03)

| Field  | Endpoint #6   | v1 index_data  |
| ------ | ------------- | -------------- |
| open   | 5126.15       | 5126.15 ✅     |
| high   | 5169.71       | 5169.71 ✅     |
| low    | 5131.07       | 5131.07 ✅     |
| close  | 5145.84       | 5145.84 ✅     |
| volume | 4,313,310,000 | 166,355,006 ⚠️ |

OHLC match exactly. **Volume definition differs:**

- Endpoint #6's DSEX `volume` ≈ whole-market share volume
- v1's DSEX `volume` = DSEX-constituent share volume (about 1/26 of #6's)
  **Module 1 decision:** use endpoint #6 for OHLC. Do not cross-validate volume
  between the two — different definitions. Regime features will rely on
  **price-based signals** (trend, drawdown, vol), not volume.

### Data quality

- ✅ OHLCV clean, no nulls observed in sampled pages
- ✅ Timestamps are exact dates (UTC midnight); trading-day calendar derivable
- ✅ Per-instrument, per-listing-date coverage (new listings start late, fine)
- ⚠️ DSEX pre-2013 contaminated with DGEN — filter
- ⚠️ DS30 / DSES launch dates not yet verified (pending)
- ⚠️ Empty page semantics = end of archive; no error response
- ⚠️ Rate limiting not yet tested — assume it exists; backfill with delay

### Verdict

✅ **PRIMARY HISTORICAL SOURCE** for Module 1. Single endpoint for:

- Daily OHLCV bars for any instrument (index or stock)
- Full history back to instrument listing (or archive start ~2002)
- Any resolution: `1D`, `1W`, `1M`
  **Study start:** 2013-01-28 (DSEX launch) — see CONTEXT.md.
  **Not usable for:**
- Pre-2013 DSEX as "DSEX" (it's DGEN)
- Anything requiring volume cross-checks against v1
  **Backfill plan (Module 1):**
- For each instrument, page through `skip=0, 400, 800, ...` until empty
- Estimated ~15 pages per instrument × ~430 instruments ≈ 6,500 calls
- Apply rate limiting (e.g. 1 req/s) → ~2 hours for full backfill
- Store raw JSON per page (audit-grade) then parse to DB

---
## Entry 7 — provider.bullbd.com /shares/get-one-for-tv2?code={CODE}
- **URL pattern:** `https://provider.bullbd.com/shares/get-one-for-tv2?code={CODE}`
- **Method:** GET
- **Headers required:** none
- **HTTP status:** 200 OK
- **Content-Type:** application/json; charset=utf-8
- **Sample raw files:**
  - `audit/raw/20261005-205639__provider.bullbd.com__shares_get-one-for-tv2__4c36c9f0.json` (DSEX)
  - `audit/raw/20261005-210514__provider.bullbd.com__shares_get-one-for-tv2__59370348.json` (ACI)
  - `audit/raw/20261005-211722__provider.bullbd.com__shares_get-one-for-tv2__33d9d7b7.json` (ROBI)
### Structure
Top-level: JSON **object**, 6 keys. Each value is a **flat array** of the same length:
| Key | Field | Unit | Notes |
|-----|-------|------|-------|
| o | open | price | verified vs snapshot |
| h | high | price | verified |
| l | low | price | verified |
| c | close | price | verified |
| v | volume | raw shares | see "volume semantics" below |
| d | timestamp | ms epoch (UTC midnight) | `1393718400000` = 2014-03-02 |
### Coverage
| Instrument | Bars | Coverage |
|------------|------|----------|
| DSEX | 3,001 | 2014-03-02 → 2026-10-05 |
| ACI | 3,001 | 2014-03-02 → 2026-10-05 |
| ROBI | 1,379 | 2020-12-24 → 2026-10-05 (IPO) |
**Global archive floor: 2014-03-02.** Per-instrument coverage bounded by IPO.
One call returns the entire history — no pagination.
### OHLC cross-validation vs endpoint #6
**2021-06-01 DSEX:**
| Field | Endpoint #7 | Endpoint #6 |
|-------|-------------|-------------|
| open | 5990.99 | 5990.99 ✅ |
| high | 6040.08 | 6040.08 ✅ |
| low | 5988.27 | 5988.27 ✅ |
| close | 5993.33 | 5993.33 ✅ |
| volume | 464,588,000 | 19,035,259,000 ⚠️ |
OHLC identical. Volume off by ~41×.
### ⚠️ Volume semantics
**Endpoint #7's DSEX `volume` = DSEX-constituent share volume** (matches v1 index_data).
**Endpoint #6's DSEX `volume` = whole-market share volume.**
For per-stock instruments (e.g. ACI), the two are expected to match — verify in Module 1.
### Data quality
- ✅ Single-call full history — vastly more efficient than #6 for backfill
- ✅ OHLC identical to endpoint #6 on all cross-checks
- ✅ Correct per-listing coverage (ROBI starts at IPO)
- ✅ Timestamps are ms epoch, UTC midnight — trivial to parse
- ⚠️ Archive floor 2014-03-02 — missing 2013-01-28 → 2014-03-01 (~230 trading days)
- ⚠️ Volume definition differs from #6 for indices — must be documented and never mixed
- ⚠️ Rate limiting not tested
### Verdict
✅ **PRIMARY BULK BACKFILL SOURCE** for Module 1.
- One HTTP call per instrument → ~430 calls total for full universe
- Backfill estimate: 5–15 minutes (vs ~2 hours via endpoint #6)
**Gap-fill source:** endpoint #6 for 2013-01-28 → 2014-03-01
**Volume caveat:** for DSEX/DS30/DSES, prefer endpoint #6's volume (market-wide);
for individual stocks, either is fine — confirm in Module 1.
---
## Entry 9 — provider.bullbd.com /shares/get-block-share?code={CODE}
- **URL pattern:** `https://provider.bullbd.com/shares/get-block-share?code={CODE}`
- **Method:** GET
- **Headers required:** none
- **HTTP status:** 200 OK
- **Content-Type:** application/json; charset=utf-8
- **Sample raw files:**
  - `audit/raw/20261005-212913__provider.bullbd.com__shares_get-block-share__59370348.json` (ACI, 115 rows)
  - `audit/raw/20261005-212951__provider.bullbd.com__shares_get-block-share__e8378573.json` (BEXIMCO, 427 rows)
  - `audit/raw/20261005-213012__provider.bullbd.com__shares_get-block-share__70c423ff.json` (SQURPHARMA, 270 rows)
### Structure
Top-level: JSON **array**, one object per block-trade day per instrument.
Length varies by instrument: ACI 115, BEXIMCO 427, SQURPHARMA 270.
### Fields (per row)
| Field | Type | Meaning | Notes |
|-------|------|---------|-------|
| _id | str | MongoDB ObjectId | ignore |
| code | str | Ticker | ✅ |
| date | str | "YYYY-MM-DD" (date string) | ✅ |
| __v | int | MongoDB version | ignore, always 0 |
| maxPrice | num | Highest block price that day | ✅ |
| minPrice | num | Lowest block price that day | ✅ |
| trades | int | Number of block trades | ✅ |
| value | num | Total block value, **millions BDT** | ✅ verified (`value * 1e6 / volume == price`) |
| volume | int | Total block shares | ✅ |
### Unit verification
ACI 2023-06-21: `volume=4175, maxPrice=minPrice=241, value=1.006`.
`1.006 * 1e6 / 4175 = 241.0` ✅ — matches price. **`value` is millions BDT.**
### Coverage — ⚠️ ALL TESTED STOCKS START 2023-06-21
| Instrument | Rows | First date |
|------------|------|------------|
| ACI | 115 | 2023-06-21 |
| BEXIMCO | 427 | 2023-06-21 |
| SQURPHARMA | 270 | 2023-06-21 |
**BullBD began recording block trades on 2023-06-21.** No pre-2023-06-21
block data exists in this endpoint, regardless of instrument.
### Data quality
- ✅ Clean JSON, no nulls observed
- ✅ Value unit confirmed
- ✅ Multi-trade days aggregated into one row (with `trades` count)
- ⚠️ Only one price range per day (`minPrice`/`maxPrice`) — no individual trade breakdown
- ⚠️ **No side indicator** (buy vs sell) — cannot distinguish accumulation from
  distribution from this endpoint alone
- ⚠️ **No participant identity** — cannot distinguish sponsor/director from
  third-party block
- ⚠️ **Coverage: 2023-06-21 → present only** (~2.5 years)
### Verdict
✅ **Usable, but with major caveat.**
- Data quality is high
- **Historical coverage is too short for H2 to be research-tested** on
  2013–2020 research or 2021–2023 validation periods
- H2 testable only on **2023-06-21 → present**, which falls entirely within
  the final test period (2024–2026) plus a sliver of validation
**Implications:**
1. H2 cannot be evaluated against the pre-committed kill criteria (which
   require validation-set IC ≥ 0.02). There is insufficient validation data.
2. Module 2 must decide:
   - **Keep H2 as a live-only hypothesis** — used in production but not backtested
   - **Replace H2 with a broader accumulation proxy** — e.g. volume+range based
   - **Drop H2 entirely**
3. The **concept** of block-trade activity remains viable as a *live* signal.
   It is not a research-testable feature.
**Recommendation:** record the finding, keep the endpoint for live deployment,
and let Module 2 evaluate whether H2's concept can be tested through a
different (pre-2023) proxy.
---
