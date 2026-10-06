"""Backfill the daily_bars table for the equity universe.
Source: endpoint #7 (bullbd get-one-for-tv2).
  - One call per instrument, full history, archive floor 2014-03-02.
  - No gap-fill (deferred; see decision log 2026-10-06).
Universe: instruments WHERE type='EQ'.
Validation:
  - OHLC constraints enforced (high>=low, high>=open, high>=close,
    low<=open, low<=close). Bad rows are dropped and counted.
  - Empty payload (missing expected keys) -> SUCCESS with 0 rows.
  - HTTP error -> FAILED, continue.
Idempotent: INSERT ... ON DUPLICATE KEY UPDATE on (instrument_id, trade_date).
Run: py -m src.loaders.load_daily_bars
"""
from __future__ import annotations
import sys
import time
from datetime import date, datetime, timezone
from urllib.parse import quote
from src import db, paths
from src.http_client import fetch_json
from src.logging_setup import setup_logging
LOG = setup_logging("load_daily_bars")
TARGET_TABLE = "daily_bars"
SOURCE_PROVIDER = "bullbd"
EP7_URL = "https://provider.bullbd.com/shares/get-one-for-tv2?code={code}"
SOURCE_TAG = "bullbd"
SLEEP_BETWEEN_CALLS = 0.1
def _fetch_endpoint7_equity(code: str):
    url = EP7_URL.format(code=quote(code, safe=""))
    result = fetch_json(url, cache_dir=paths.AUDIT_RAW_DIR)
    data = result.data
    if not isinstance(data, dict):
        raise ValueError(f"endpoint #7 [{code}] not an object: {type(data).__name__}")
    required = ("o", "h", "l", "c", "v", "d")
    if not all(k in data for k in required):
        return None
    n = len(data["d"])
    if n == 0:
        return None
    for key in ("o", "h", "l", "c", "v"):
        if not isinstance(data[key], list) or len(data[key]) != n:
            raise ValueError(
                f"endpoint #7 [{code}] key {key!r} bad shape "
                f"(d={n}, {key}={len(data[key]) if isinstance(data[key], list) else 'n/a'})"
            )
    dates = []
    opens = []
    highs = []
    lows = []
    closes = []
    vols = []
    for i in range(n):
        ms = data["d"][i]
        if not isinstance(ms, (int, float)):
            raise ValueError(f"endpoint #7 [{code}] d[{i}] not numeric: {ms!r}")
        dt = datetime.fromtimestamp(ms / 1000, tz=timezone.utc).date()
        o = float(data["o"][i])
        h = float(data["h"][i])
        lo = float(data["l"][i])
        c = float(data["c"][i])
        v = data["v"][i]
        v = int(v) if v is not None else 0
        dates.append(dt)
        opens.append(o)
        highs.append(h)
        lows.append(lo)
        closes.append(c)
        vols.append(v)
    return dates, opens, highs, lows, closes, vols
def _ohlc_valid(o, h, l, c):
    return (
        h >= l
        and h >= o
        and h >= c
        and l <= o
        and l <= c
        and o > 0 and h > 0 and l > 0 and c > 0
    )
def _build_rows(instrument_id, dates, opens, highs, lows, closes, vols):
    rows = []
    bad = 0
    for i in range(len(dates)):
        o, h, l, c = opens[i], highs[i], lows[i], closes[i]
        if not _ohlc_valid(o, h, l, c):
            bad += 1
            continue
        rows.append((
            instrument_id,
            dates[i],
            o, h, l, c,
            vols[i],
            SOURCE_TAG,
        ))
    return rows, bad
def _upsert_daily_bars(conn, rows):
    if not rows:
        return 0
    sql = (
        "INSERT INTO daily_bars "
        "(instrument_id, trade_date, open, high, low, close, volume, source) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
        "ON DUPLICATE KEY UPDATE "
        "  open = VALUES(open), high = VALUES(high), "
        "  low = VALUES(low), close = VALUES(close), "
        "  volume = VALUES(volume), "
        "  source = VALUES(source)"
    )
    cur = conn.cursor()
    try:
        cur.executemany(sql, rows)
    finally:
        cur.close()
    return len(rows)
def _get_equity_universe():
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
    universe = _get_equity_universe()
    LOG.info("equity universe: %d instruments", len(universe))
    total_rows = 0
    total_bad = 0
    total_empty = 0
    total_failed = 0
    results = []
    for instrument_id, code in universe:
        run_id = None
        log_id = None
        try:
            run_id, log_id = db.start_load_log(
                target_table=TARGET_TABLE,
                source_provider=SOURCE_PROVIDER,
                source_endpoint=EP7_URL.format(code=code),
                notes=f"code={code}",
            )
            payload = _fetch_endpoint7_equity(code)
            if payload is None:
                LOG.info("[%s] empty payload (no history)", code)
                db.finish_load_log(
                    log_id,
                    status="SUCCESS",
                    rows_inserted=0,
                    notes=f"code={code}; empty payload",
                )
                results.append((code, 0, 0, 1, "SUCCESS"))
                total_empty += 1
                time.sleep(SLEEP_BETWEEN_CALLS)
                continue
            dates, opens, highs, lows, closes, vols = payload
            rows, bad = _build_rows(instrument_id, dates, opens, highs, lows, closes, vols)
            if bad:
                LOG.warning("[%s] dropped %d rows failing OHLC/positive check", code, bad)
            with db.connection() as conn:
                submitted = _upsert_daily_bars(conn, rows)
            db.finish_load_log(
                log_id,
                status="SUCCESS",
                rows_inserted=submitted,
                rows_skipped=bad,
                notes=f"code={code}; bad={bad}",
            )
            total_rows += submitted
            total_bad += bad
            results.append((code, submitted, bad, 0, "SUCCESS"))
            LOG.info("[%s] done: %d rows (%d bad)", code, submitted, bad)
            time.sleep(SLEEP_BETWEEN_CALLS)
        except Exception as exc:
            LOG.exception("[%s] load failed", code)
            if log_id is not None:
                try:
                    db.finish_load_log(
                        log_id,
                        status="FAILED",
                        error_message=str(exc)[:1024],
                        notes=f"code={code}",
                    )
                except Exception:
                    LOG.exception("[%s] could not mark load_log as FAILED", code)
            total_failed += 1
            results.append((code, 0, 0, 0, "FAILED"))
            time.sleep(SLEEP_BETWEEN_CALLS)
    print(f"daily_bars: {len(results)} instruments processed, "
          f"{total_rows} rows upserted, {total_bad} bad rows dropped, "
          f"{total_empty} empty, {total_failed} failed")
    if total_failed:
        print("FAILED instruments:")
        for code, rows, bad, empty, status in results:
            if status == "FAILED":
                print(f"  {code}")
    return 0 if total_failed == 0 else 2
if __name__ == "__main__":
    sys.exit(main())