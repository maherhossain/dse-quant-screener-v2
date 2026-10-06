"""One-shot backfill of instruments.first_seen_date / last_seen_date.
Derived from daily_bars: min/max trade_date per instrument.
Not a data load; no load_log entry. first_seen_date/last_seen_date are
the audit trail.
Idempotent. Safe to re-run any time daily_bars changes.
Run: py -m src.loaders.backfill_instrument_dates
"""
from __future__ import annotations
import sys
from src import db
from src.logging_setup import setup_logging
LOG = setup_logging("backfill_instrument_dates")
_NULL_COUNT_SQL = (
    "SELECT "
    "  SUM(first_seen_date IS NULL) AS null_fsd, "
    "  SUM(first_seen_date IS NOT NULL) AS notnull_fsd, "
    "  SUM(last_seen_date IS NULL) AS null_lsd, "
    "  SUM(last_seen_date IS NOT NULL) AS notnull_lsd "
    "FROM instruments"
)
_UPDATE_SQL = (
    "UPDATE instruments i "
    "LEFT JOIN ( "
    "  SELECT instrument_id, "
    "         MIN(trade_date) AS fsd, "
    "         MAX(trade_date) AS lsd "
    "  FROM daily_bars "
    "  GROUP BY instrument_id "
    ") d ON d.instrument_id = i.id "
    "SET i.first_seen_date = d.fsd, "
    "    i.last_seen_date  = d.lsd"
)
def _counts(conn):
    cur = conn.cursor()
    try:
        cur.execute(_NULL_COUNT_SQL)
        row = cur.fetchone()
    finally:
        cur.close()
    return tuple(int(v or 0) for v in row)
def main():
    try:
        with db.connection() as conn:
            before = _counts(conn)
            LOG.info(
                "before: fsd null=%d not-null=%d; lsd null=%d not-null=%d",
                *before,
            )
            cur = conn.cursor()
            try:
                cur.execute(_UPDATE_SQL)
                affected = cur.rowcount
            finally:
                cur.close()
            after = _counts(conn)
            LOG.info(
                "after:  fsd null=%d not-null=%d; lsd null=%d not-null=%d",
                *after,
            )
        print(f"backfill_instrument_dates: rowcount={affected}")
        print(
            f"  first_seen_date: null {before[0]} -> {after[0]}, "
            f"not-null {before[1]} -> {after[1]}"
        )
        print(
            f"  last_seen_date:  null {before[2]} -> {after[2]}, "
            f"not-null {before[3]} -> {after[3]}"
        )
        return 0
    except Exception as exc:
        LOG.exception("backfill failed")
        print(f"backfill_instrument_dates: FAILED - {exc}", file=sys.stderr)
        return 1
if __name__ == "__main__":
    sys.exit(main())