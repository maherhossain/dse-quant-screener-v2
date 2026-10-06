"""Backfill the index_bars table.
Sources:
  - endpoint #7: https://provider.bullbd.com/shares/get-one-for-tv2?code={CODE}
      OHLC + constituent volume. Archive floor 2014-03-02.
  - endpoint #6: https://stocknow.com.bd/api/v1/instruments/{CODE}/history
      Used for:
        * turnover_market_million on broad indices (whole-market turnover)
        * DSEX OHLC gap-fill for 2013-01-28 -> 2014-03-01
Sources are recorded per-row via source_ohlc / source_volume / source_turnover.
Idempotent: INSERT ... ON DUPLICATE KEY UPDATE on (index_id, trade_date).
Run: py -m src.loaders.load_index_bars
"""
from __future__ import annotations
from urllib.parse import quote
import sys
from datetime import date, datetime, timezone
from typing import Any
from src import db, paths
from src.http_client import fetch_json
from src.logging_setup import setup_logging
LOG = setup_logging("load_index_bars")
TARGET_TABLE = "index_bars"
EP7_URL = "https://provider.bullbd.com/shares/get-one-for-tv2?code={code}"
EP7_SOURCE = "bullbd"
EP6_URL = (
    "https://stocknow.com.bd/api/v1/instruments/{code}/history"
    "?data2=true&resolution=1D&skip={skip}"
)
EP6_SOURCE = "stocknow"
DSEX_GAP_FROM = date(2013, 1, 28)
DSEX_GAP_TO = date(2014, 3, 1)
BROAD_CODES = {"DSEX", "DS30", "DSES"}
def _fetch_endpoint7(code: str):
    url = EP7_URL.format(code=quote(code, safe=""))
    result = fetch_json(url, cache_dir=paths.AUDIT_RAW_DIR)
    data = result.data
    if not isinstance(data, dict):
        raise ValueError(f"endpoint #7 [{code}] not an object: {type(data).__name__}")
    for key in ("o", "h", "l", "c", "v", "d"):
        if key not in data:
            raise ValueError(f"endpoint #7 [{code}] missing key: {key!r}")
        if not isinstance(data[key], list):
            raise ValueError(f"endpoint #7 [{code}] key {key!r} is not a list")
    n = len(data["d"])
    for key in ("o", "h", "l", "c", "v"):
        if len(data[key]) != n:
            raise ValueError(
                f"endpoint #7 [{code}] length mismatch: d={n}, {key}={len(data[key])}"
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
        dates.append(dt)
        opens.append(float(data["o"][i]))
        highs.append(float(data["h"][i]))
        lows.append(float(data["l"][i]))
        closes.append(float(data["c"][i]))
        v = data["v"][i]
        vols.append(int(v) if v is not None else 0)
    return dates, opens, highs, lows, closes, vols
def _fetch_endpoint6_page(code: str, skip: int):
    url = EP6_URL.format(code=quote(code, safe=""), skip=skip)
    result = fetch_json(url, cache_dir=paths.AUDIT_RAW_DIR)
    data = result.data
    if not isinstance(data, list) or len(data) != 6:
        raise ValueError(
            f"endpoint #6 [{code}] skip={skip} expected 6 arrays, got "
            f"{type(data).__name__} len={len(data) if isinstance(data, list) else 'n/a'}"
        )
    return data
def _fetch_endpoint6_all(code: str, max_pages: int = 50):
    all_rows = [[], [], [], [], [], []]
    for page in range(max_pages):
        skip = page * 400
        payload = _fetch_endpoint6_page(code, skip)
        if len(payload[5]) == 0:
            break
        for i in range(6):
            all_rows[i].extend(payload[i])
        if len(payload[5]) < 400:
            break
    else:
        LOG.warning("endpoint #6 [%s] hit max_pages=%d", code, max_pages)
    return all_rows
def _parse_endpoint6(payload, from_date, to_date):
    ts = payload[5]
    o = payload[0]
    h = payload[1]
    l = payload[2]
    c = payload[3]
    col4 = payload[4]
    n = len(ts)
    for arr, name in ((o, "o"), (h, "h"), (l, "l"), (c, "c"), (col4, "col4")):
        if len(arr) != n:
            raise ValueError(f"endpoint #6 length mismatch: ts={n}, {name}={len(arr)}")
    dates = []
    opens = []
    highs = []
    lows = []
    closes = []
    vals = []
    for i in range(n):
        dt = _parse_ep6_timestamp(ts[i])
        if from_date and dt < from_date:
            continue
        if to_date and dt > to_date:
            continue
        dates.append(dt)
        opens.append(float(o[i]))
        highs.append(float(h[i]))
        lows.append(float(l[i]))
        closes.append(float(c[i]))
        vals.append(float(col4[i]) if col4[i] is not None else 0.0)
    return dates, opens, highs, lows, closes, vals
def _parse_ep6_timestamp(raw):
    if isinstance(raw, (int, float)):
        return datetime.fromtimestamp(raw / 1000, tz=timezone.utc).date()
    if isinstance(raw, str):
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
        except ValueError:
            pass
        try:
            return datetime.fromtimestamp(int(raw) / 1000, tz=timezone.utc).date()
        except (ValueError, TypeError) as exc:
            raise ValueError(f"Unparseable endpoint #6 timestamp: {raw!r}") from exc
    raise ValueError(f"Unsupported endpoint #6 timestamp type: {type(raw).__name__}")
def _upsert_index_bars(conn, rows):
    if not rows:
        return 0
    sql = (
        "INSERT INTO index_bars "
        "(index_id, trade_date, open, high, low, close, "
        " volume_constituent, turnover_market_million, "
        " source_ohlc, source_volume, source_turnover) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
        "ON DUPLICATE KEY UPDATE "
        "  open = VALUES(open), high = VALUES(high), "
        "  low = VALUES(low), close = VALUES(close), "
        "  volume_constituent = VALUES(volume_constituent), "
        "  turnover_market_million = VALUES(turnover_market_million), "
        "  source_ohlc = VALUES(source_ohlc), "
        "  source_volume = VALUES(source_volume), "
        "  source_turnover = VALUES(source_turnover)"
    )
    cur = conn.cursor()
    try:
        cur.executemany(sql, rows)
    finally:
        cur.close()
    return len(rows)
def _load_one_index(conn, idx_id, code, kind):
    rows = []
    d7, o7, h7, l7, c7, v7 = _fetch_endpoint7(code)
    LOG.info("[%s] endpoint #7: %d bars", code, len(d7))
    for i in range(len(d7)):
        rows.append((
            idx_id, d7[i], o7[i], h7[i], l7[i], c7[i],
            v7[i], None,
            EP7_SOURCE, EP7_SOURCE, None,
        ))
    turnover_map = {}
    if code in BROAD_CODES:
        try:
            payload = _fetch_endpoint6_all(code)
            d6, _o6, _h6, _l6, _c6, col4 = _parse_endpoint6(payload, None, None)
            for i, dt in enumerate(d6):
                turnover_map[dt] = col4[i] / 1e6
            LOG.info("[%s] endpoint #6 turnover: %d days", code, len(turnover_map))
        except Exception as exc:
            LOG.error("[%s] endpoint #6 turnover fetch failed: %s", code, exc)
    if turnover_map:
        new_rows = []
        for r in rows:
            idx_id_, td, o, h, l, c, v, _turn, so, sv, st = r
            turn = turnover_map.get(td)
            new_rows.append((
                idx_id_, td, o, h, l, c, v, turn,
                so, sv, EP6_SOURCE if turn is not None else st,
            ))
        rows = new_rows
    if code == "DSEX":
        try:
            payload = _fetch_endpoint6_all(code)
            d6, o6, h6, l6, c6, col4 = _parse_endpoint6(
                payload, DSEX_GAP_FROM, DSEX_GAP_TO
            )
            existing_dates = {r[1] for r in rows}
            gap_count = 0
            for i, dt in enumerate(d6):
                if dt in existing_dates:
                    continue
                rows.append((
                    idx_id, dt, o6[i], h6[i], l6[i], c6[i],
                    None, col4[i] / 1e6,
                    EP6_SOURCE, None, EP6_SOURCE,
                ))
                gap_count += 1
            LOG.info("[%s] endpoint #6 gap-fill: %d bars added", code, gap_count)
        except Exception as exc:
            LOG.error("[%s] endpoint #6 gap-fill failed: %s", code, exc)
    # --- diagnostic: check OHLC sanity ---
    bad = []
    for r in rows:
        idx_id_, td, o, h, l, c, v, turn, so, sv, st = r
        if not (h >= l and h >= o and h >= c and l <= o and l <= c):
            bad.append((td, o, h, l, c))
    if bad:
        LOG.warning("[%s] %d rows fail OHLC constraint; first 5: %s",
                    code, len(bad), bad[:5])
        # Drop bad rows for now; diagnose before re-enabling insert of all.
        rows = [r for r in rows if (r[3] >= r[4] and r[3] >= r[2] and r[3] >= r[5]
                                    and r[4] <= r[2] and r[4] <= r[5])]
    LOG.info("[%s] after OHLC filter: %d rows remain", code, len(rows))
    # --- end diagnostic ---

    submitted = _upsert_index_bars(conn, rows)
    return submitted, "SUCCESS"
def _load_all_indices():
    with db.connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, code, kind FROM indices ORDER BY id")
        rows = list(cur.fetchall())
        cur.close()
    return [(int(r[0]), str(r[1]), str(r[2])) for r in rows]
def main():
    total_submitted = 0
    total_failed = 0
    results = []
    indices = _load_all_indices()
    LOG.info("loaded %d indices from reference table", len(indices))
    for idx_id, code, kind in indices:
        run_id = None
        log_id = None
        try:
            run_id, log_id = db.start_load_log(
                target_table=TARGET_TABLE,
                source_provider=f"{EP7_SOURCE}+{EP6_SOURCE}",
                source_endpoint=EP7_URL.format(code=code),
                notes=f"code={code}, kind={kind}",
            )
            LOG.info("=== [%s] run_id=%s log_id=%s ===", code, run_id, log_id)
            with db.connection() as conn:
                submitted, status = _load_one_index(conn, idx_id, code, kind)
            db.finish_load_log(
                log_id,
                status=status,
                rows_inserted=submitted,
                notes=f"code={code}, kind={kind}",
            )
            total_submitted += submitted
            results.append((code, submitted, status))
            LOG.info("[%s] done: %d rows", code, submitted)
        except Exception as exc:
            LOG.exception("[%s] load failed", code)
            if log_id is not None:
                try:
                    db.finish_load_log(
                        log_id,
                        status="FAILED",
                        error_message=str(exc)[:1024],
                        notes=f"code={code}, kind={kind}",
                    )
                except Exception:
                    LOG.exception("[%s] could not mark load_log row as FAILED", code)
            total_failed += 1
            results.append((code, 0, "FAILED"))
    print(f"index_bars: {len(results)} indices processed, "
          f"{total_submitted} rows upserted, {total_failed} failed")
    for code, n, status in results:
        print(f"  {code:30s} {status:8s} {n:6d} rows")
    return 0 if total_failed == 0 else 2
if __name__ == "__main__":
    sys.exit(main())