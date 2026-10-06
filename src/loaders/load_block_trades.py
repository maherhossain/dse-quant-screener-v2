"""Load the block_trades table.
Source: endpoint #9 (bullbd get-block-share).
Universe: instruments WHERE type='EQ'.
Coverage: 2023-06-21 onward (BullBD's block-trade archive floor).
Idempotent: INSERT ... ON DUPLICATE KEY UPDATE on (instrument_id, trade_date).
Run: py -m src.loaders.load_block_trades
"""
from __future__ import annotations
import sys
import time
from datetime import date, datetime
from typing import Any, Optional
from urllib.parse import quote
from src import db, paths
from src.http_client import fetch_json
from src.logging_setup import setup_logging
LOG = setup_logging("load_block_trades")
TARGET_TABLE = "block_trades"
SOURCE_PROVIDER = "bullbd"
EP9_URL = "https://provider.bullbd.com/shares/get-block-share?code={code}"
SLEEP_BETWEEN_CALLS = 0.1
def _parse_date(raw):
    if raw is None:
        return None
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return None
        try:
            return datetime.fromisoformat(s).date()
        except ValueError:
            LOG.warning("unparseable date: %r", raw)
            return None
    return None
def _to_int(raw):
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None
def _to_float(raw):
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None
def _fetch_endpoint9(code):
    url = EP9_URL.format(code=quote(code, safe=""))
    result = fetch_json(url, cache_dir=paths.AUDIT_RAW_DIR)
    data = result.data
    if not isinstance(data, list):
        return None
    if not data:
        return None
    return data
def _build_rows(instrument_id, code, entries):
    rows = []
    for e in entries:
        if not isinstance(e, dict):
            LOG.warning("[%s] skipping non-dict entry", code)
            continue
        trade_date = _parse_date(e.get("date"))
        if trade_date is None:
            LOG.warning("[%s] entry missing/unparseable date; skipping", code)
            continue
        trades = _to_int(e.get("trades"))
        volume = _to_int(e.get("volume"))
        value_m = _to_float(e.get("value"))
        min_p = _to_float(e.get("minPrice"))
        max_p = _to_float(e.get("maxPrice"))
        if trades is None or volume is None or value_m is None or min_p is None or max_p is None:
            LOG.warning("[%s] entry %s has null numeric field; skipping", code, trade_date)
            continue
        rows.append((
            code,
            instrument_id,
            trade_date,
            trades,
            volume,
            value_m,
            min_p,
            max_p,
            SOURCE_PROVIDER,
        ))
    return rows
def _upsert(conn, rows):
    if not rows:
        return 0
    sql = (
        "INSERT INTO block_trades "
        "(code, instrument_id, trade_date, block_trade_count, block_volume, "
        " block_value_million, block_min_price, block_max_price, source_provider) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) "
        "ON DUPLICATE KEY UPDATE "
        "  block_trade_count = VALUES(block_trade_count), "
        "  block_volume = VALUES(block_volume), "
        "  block_value_million = VALUES(block_value_million), "
        "  block_min_price = VALUES(block_min_price), "
        "  block_max_price = VALUES(block_max_price), "
        "  source_provider = VALUES(source_provider)"
    )
    cur = conn.cursor()
    try:
        cur.executemany(sql, rows)
    finally:
        cur.close()
    return len(rows)
def _get_universe():
    with db.connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, code FROM instruments WHERE type = %s ORDER BY id",
            ("EQ",),
        )
        rows = list(cur.fetchall())
        cur.close()
    return [(int(r[0]), str(r[1])) for r in rows]
def main():
    universe = _get_universe()
    LOG.info("block_trades universe: %d equity instruments", len(universe))
    total_rows = 0
    total_empty = 0
    total_failed = 0
    earliest = None
    latest = None
    for instrument_id, code in universe:
        run_id = None
        log_id = None
        try:
            run_id, log_id = db.start_load_log(
                target_table=TARGET_TABLE,
                source_provider=SOURCE_PROVIDER,
                source_endpoint=EP9_URL.format(code=code),
                notes=f"code={code}",
            )
            entries = _fetch_endpoint9(code)
            if entries is None:
                db.finish_load_log(log_id, status="SUCCESS", rows_inserted=0,
                                   notes=f"code={code}; empty payload")
                total_empty += 1
                time.sleep(SLEEP_BETWEEN_CALLS)
                continue
            rows = _build_rows(instrument_id, code, entries)
            with db.connection() as conn:
                submitted = _upsert(conn, rows)
            if rows:
                d_min = min(r[2] for r in rows)
                d_max = max(r[2] for r in rows)
                earliest = d_min if earliest is None else min(earliest, d_min)
                latest = d_max if latest is None else max(latest, d_max)
            date_note = ""
            if rows:
                d_min = min(r[2] for r in rows)
                d_max = max(r[2] for r in rows)
                date_note = f"; {d_min}..{d_max}"
            db.finish_load_log(log_id, status="SUCCESS",
                               rows_inserted=submitted,
                               notes=f"code={code}; entries={len(entries)}{date_note}")
            total_rows += submitted
            LOG.info("[%s] done: %d rows", code, submitted)
            time.sleep(SLEEP_BETWEEN_CALLS)
        except Exception as exc:
            LOG.exception("[%s] failed", code)
            if log_id is not None:
                try:
                    db.finish_load_log(log_id, status="FAILED",
                                       error_message=str(exc)[:1024],
                                       notes=f"code={code}")
                except Exception:
                    LOG.exception("[%s] could not mark load_log FAILED", code)
            total_failed += 1
            time.sleep(SLEEP_BETWEEN_CALLS)
    print(f"block_trades: {len(universe)} instruments processed, "
          f"{total_rows} rows upserted, {total_empty} empty, {total_failed} failed")
    if earliest and latest:
        print(f"date range observed: {earliest} to {latest}")
    return 0 if total_failed == 0 else 2
if __name__ == "__main__":
    sys.exit(main())