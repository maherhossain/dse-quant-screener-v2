"""Load the indices reference table.
Source: https://provider.bullbd.com/shares/get-names-tv (endpoint #2),
        filtered to type='IDX'.
Produces: 24 rows in `indices` (3 broad: DSEX, DS30, DSES; 21 sector).
valid_from policy:
  - DSEX: 2013-01-28 hard requirement. Pre-launch DSEX archive is DGEN.
  - DS30, DSES: 2013-01-28 placeholder.
  - Sector indices: 2013-01-28 placeholder.
  Placeholders will be refined in Move 1d once actual first-bar dates are
  observed from the historical backfill.
sector_id linkage: sector indices are matched by name to `sectors.name`
(a UNIQUE column). Load fails loudly if any name does not match.
Idempotent: INSERT ... ON DUPLICATE KEY UPDATE on `code`.
Run: py -m src.loaders.load_indices
"""
from __future__ import annotations
import sys
from datetime import date
from typing import Any
from src import db, paths
from src.http_client import fetch_json
from src.logging_setup import setup_logging
LOG = setup_logging("load_indices")
SOURCE_PROVIDER = "provider.bullbd.com"
SOURCE_ENDPOINT = "https://provider.bullbd.com/shares/get-names-tv"
TARGET_TABLE = "indices"
STUDY_START = date(2013, 1, 28)
# Hard-coded broad index definitions. If endpoint #2 stops returning any of
# these, or returns something unexpected, the loader fails loudly.
BROAD_INDICES: dict[str, dict[str, Any]] = {
    "DSEX": {
        "name": "DSEX",
        "valid_from": date(2013, 1, 28),
        "notes": (
            "DSEX launched 2013-01-28; pre-launch archive is DGEN, not DSEX"
        ),
    },
    "DS30": {
        "name": "DS30",
        "valid_from": STUDY_START,
        "notes": "valid_from=study_start placeholder; refine in Move 1d",
    },
    "DSES": {
        "name": "DSES",
        "valid_from": STUDY_START,
        "notes": "valid_from=study_start placeholder; refine in Move 1d",
    },
}
def _extract_idx_rows(data: Any) -> list[dict[str, Any]]:
    """Filter endpoint #2's response to type='IDX' rows.
    Returns a list of dicts with keys: code, type. (name/sector are NULL
    for IDX rows per the endpoint audit.)
    """
    if not isinstance(data, list):
        raise ValueError(
            f"endpoint #2 response is not a list: {type(data).__name__}"
        )
    if not data:
        raise ValueError("endpoint #2 response is empty")
    idx_rows: list[dict[str, Any]] = []
    for i, entry in enumerate(data):
        if not isinstance(entry, dict):
            raise ValueError(
                f"endpoint #2 entry {i} is not an object: {type(entry).__name__}"
            )
        if entry.get("type") == "IDX":
            code = entry.get("code")
            if not isinstance(code, str) or not code.strip():
                raise ValueError(
                    f"IDX entry {i} has invalid code: {code!r}"
                )
            idx_rows.append({"code": code.strip()})
    if not idx_rows:
        raise ValueError("endpoint #2 returned zero type='IDX' rows")
    return idx_rows
def _classify(idx_rows: list[dict[str, Any]]) -> tuple[
    list[dict[str, Any]], list[dict[str, Any]]
]:
    """Split IDX rows into (broad, sector).
    Broad = the three codes in BROAD_INDICES.
    Sector = everything else. Codes for sector indices are sector names.
    Fails loudly if:
      - The set of broad codes returned does not match BROAD_INDICES exactly.
      - Any sector code collides with a broad code (shouldn't be possible,
        but this guards against future endpoint changes).
    """
    codes = [r["code"] for r in idx_rows]
    if len(codes) != len(set(codes)):
        dupes = [c for c in codes if codes.count(c) > 1]
        raise ValueError(f"endpoint #2 returned duplicate IDX codes: {sorted(set(dupes))}")
    broad_codes_returned = set(codes) & set(BROAD_INDICES.keys())
    if broad_codes_returned != set(BROAD_INDICES.keys()):
        raise ValueError(
            "endpoint #2 broad-index set does not match expected. "
            f"expected={sorted(BROAD_INDICES.keys())} "
            f"returned={sorted(broad_codes_returned)}"
        )
    broad: list[dict[str, Any]] = []
    sector: list[dict[str, Any]] = []
    for row in idx_rows:
        code = row["code"]
        if code in BROAD_INDICES:
            spec = BROAD_INDICES[code]
            broad.append({
                "code": code,
                "name": spec["name"],
                "kind": "broad",
                "sector_id": None,
                "valid_from": spec["valid_from"],
                "notes": spec["notes"],
            })
        else:
            if code in BROAD_INDICES:
                raise ValueError(
                    f"sector code collides with broad code: {code!r}"
                )
            sector.append({
                "code": code,
                "name": code,   # name = code for sector indices
                "kind": "sector",
                "sector_id": None,   # resolved later via name join
                "valid_from": STUDY_START,
                "notes": "valid_from=study_start placeholder; refine in Move 1d",
            })
    return broad, sector
def _resolve_sector_ids(
    conn, sector_rows: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Look up each sector index's sectors.id by name.
    Returns (resolved_rows, unmatched_rows). unmatched_rows are those whose
    name is not present in `sectors`. The caller decides what to do.
    """
    if not sector_rows:
        return [], []
    names = [r["code"] for r in sector_rows]
    placeholders = ",".join(["%s"] * len(names))
    cur = conn.cursor()
    try:
        cur.execute(
            f"SELECT name, id FROM sectors WHERE name IN ({placeholders})",
            tuple(names),
        )
        name_to_id = {name: sid for name, sid in cur.fetchall()}
    finally:
        cur.close()
    resolved: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    for row in sector_rows:
        sid = name_to_id.get(row["code"])
        if sid is None:
            unmatched.append(row)
            continue
        resolved.append({**row, "sector_id": sid})
    return resolved, unmatched
def _upsert_indices(conn, rows: list[dict[str, Any]]) -> int:
    """Upsert all rows. Returns the number of rows submitted."""
    sql = (
        "INSERT INTO indices (code, name, kind, sector_id, valid_from, notes) "
        "VALUES (%s, %s, %s, %s, %s, %s) "
        "ON DUPLICATE KEY UPDATE "
        "  name = VALUES(name), "
        "  kind = VALUES(kind), "
        "  sector_id = VALUES(sector_id), "
        "  valid_from = VALUES(valid_from), "
        "  notes = VALUES(notes)"
    )
    params = [
        (
            r["code"],
            r["name"],
            r["kind"],
            r["sector_id"],
            r["valid_from"],
            r["notes"],
        )
        for r in rows
    ]
    cur = conn.cursor()
    try:
        cur.executemany(sql, params)
    finally:
        cur.close()
    return len(params)
def _audit_sectors_without_index(conn) -> list[tuple[int, str]]:
    """Return (id, name) for sectors that have no matching index.
    Purely informational. A sector with no index is expected for at least
    Debenture (5) and Treasury Bond (22).
    """
    sql = (
        "SELECT s.id, s.name "
        "FROM sectors s "
        "LEFT JOIN indices i ON i.sector_id = s.id "
        "WHERE s.is_index_bucket = 0 "
        "  AND i.id IS NULL "
        "ORDER BY s.id"
    )
    cur = conn.cursor()
    try:
        cur.execute(sql)
        return list(cur.fetchall())
    finally:
        cur.close()
def main() -> int:
    run_id = None
    log_id = None
    try:
        run_id, log_id = db.start_load_log(
            target_table=TARGET_TABLE,
            source_provider=SOURCE_PROVIDER,
            source_endpoint=SOURCE_ENDPOINT,
            notes="endpoint #2, type='IDX' only",
        )
        LOG.info("run_id=%s log_id=%s starting indices load", run_id, log_id)
        result = fetch_json(SOURCE_ENDPOINT, cache_dir=paths.AUDIT_RAW_DIR)
        LOG.info(
            "fetched %s (%d bytes, %.3fs), cached=%s",
            result.url, result.byte_size, result.elapsed_seconds,
            result.cache_path,
        )
        idx_rows = _extract_idx_rows(result.data)
        LOG.info("filtered to %d type='IDX' rows", len(idx_rows))
        broad, sector = _classify(idx_rows)
        LOG.info("classified: %d broad, %d sector", len(broad), len(sector))
        with db.connection() as conn:
            resolved_sector, unmatched = _resolve_sector_ids(conn, sector)
            if unmatched:
                names = [r["code"] for r in unmatched]
                raise ValueError(
                    f"sector indices without matching sectors.name row: {names}"
                )
            all_rows = broad + resolved_sector
            submitted = _upsert_indices(conn, all_rows)
            # Informational: which sectors have no index?
            unindexed = _audit_sectors_without_index(conn)
        if unindexed:
            pretty = ", ".join(f"{name}(id={sid})" for sid, name in unindexed)
            LOG.info("%d sectors have no index: [%s]", len(unindexed), pretty)
        db.finish_load_log(
            log_id,
            status="SUCCESS",
            rows_inserted=submitted,
            notes=(
                f"{len(broad)} broad + {len(resolved_sector)} sector; "
                f"cache={result.cache_path.name if result.cache_path else 'none'}"
            ),
        )
        LOG.info("done: %d rows upserted", submitted)
        print(
            f"indices: upserted {submitted} rows "
            f"({len(broad)} broad + {len(resolved_sector)} sector) "
            f"[run_id={run_id}]"
        )
        return 0
    except Exception as exc:
        LOG.exception("indices load failed")
        if log_id is not None:
            try:
                db.finish_load_log(
                    log_id,
                    status="FAILED",
                    error_message=str(exc)[:1024],
                    notes="see logs/load_indices.log",
                )
            except Exception:
                LOG.exception("could not mark load_log row as FAILED")
        print(f"indices: FAILED - {exc}", file=sys.stderr)
        return 1
if __name__ == "__main__":
    sys.exit(main())