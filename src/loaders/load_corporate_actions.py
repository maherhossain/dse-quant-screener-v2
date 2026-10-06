"""Load the corporate_actions table.
Source: endpoint #8 (bullbd get-corporate-actions).
Universe: all instruments (563).
Coverage: ~2014-03 onward; ~1 event/stock/year (annual dividend).
Date handling (from ENDPOINT_AUDIT entry 8):
  - publish_date: kept as-is.
  - year_ended_on, agm_date, record_date: shifted +1 day to correct
    from the source's 18:00 UTC representation.
  - agm_date sentinel 1969-12-31 -> NULL.
Idempotent: INSERT ... ON DUPLICATE KEY UPDATE on (instrument_id, news_id).
Run: py -m src.loaders.load_corporate_actions
"""
from __future__ import annotations
import sys
import time
from datetime import date, datetime, timedelta
from typing import Any, Optional
from urllib.parse import quote
from src import db, paths
from src.http_client import fetch_json
from src.logging_setup import setup_logging
LOG = setup_logging("load_corporate_actions")
TARGET_TABLE = "corporate_actions"
SOURCE_PROVIDER = "bullbd"
EP8_URL = "https://provider.bullbd.com/corporate-actions/get-corporate-actions?share={code}"
SLEEP_BETWEEN_CALLS = 0.1
NULL_DATE_MAX = date(1970, 1, 2)


def _is_null_sentinel(d: Optional[date]) -> bool:
    return d is not None and d <= NULL_DATE_MAX

def _parse_iso_date_plus1(raw):
    if raw is None:
        return None
    if not isinstance(raw, str):
        return None
    s = raw.strip()
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        LOG.warning("unparseable date string: %r", raw)
        return None
    return (dt + timedelta(days=1)).date()
def _parse_publish_date(raw):
    if raw is None or not isinstance(raw, str):
        return None
    s = raw.strip()
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        LOG.warning("unparseable publish_date: %r", raw)
        return None
    return dt.date()
def _to_float(raw):
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return None
        try:
            return float(s)
        except ValueError:
            return None
    return None
def _to_int01(raw):
    v = _to_float(raw)
    if v is None:
        return None
    return int(v)
def _fetch_endpoint8(code):
    url = EP8_URL.format(code=quote(code, safe=""))
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
        news_id = e.get("news_id")
        if not isinstance(news_id, str) or not news_id.strip():
            LOG.warning("[%s] entry missing news_id; skipping", code)
            continue
        publish_date = _parse_publish_date(e.get("publish_date"))
        if publish_date is None:
            LOG.warning("[%s] entry %s missing/unparseable publish_date; skipping",
                        code, news_id)
            continue
        year_ended_on = _parse_iso_date_plus1(e.get("year_ended_on"))
        if _is_null_sentinel(year_ended_on):
            year_ended_on = None

        agm_date = _parse_iso_date_plus1(e.get("agm_date"))
        if _is_null_sentinel(agm_date):
            agm_date = None

        record_date = _parse_iso_date_plus1(e.get("record_date"))
        if _is_null_sentinel(record_date):
            record_date = None

        rows.append((
            code,
            instrument_id,
            news_id,
            publish_date,
            year_ended_on,
            agm_date,
            record_date,
            _to_float(e.get("cash")),
            _to_float(e.get("stock")),
            _to_float(e.get("right")),
            _to_float(e.get("premium")),
            _to_float(e.get("split")),
            _to_int01(e.get("nodiv")),
            _to_int01(e.get("record_date_confirm")),
            SOURCE_PROVIDER,
        ))
    return rows
def _upsert(conn, rows):
    if not rows:
        return 0
    sql = (
        "INSERT INTO corporate_actions "
        "(code, instrument_id, news_id, publish_date, year_ended_on, agm_date, "
        " record_date, cash_pct, stock_pct, right_pct, premium, split_ratio, "
        " no_dividend, record_date_confirmed, source_provider) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
        "ON DUPLICATE KEY UPDATE "
        "  publish_date = VALUES(publish_date), "
        "  year_ended_on = VALUES(year_ended_on), "
        "  agm_date = VALUES(agm_date), "
        "  record_date = VALUES(record_date), "
        "  cash_pct = VALUES(cash_pct), "
        "  stock_pct = VALUES(stock_pct), "
        "  right_pct = VALUES(right_pct), "
        "  premium = VALUES(premium), "
        "  split_ratio = VALUES(split_ratio), "
        "  no_dividend = VALUES(no_dividend), "
        "  record_date_confirmed = VALUES(record_date_confirmed)"
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
        cur.execute("SELECT id, code FROM instruments ORDER BY id")
        rows = list(cur.fetchall())
        cur.close()
    return [(int(r[0]), str(r[1])) for r in rows]
def main():
    universe = _get_universe()
    LOG.info("corporate_actions universe: %d instruments", len(universe))
    total_rows = 0
    total_empty = 0
    total_failed = 0
    for instrument_id, code in universe:
        run_id = None
        log_id = None
        try:
            run_id, log_id = db.start_load_log(
                target_table=TARGET_TABLE,
                source_provider=SOURCE_PROVIDER,
                source_endpoint=EP8_URL.format(code=code),
                notes=f"code={code}",
            )
            entries = _fetch_endpoint8(code)
            if entries is None:
                LOG.info("[%s] empty payload", code)
                db.finish_load_log(log_id, status="SUCCESS", rows_inserted=0,
                                   notes=f"code={code}; empty payload")
                total_empty += 1
                time.sleep(SLEEP_BETWEEN_CALLS)
                continue
            rows = _build_rows(instrument_id, code, entries)
            with db.connection() as conn:
                submitted = _upsert(conn, rows)
            db.finish_load_log(log_id, status="SUCCESS",
                               rows_inserted=submitted,
                               notes=f"code={code}; entries={len(entries)}")
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
    print(f"corporate_actions: {len(universe)} instruments processed, "
          f"{total_rows} rows upserted, {total_empty} empty, {total_failed} failed")
    return 0 if total_failed == 0 else 2
if __name__ == "__main__":
    sys.exit(main())