"""Populate the trading_calendar table.
Source: DSEX rows in index_bars. Every date DSEX has a bar = a trading day.
Range: MIN(DSEX.trade_date) -> today.
  - DSEX bars start 2014-03-02 (endpoint #7 archive floor).
  - Pre-archive window 2013-01-28 -> 2014-03-01 is documented in
    DATA_QUALITY.md, not encoded here.
Notes column:
  - NULL for weekends (Fri/Sat)
  - NULL for trading days
  - 'no DSEX bar' for Mon-Thu dates without a DSEX bar (suspected holidays)
Idempotent: INSERT ... ON DUPLICATE KEY UPDATE on trade_date.
Run: py -m src.loaders.load_trading_calendar
"""
from __future__ import annotations
import sys
from datetime import date, timedelta
from src import db
from src.logging_setup import setup_logging
LOG = setup_logging("load_trading_calendar")
TARGET_TABLE = "trading_calendar"
SOURCE_PROVIDER = "derived"
DSEX_CODE = "DSEX"
WEEKEND_WEEKDAYS = {4, 5}
def _fetch_bounds_and_trading_days():
    with db.connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT MIN(b.trade_date), MAX(b.trade_date) "
            "FROM index_bars b JOIN indices i ON i.id = b.index_id "
            "WHERE i.code = %s",
            (DSEX_CODE,),
        )
        row = cur.fetchone()
        if row is None or row[0] is None:
            raise RuntimeError("no DSEX bars found in index_bars")
        min_date, max_date = row
        cur.execute(
            "SELECT b.trade_date "
            "FROM index_bars b JOIN indices i ON i.id = b.index_id "
            "WHERE i.code = %s",
            (DSEX_CODE,),
        )
        trading_days = {r[0] for r in cur.fetchall()}
        cur.close()
    return min_date, max_date, trading_days
def _build_calendar_rows(min_date, max_date, trading_days):
    rows = []
    cur = min_date
    while cur <= max_date:
        is_trading = 1 if cur in trading_days else 0
        if is_trading:
            notes = None
        elif cur.weekday() in WEEKEND_WEEKDAYS:
            notes = None
        else:
            notes = "no DSEX bar"
        rows.append((cur, is_trading, notes))
        cur = cur + timedelta(days=1)
    return rows
def _upsert(conn, rows):
    if not rows:
        return 0
    sql = (
        "INSERT INTO trading_calendar (trade_date, is_trading_day, notes) "
        "VALUES (%s, %s, %s) "
        "ON DUPLICATE KEY UPDATE "
        "  is_trading_day = VALUES(is_trading_day), "
        "  notes = VALUES(notes)"
    )
    cur = conn.cursor()
    try:
        cur.executemany(sql, rows)
    finally:
        cur.close()
    return len(rows)
def main():
    run_id = None
    log_id = None
    try:
        min_date, max_date_dsex, trading_days = _fetch_bounds_and_trading_days()
        today = date.today()
        end_date = max(max_date_dsex, today)
        LOG.info(
            "DSEX range: %s -> %s (%d trading days); calendar end: %s",
            min_date, max_date_dsex, len(trading_days), end_date,
        )
        run_id, log_id = db.start_load_log(
            target_table=TARGET_TABLE,
            source_provider=SOURCE_PROVIDER,
            source_endpoint=None,
            scope_date_from=min_date,
            scope_date_to=end_date,
            notes="derived from DSEX index_bars",
        )
        LOG.info("run_id=%s log_id=%s", run_id, log_id)
        rows = _build_calendar_rows(min_date, end_date, trading_days)
        LOG.info("built %d calendar rows", len(rows))
        with db.connection() as conn:
            submitted = _upsert(conn, rows)
        trading_count = sum(1 for r in rows if r[1] == 1)
        nontrading_weekday = sum(
            1 for r in rows if r[1] == 0 and r[0].weekday() not in WEEKEND_WEEKDAYS
        )
        weekend_count = sum(
            1 for r in rows if r[1] == 0 and r[0].weekday() in WEEKEND_WEEKDAYS
        )
        db.finish_load_log(
            log_id,
            status="SUCCESS",
            rows_inserted=submitted,
            notes=(
                f"trading={trading_count}, "
                f"weekend={weekend_count}, "
                f"holiday_weekday={nontrading_weekday}"
            ),
        )
        print(
            f"trading_calendar: {submitted} rows "
            f"({trading_count} trading, {weekend_count} weekend, "
            f"{nontrading_weekday} holiday-weekday) "
            f"range {min_date}..{end_date} "
            f"[run_id={run_id}]"
        )
        return 0
    except Exception as exc:
        LOG.exception("trading_calendar load failed")
        if log_id is not None:
            try:
                db.finish_load_log(
                    log_id,
                    status="FAILED",
                    error_message=str(exc)[:1024],
                )
            except Exception:
                LOG.exception("could not mark load_log as FAILED")
        print(f"trading_calendar: FAILED - {exc}", file=sys.stderr)
        return 1
if __name__ == "__main__":
    sys.exit(main())