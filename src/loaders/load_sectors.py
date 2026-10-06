"""Load the sectors reference table.
Source: https://stocknow.com.bd/api/v1/sectors (endpoint #1).
Produces: 24 rows in `sectors` (23 real + 1 synthetic id=23 "Index").
Idempotent: safe to re-run. Uses INSERT ... ON DUPLICATE KEY UPDATE.
Run: py -m src.loaders.load_sectors
"""
from __future__ import annotations
import sys
from typing import Any
from src import db, paths
from src.http_client import fetch_json
from src.logging_setup import setup_logging
LOG = setup_logging("load_sectors")
SOURCE_PROVIDER = "stocknow.com.bd"
SOURCE_ENDPOINT = "https://stocknow.com.bd/api/v1/sectors"
TARGET_TABLE = "sectors"
# Synthetic row required by the schema: instruments.sector_id=23 refers to
# DSEX/DS30/DSES and their sector-index siblings. Endpoint #1 does not
# return id=23, so we insert it ourselves.
SYNTHETIC_INDEX_SECTOR = {
    "id": 23,
    "name": "Index",
    "is_index_bucket": 1,
    "notes": "synthetic - index bucket (not from endpoint #1)",
}
def _validate_sector(raw: Any, key: str) -> dict[str, Any]:
    """Validate one sector entry from the endpoint's JSON object.
    Fails loudly on any malformed entry. Returns a normalized dict with
    keys: id (int), name (str).
    """
    if not isinstance(raw, dict):
        raise ValueError(f"sectors[{key!r}] is not an object: {type(raw).__name__}")
    if "id" not in raw or "name" not in raw:
        raise ValueError(f"sectors[{key!r}] missing 'id' or 'name': {raw!r}")
    sid = raw["id"]
    name = raw["name"]
    if not isinstance(sid, int):
        raise ValueError(f"sectors[{key!r}] id is not int: {sid!r}")
    if not isinstance(name, str) or not name.strip():
        raise ValueError(f"sectors[{key!r}] name is empty or not str: {name!r}")
    return {"id": sid, "name": name.strip()}
def _parse_sectors(data: Any) -> list[dict[str, Any]]:
    """Parse and validate the top-level response object.
    Expected shape: {"1": {"id":1,"name":"Bank"}, "2": {...}, ...}
    """
    if not isinstance(data, dict):
        raise ValueError(
            f"Top-level response is not an object: {type(data).__name__}"
        )
    if not data:
        raise ValueError("Top-level response is an empty object")
    rows: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    seen_names: set[str] = set()
    for key, value in data.items():
        row = _validate_sector(value, key)
        if row["id"] in seen_ids:
            raise ValueError(f"Duplicate sector id in response: {row['id']}")
        if row["name"] in seen_names:
            raise ValueError(f"Duplicate sector name in response: {row['name']!r}")
        seen_ids.add(row["id"])
        seen_names.add(row["name"])
        rows.append(row)
    return rows
def _upsert_sectors(conn, rows: list[dict[str, Any]]) -> int:
    """Upsert all rows. Returns the number of rows submitted (not net new)."""
    sql = (
        "INSERT INTO sectors (id, name, is_index_bucket, notes) "
        "VALUES (%s, %s, %s, %s) "
        "ON DUPLICATE KEY UPDATE "
        "  name = VALUES(name), "
        "  is_index_bucket = VALUES(is_index_bucket), "
        "  notes = VALUES(notes)"
    )
    params = [
        (
            row["id"],
            row["name"],
            int(row.get("is_index_bucket", 0)),
            row.get("notes"),
        )
        for row in rows
    ]
    cur = conn.cursor()
    try:
        cur.executemany(sql, params)
    finally:
        cur.close()
    return len(params)
def main() -> int:
    run_id = None
    log_id = None
    try:
        run_id, log_id = db.start_load_log(
            target_table=TARGET_TABLE,
            source_provider=SOURCE_PROVIDER,
            source_endpoint=SOURCE_ENDPOINT,
            notes="endpoint #1 sectors + synthetic id=23",
        )
        LOG.info("run_id=%s log_id=%s starting sectors load", run_id, log_id)
        result = fetch_json(SOURCE_ENDPOINT, cache_dir=paths.AUDIT_RAW_DIR)
        LOG.info(
            "fetched %s (%d bytes, %.3fs), cached=%s",
            result.url, result.byte_size, result.elapsed_seconds,
            result.cache_path,
        )
        real_rows = _parse_sectors(result.data)
        LOG.info("parsed %d real sectors", len(real_rows))
        all_rows = real_rows + [SYNTHETIC_INDEX_SECTOR]
        LOG.info("prepared %d total rows (incl. synthetic id=%d)",
                 len(all_rows), SYNTHETIC_INDEX_SECTOR["id"])
        with db.connection() as conn:
            submitted = _upsert_sectors(conn, all_rows)
        db.finish_load_log(
            log_id,
            status="SUCCESS",
            rows_inserted=submitted,
            notes=(
                f"{len(real_rows)} real + 1 synthetic; "
                f"cache={result.cache_path.name if result.cache_path else 'none'}"
            ),
        )
        LOG.info("done: %d rows upserted", submitted)
        print(
            f"sectors: upserted {submitted} rows "
            f"({len(real_rows)} endpoint + 1 synthetic) "
            f"[run_id={run_id}]"
        )
        return 0
    except Exception as exc:
        LOG.exception("sectors load failed")
        if log_id is not None:
            try:
                db.finish_load_log(
                    log_id,
                    status="FAILED",
                    error_message=str(exc)[:1024],
                    notes="see logs/load_sectors.log",
                )
            except Exception:
                LOG.exception("could not mark load_log row as FAILED")
        print(f"sectors: FAILED - {exc}", file=sys.stderr)
        return 1
if __name__ == "__main__":
    sys.exit(main())