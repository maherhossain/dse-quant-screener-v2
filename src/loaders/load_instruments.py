"""Load the instruments reference table.
Sources:
  - endpoint #2: https://provider.bullbd.com/shares/get-names-tv
  - endpoint #3: https://stocknow.com.bd/api/v1/instruments
Union of both, one row per unique `code`. All instruments loaded (equities,
bonds, MFs, indices, dead codes) so the table is a complete registry.
Module 2 filters universe by type='EQ'.
Reconciliation rules (locked decisions):
  - category: from endpoint #2 (may be NULL)
  - is_sme:   from endpoint #3 (stocknow splits SME out; #2 does not)
  - type:     from endpoint #2, with manual overrides for 8 codes that
              endpoint #2 fails to classify
  - sector_id: from endpoint #3 (integer). For endpoint #2-only rows,
               resolved by name-join against sectors.name.
  - Rejected: 'CDSET', and the malformed key 'Debenture'
Idempotent: INSERT ... ON DUPLICATE KEY UPDATE on `code`.
Run: py -m src.loaders.load_instruments
"""
from __future__ import annotations
import sys
from typing import Any
from src import db, paths
from src.http_client import fetch_json
from src.logging_setup import setup_logging
LOG = setup_logging("load_instruments")
SOURCE_PROVIDER = "bullbd+stocknow"
SOURCE_ENDPOINT = "provider.bullbd.com/shares/get-names-tv + stocknow.com.bd/api/v1/instruments"
TARGET_TABLE = "instruments"
ENDPOINT_NAMES = "https://provider.bullbd.com/shares/get-names-tv"
ENDPOINT_INSTRUMENTS = "https://stocknow.com.bd/api/v1/instruments"
# Codes present in one or both endpoints that must be rejected at load.
REJECTED_CODES: set[str] = {"CDSET", "Debenture"}
# Manual type overrides for endpoint #2 rows where BullBD's type is NULL or
# wrong. Locked per Module 1 Move 1d decision log. Values are the corrected
# type ('EQ' or 'MF' or 'CB' or 'IDX').
TYPE_OVERRIDES: dict[str, str] = {
    # Real equities BullBD fails to classify:
    "BDSERVICE": "EQ",
    "BXSYNTH": "EQ",
    "GLAXOSMITH": "EQ",
    "MODERNDYE": "EQ",
    "MONNOSTAF": "EQ",
    "SAVAREFR": "EQ",
    "SPPCL": "EQ",
    "UNITEDAIR": "EQ",
    # Non-equity reclassifications:
    "1STBSRS": "CB",
    "1STICB": "CB",
    "2NDICB": "CB",
    "3RDICB": "CB",
    "4THICB": "CB",
    "5THICB": "CB",
    "6THICB": "CB",
    "7THICB": "CB",
    "8THICB": "CB",
    "ACIZCBOND": "CB",
    "BRACSCBOND": "CB",
    "CBLPBOND": "CB",
    "MBPLCPBOND": "CB",
    "UCB2PBOND": "CB",
    "DEBBXDENIM": "CB",
    "DEBBXKNI": "CB",
    "AIMS1STMF": "MF",
    "GRAMEEN1": "MF",
    "ICB1STNRB": "MF",
    "ICB2NDNRB": "MF",
    "ICBISLAMIC": "MF",
    "NLI1STMF": "MF",
    "SEBL1STMF": "MF",
    "DGENX": "IDX",
}
# ---------------------------------------------------------------------
# endpoint #2 parsing
# ---------------------------------------------------------------------
def _parse_endpoint2(data: Any) -> dict[str, dict[str, Any]]:
    """Parse endpoint #2 into {code: row_dict}.
    Skips IDX rows (they go in `indices`, already loaded by Move 1c).
    Skips REJECTED_CODES.
    Applies TYPE_OVERRIDES.
    """
    if not isinstance(data, list):
        raise ValueError(f"endpoint #2 response is not a list: {type(data).__name__}")
    out: dict[str, dict[str, Any]] = {}
    for i, entry in enumerate(data):
        if not isinstance(entry, dict):
            raise ValueError(f"endpoint #2 entry {i} is not an object")
        code = entry.get("code")
        if not isinstance(code, str) or not code.strip():
            raise ValueError(f"endpoint #2 entry {i} has invalid code: {code!r}")
        code = code.strip()
        if code in REJECTED_CODES:
            continue
        etype = entry.get("type")
        if etype == "IDX":
            continue  # indices loaded separately
        # Apply overrides
        if code in TYPE_OVERRIDES:
            etype = TYPE_OVERRIDES[code]
        sector_name = entry.get("sector")
        out[code] = {
            "code": code,
            "name": entry.get("name"),
            "type": etype,
            "category": entry.get("category"),
            "sector_name": sector_name if isinstance(sector_name, str) else None,
            "in_2": True,
            "in_3": False,
        }
    return out
# ---------------------------------------------------------------------
# endpoint #3 parsing
# ---------------------------------------------------------------------
def _infer_type_from_category3(category: Any) -> tuple[str | None, int, str | None]:
    """Return (type, is_sme, category) inferred from endpoint #3's category.
    Rules (locked):
      A/B/Z -> type='EQ', is_sme=0, category preserved
      SME   -> type='EQ', is_sme=1, category NULL (folded)
      N or null -> type=None, is_sme=0, category preserved
    """
    if isinstance(category, str):
        c = category.strip().upper()
        if c in ("A", "B", "Z"):
            return ("EQ", 0, c)
        if c == "SME":
            return ("EQ", 1, None)
        if c == "N":
            return (None, 0, c)
    return (None, 0, category if isinstance(category, str) else None)
def _parse_endpoint3(data: Any) -> dict[str, dict[str, Any]]:
    """Parse endpoint #3 into {code: row_dict}.
    Skips REJECTED_CODES.
    """
    if not isinstance(data, dict):
        raise ValueError(f"endpoint #3 response is not an object: {type(data).__name__}")
    out: dict[str, dict[str, Any]] = {}
    for code, entry in data.items():
        if not isinstance(code, str) or not code.strip():
            raise ValueError(f"endpoint #3 has invalid key: {code!r}")
        code = code.strip()
        if code in REJECTED_CODES:
            continue
        if not isinstance(entry, dict):
            raise ValueError(f"endpoint #3 entry {code!r} is not an object")
        etype, is_sme, cat = _infer_type_from_category3(entry.get("category"))
        sector_id = entry.get("sector_id")
        if not isinstance(sector_id, int):
            sector_id = None
        out[code] = {
            "code": code,
            "name": entry.get("name"),
            "type": etype,
            "category": cat,
            "sector_id": sector_id,
            "is_sme": is_sme,
            "in_2": False,
            "in_3": True,
        }
    return out
# ---------------------------------------------------------------------
# merge
# ---------------------------------------------------------------------
def _merge(
    p2: dict[str, dict[str, Any]],
    p3: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge endpoint #2 and #3 dicts into a list of final rows.
    Rules:
      - Union on code.
      - category: from #2 if present, else from #3.
      - type: from #2 if present, else from #3.
      - is_sme: from #3 if present, else 0.
      - sector_id: from #3 if present. If #2-only, sector_name is kept
        and resolved later.
    """
    all_codes = sorted(set(p2.keys()) | set(p3.keys()))
    merged: list[dict[str, Any]] = []
    for code in all_codes:
        r2 = p2.get(code)
        r3 = p3.get(code)
        if r2 and r3:
            category = r2.get("category") if r2.get("category") is not None else r3.get("category")
            etype = r2.get("type") if r2.get("type") is not None else r3.get("type")
            is_sme = r3.get("is_sme", 0)
            sector_id = r3.get("sector_id")
            name = r2.get("name") or r3.get("name")
            sector_name = None  # not needed; sector_id is set
            source_primary = "bullbd+stocknow"
        elif r2:
            category = r2.get("category")
            etype = r2.get("type")
            is_sme = 0
            sector_id = None
            name = r2.get("name")
            sector_name = r2.get("sector_name")
            source_primary = "bullbd"
        else:
            assert r3 is not None
            category = r3.get("category")
            etype = r3.get("type")
            is_sme = r3.get("is_sme", 0)
            sector_id = r3.get("sector_id")
            name = r3.get("name")
            sector_name = None
            source_primary = "stocknow"
        merged.append({
            "code": code,
            "name": name,
            "type": etype,
            "category": category,
            "is_sme": is_sme,
            "sector_id": sector_id,
            "sector_name": sector_name,  # may be None; resolved later
            "source_primary": source_primary,
        })
    return merged
# ---------------------------------------------------------------------
# DB writes
# ---------------------------------------------------------------------
def _resolve_sector_ids_by_name(
    conn, rows: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[str]]:
    """For rows with sector_name set and sector_id None, resolve by name.
    Returns (rows, unmatched_names). Unmatched names are logged, not fatal.
    """
    names = sorted({r["sector_name"] for r in rows if r.get("sector_name")})
    if not names:
        return rows, []
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
    unmatched: list[str] = []
    for r in rows:
        if r.get("sector_name") and r.get("sector_id") is None:
            sid = name_to_id.get(r["sector_name"])
            if sid is None:
                if r["sector_name"] not in unmatched:
                    unmatched.append(r["sector_name"])
            else:
                r["sector_id"] = sid
    return rows, unmatched
def _upsert_instruments(conn, rows: list[dict[str, Any]]) -> int:
    """Upsert all rows. Returns the number of rows submitted.
    Fields written:
      code, name, sector_id, type, category, is_sme, source_primary, source_notes
    first_seen_date / last_seen_date left NULL (populated later from daily_bars).
    """
    sql = (
        "INSERT INTO instruments "
        "(code, name, sector_id, type, category, is_sme, source_primary, source_notes) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
        "ON DUPLICATE KEY UPDATE "
        "  name = VALUES(name), "
        "  sector_id = VALUES(sector_id), "
        "  type = VALUES(type), "
        "  category = VALUES(category), "
        "  is_sme = VALUES(is_sme), "
        "  source_primary = VALUES(source_primary), "
        "  source_notes = VALUES(source_notes)"
    )
    params = [
        (
            r["code"],
            r["name"],
            r["sector_id"],
            r["type"],
            r["category"],
            int(r["is_sme"]),
            r["source_primary"],
            None,
        )
        for r in rows
    ]
    cur = conn.cursor()
    try:
        cur.executemany(sql, params)
    finally:
        cur.close()
    return len(params)
# ---------------------------------------------------------------------
# main
# ---------------------------------------------------------------------
def main() -> int:
    run_id = None
    log_id = None
    try:
        run_id, log_id = db.start_load_log(
            target_table=TARGET_TABLE,
            source_provider=SOURCE_PROVIDER,
            source_endpoint=SOURCE_ENDPOINT,
            notes="union endpoint #2 + #3; 8 type overrides; 2 codes rejected",
        )
        LOG.info("run_id=%s log_id=%s starting instruments load", run_id, log_id)
        # Fetch both endpoints
        r2 = fetch_json(ENDPOINT_NAMES, cache_dir=paths.AUDIT_RAW_DIR)
        LOG.info("endpoint #2: %d bytes, cached=%s",
                 r2.byte_size, r2.cache_path.name if r2.cache_path else None)
        r3 = fetch_json(ENDPOINT_INSTRUMENTS, cache_dir=paths.AUDIT_RAW_DIR)
        LOG.info("endpoint #3: %d bytes, cached=%s",
                 r3.byte_size, r3.cache_path.name if r3.cache_path else None)
        # Parse
        p2 = _parse_endpoint2(r2.data)
        p3 = _parse_endpoint3(r3.data)
        LOG.info("parsed: %d from endpoint #2, %d from endpoint #3", len(p2), len(p3))
        # Merge
        merged = _merge(p2, p3)
        only_2 = sum(1 for r in merged if r["source_primary"] == "bullbd")
        only_3 = sum(1 for r in merged if r["source_primary"] == "stocknow")
        both = sum(1 for r in merged if r["source_primary"] == "bullbd+stocknow")
        LOG.info("merged: %d total (both=%d, only#2=%d, only#3=%d)",
                 len(merged), both, only_2, only_3)
        # Resolve sector names for endpoint #2-only rows
        with db.connection() as conn:
            merged, unmatched = _resolve_sector_ids_by_name(conn, merged)
            if unmatched:
                LOG.warning("%d sector names from endpoint #2 not found in sectors: %s",
                            len(unmatched), unmatched)
            submitted = _upsert_instruments(conn, merged)
        # Summary counts by type
        type_counts: dict[str, int] = {}
        for r in merged:
            t = r["type"] or "<null>"
            type_counts[t] = type_counts.get(t, 0) + 1
        LOG.info("type distribution: %s", dict(sorted(type_counts.items())))
        db.finish_load_log(
            log_id,
            status="SUCCESS",
            rows_inserted=submitted,
            notes=(
                f"both={both}, only#2={only_2}, only#3={only_3}; "
                f"rejected={len(REJECTED_CODES)}; "
                f"type_overrides={len(TYPE_OVERRIDES)}"
            ),
        )
        LOG.info("done: %d rows upserted", submitted)
        print(
            f"instruments: upserted {submitted} rows "
            f"(both={both}, only#2={only_2}, only#3={only_3}) "
            f"[run_id={run_id}]"
        )
        return 0
    except Exception as exc:
        LOG.exception("instruments load failed")
        if log_id is not None:
            try:
                db.finish_load_log(
                    log_id,
                    status="FAILED",
                    error_message=str(exc)[:1024],
                    notes="see logs/load_instruments.log",
                )
            except Exception:
                LOG.exception("could not mark load_log row as FAILED")
        print(f"instruments: FAILED - {exc}", file=sys.stderr)
        return 1
if __name__ == "__main__":
    sys.exit(main())