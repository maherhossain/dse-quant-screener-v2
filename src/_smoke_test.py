"""Smoke test for the Module 1a scaffold.
Verifies: paths, logging, DB connection, load_log round-trip.
Run with: py -m src._smoke_test
Exits 0 on success, 1 on failure. Prints one 'SMOKE OK: <run_id>' line.
"""
from __future__ import annotations
import sys
from src import paths
from src.db import connection, finish_load_log, start_load_log
from src.logging_setup import setup_logging
def main() -> int:
    log = setup_logging("smoke_test")
    log.info("smoke test starting; project_root=%s", paths.PROJECT_ROOT)
    run_id = None
    log_id = None
    try:
        # 1. DB connectivity
        with connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1")
            row = cur.fetchone()
            cur.close()
        assert row == (1,), f"SELECT 1 returned {row!r}"
        log.info("DB connectivity OK")
        # 2. load_log lifecycle
        run_id, log_id = start_load_log(
            target_table="load_log",
            source_provider="internal",
            source_endpoint="smoke_test",
            notes="Move 1a.6 smoke test",
        )
        log.info("start_load_log -> run_id=%s log_id=%s", run_id, log_id)
        # 3. read back (independent connection, raw SQL)
        with connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT run_id, status FROM load_log WHERE id = %s",
                (log_id,),
            )
            fetched = cur.fetchone()
            cur.close()
        assert fetched is not None, f"load_log row {log_id} not found after insert"
        assert fetched[0] == run_id, f"run_id mismatch: {fetched[0]!r} != {run_id!r}"
        assert fetched[1] == "RUNNING", f"status mismatch: {fetched[1]!r} != 'RUNNING'"
        log.info("load_log read-back OK")
        # 4. finalize
        finish_load_log(
            log_id,
            status="SMOKE_OK",
            rows_inserted=1,
            notes="Move 1a.6 smoke test finished",
        )
        log.info("finish_load_log OK")
        print(f"SMOKE OK: {run_id}")
        return 0
    except Exception as exc:
        log.exception("smoke test failed")
        # Try to mark the load_log row as FAILED if we got that far.
        if log_id is not None:
            try:
                finish_load_log(
                    log_id,
                    status="FAILED",
                    rows_failed=1,
                    error_message=str(exc)[:1024],
                    notes="Move 1a.6 smoke test failed",
                )
            except Exception:
                log.exception("could not mark load_log row as FAILED")
        print(f"SMOKE FAIL: {exc}", file=sys.stderr)
        return 1
if __name__ == "__main__":
    sys.exit(main())