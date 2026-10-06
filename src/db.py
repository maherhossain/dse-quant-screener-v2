"""Database access for the project.
Two responsibilities:
  1. Open MySQL connections using .env credentials.
  2. Write load_log entries for every load event.
No connection pooling, no ORM. Loaders are short-lived scripts; they open
a connection, do their work, close it. Use context managers.
"""
from __future__ import annotations
import logging
import os
import socket
import subprocess
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator, Optional
import mysql.connector
from dotenv import load_dotenv
from mysql.connector import MySQLConnection
from src import paths
logger = logging.getLogger(__name__)
# Load .env once at import time. Missing file is fine (env may come from
# the shell); we check for required keys at connection time instead.
load_dotenv(paths.ENV_FILE)
def _db_config() -> dict[str, Any]:
    """Build the mysql-connector config dict from environment variables.
    Fails loudly if a required key is missing — we do not want a loader to
    silently connect to the wrong database.
    """
    required = ["DB_HOST", "DB_USER", "DB_NAME"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        raise RuntimeError(
            f"Missing DB env vars: {missing}. Check .env at {paths.ENV_FILE}."
        )
    return {
        "host": os.environ["DB_HOST"],
        "port": int(os.environ.get("DB_PORT", "3306")),
        "user": os.environ["DB_USER"],
        "password": os.environ.get("DB_PASSWORD", ""),
        "database": os.environ["DB_NAME"],
        "autocommit": False,
        "charset": "utf8mb4",
        "use_pure": True,
    }
def get_connection() -> MySQLConnection:
    """Open a new MySQL connection. Caller is responsible for closing it."""
    cfg = _db_config()
    return mysql.connector.connect(**cfg)
@contextmanager
def connection() -> Iterator[MySQLConnection]:
    """Context manager: yields a connection, commits on success, rolls back
    on exception, always closes.

    Defensive against unread result sets on open cursors: consume_results()
    drains them before commit. This is safe to call even when no cursor
    has an unread result.
    """
    conn = get_connection()
    try:
        yield conn
        try:
            conn.consume_results()
        except Exception as exc:
            # consume_results() raises if there's nothing to consume on
            # some connector versions; that's expected and harmless.
            logger.debug("consume_results() before commit raised: %s", exc)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def _git_commit_hash() -> Optional[str]:
    """Return the current git HEAD hash, or None if unavailable.
    Failure is logged at WARNING, not swallowed — see operating rules.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=paths.PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        return result.stdout.strip() or None
    except (subprocess.SubprocessError, FileNotFoundError) as exc:
        logger.warning("Could not read git commit hash: %s", exc)
        return None
def new_run_id() -> str:
    """Generate a run_id: 17 chars, sortable, unique enough for our scale.
    Format: YYYYMMDDTHHMMSS-xxxxxxxx  (8 + 1 + 8 = 17)
    """
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"{ts}-{uuid.uuid4().hex[:8]}"
def start_load_log(
    target_table: str,
    source_provider: str,
    *,
    source_endpoint: Optional[str] = None,
    scope_date_from: Optional[datetime] = None,
    scope_date_to: Optional[datetime] = None,
    notes: Optional[str] = None,
    conn: Optional[MySQLConnection] = None,
) -> tuple[str, int]:
    """Insert a load_log row with status='RUNNING'. Returns (run_id, log_id).
    If conn is provided, uses it (caller manages commit). Otherwise opens
    its own connection and commits immediately.
    """
    run_id = new_run_id()
    started_at = datetime.now().replace(microsecond=0)
    commit_hash = _git_commit_hash()
    host = socket.gethostname()
    sql = (
        "INSERT INTO load_log "
        "(run_id, started_at, target_table, source_provider, source_endpoint, "
        " scope_date_from, scope_date_to, status, git_commit_hash, hostname, notes) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
    )
    params = (
        run_id, started_at, target_table, source_provider, source_endpoint,
        scope_date_from, scope_date_to, "RUNNING", commit_hash, host, notes,
    )
    if conn is not None:
        cur = conn.cursor()
        cur.execute(sql, params)
        log_id = cur.lastrowid
        cur.close()
        return run_id, log_id
    with connection() as own_conn:
        cur = own_conn.cursor()
        cur.execute(sql, params)
        log_id = cur.lastrowid
        cur.close()
    return run_id, log_id
def finish_load_log(
    log_id: int,
    *,
    status: str,
    rows_inserted: int = 0,
    rows_skipped: int = 0,
    rows_failed: int = 0,
    error_message: Optional[str] = None,
    notes: Optional[str] = None,
    conn: Optional[MySQLConnection] = None,
) -> None:
    """Update a load_log row with final status and counts.
    status values: 'SUCCESS', 'PARTIAL', 'FAILED'. (RUNNING is the initial state.)
    """
    if len(status) > 16:
        raise ValueError(f"status too long for VARCHAR(16): {status!r}")
    sql = (
        "UPDATE load_log SET "
        "finished_at = %s, status = %s, rows_inserted = %s, "
        "rows_skipped = %s, rows_failed = %s, error_message = %s, "
        "notes = COALESCE(%s, notes) "
        "WHERE id = %s"
    )
    params = (
        datetime.now().replace(microsecond=0),
        status, rows_inserted, rows_skipped, rows_failed, error_message,
        notes, log_id,
    )
    if conn is not None:
        cur = conn.cursor()
        cur.execute(sql, params)
        cur.close()
        return
    with connection() as own_conn:
        cur = own_conn.cursor()
        cur.execute(sql, params)
        cur.close()
__all__ = [
    "get_connection",
    "connection",
    "new_run_id",
    "start_load_log",
    "finish_load_log",
]