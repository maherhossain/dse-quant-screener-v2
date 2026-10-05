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
