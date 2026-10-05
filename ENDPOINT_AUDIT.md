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
