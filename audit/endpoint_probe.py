from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "audit" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_TIMEOUT = 30
SUMMARY_CHARS = 1500


def _sanitize(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("_")[:80] or "root"


def _filename_for(url: str, content_type: str) -> str:
    parsed = urlparse(url)
    host = _sanitize(parsed.netloc)
    path = _sanitize(parsed.path.strip("/")) or "index"
    query_hash = hashlib.sha1(parsed.query.encode("utf-8")).hexdigest()[:8]
    ext = "json" if "json" in content_type.lower() else (
        "html" if "html" in content_type.lower() else "txt"
    )
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{stamp}__{host}__{path}__{query_hash}.{ext}"


def _parse_headers(pairs: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for p in pairs or []:
        if ":" not in p:
            raise SystemExit(f"--header must be 'Name: Value', got: {p!r}")
        name, _, value = p.partition(":")
        out[name.strip()] = value.strip()
    return out


def _summarize(body: str, content_type: str) -> str:
    if "json" in content_type.lower():
        try:
            obj = json.loads(body)
            if isinstance(obj, list):
                head = f"JSON array, length={len(obj)}"
                sample = json.dumps(obj[:2], indent=2, ensure_ascii=False)
                return f"{head}\n\nFirst 2 items:\n{sample[:SUMMARY_CHARS]}"
            if isinstance(obj, dict):
                keys = list(obj.keys())
                head = f"JSON object, top-level keys ({len(keys)}): {keys[:30]}"
                sample = json.dumps(obj, indent=2, ensure_ascii=False)
                return f"{head}\n\nFirst {SUMMARY_CHARS} chars:\n{sample[:SUMMARY_CHARS]}"
            return f"JSON scalar: {obj!r}"
        except json.JSONDecodeError:
            pass
    return body[:SUMMARY_CHARS]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Probe one API endpoint.")
    ap.add_argument("url")
    ap.add_argument("--header", action="append", default=[])
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    args = ap.parse_args(argv)

    headers = _parse_headers(args.header)

    print(f"[probe] GET {args.url}")
    if headers:
        print(f"[probe] headers: {headers}")

    try:
        resp = requests.get(args.url, headers=headers, timeout=args.timeout)
    except requests.RequestException as exc:
        print(f"[probe] FAILED: {exc!r}")
        return 2

    content_type = resp.headers.get("Content-Type", "")
    body = resp.text

    raw_path = RAW_DIR / _filename_for(args.url, content_type)
    raw_path.write_text(body, encoding="utf-8", errors="replace")

    print(f"[probe] status: {resp.status_code} {resp.reason}")
    print(f"[probe] content-type: {content_type or '(none)'}")
    print(f"[probe] body bytes: {len(resp.content)}")
    print(f"[probe] saved raw: {raw_path}")
    print("-" * 72)
    print(_summarize(body, content_type))
    print("-" * 72)

    return 0 if resp.ok else 1


if __name__ == "__main__":
    sys.exit(main())