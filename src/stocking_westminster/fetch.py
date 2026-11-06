"""Fetch the Register of Members' Financial Interests.

CSV endpoint (confirmed against the official publications page,
members.parliament.uk/members/commons/interests/publications):

    GET {INTERESTS_API}/Interests/csv?registerId={id}

Notes:
- The CSV is generated server-side on request and can take a minute or two
  for a full register — hence the long timeout and streaming download.
- The /Registers list can contain ids beyond the newest *published Commons*
  register (e.g. Lords or not-yet-published entries), so we walk down the
  id list until an id yields a valid CSV.
- Row-level JSON endpoint kept as a fallback: `sw fetch --json`.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import requests

from .config import INTERESTS_API, RAW, USER_AGENT

_session = requests.Session()
_session.headers["User-Agent"] = USER_AGENT

CSV_TIMEOUT = 600  # server generates the file on demand; be patient


def _get(url: str, **params) -> dict:
    r = _session.get(url, params=params or None, timeout=60)
    r.raise_for_status()
    return r.json()


def list_registers(take: int = 50) -> list[dict]:
    payload = _get(f"{INTERESTS_API}/Registers", Skip=0, Take=take)
    return payload.get("items", [])


def candidate_register_ids(house: str = "Commons") -> list[int]:
    """Register ids, newest first, preferring entries tagged with `house`."""
    items = list_registers()
    if not items:
        raise RuntimeError("Registers endpoint returned no items")
    tagged = [it for it in items if house.lower() in json.dumps(it).lower()]
    pool = tagged or items
    return sorted({it["id"] for it in pool if "id" in it}, reverse=True)


def download_register_csv(register_id: int, dest: Path | None = None) -> Path:
    """Download the register CSV via /Interests/csv?registerId=."""
    dest = dest or RAW / f"register_{register_id}.csv"
    with _session.get(
        f"{INTERESTS_API}/Interests/csv",
        params={"registerId": register_id},
        timeout=CSV_TIMEOUT,
        stream=True,
    ) as r:
        r.raise_for_status()
        tmp = dest.with_suffix(".part")
        with tmp.open("wb") as fh:
            for chunk in r.iter_content(chunk_size=1 << 16):
                fh.write(chunk)
        head = tmp.read_bytes()[:200].lstrip()
        if head.startswith(b"%PDF") or head.startswith(b"<"):
            tmp.unlink()
            raise RuntimeError(
                f"registerId={register_id} returned non-CSV content"
            )
        if head[:2] == b"PK":  # ZIP of per-category CSVs — the normal case
            dest = dest.with_suffix(".zip")
        tmp.rename(dest)
    return dest


def fetch_interests_json(
    dest: Path | None = None,
    page_size: int = 500,
    sleep: float = 0.2,
) -> Path:
    """Fallback: paginate the row-level Interests endpoint to JSONL."""
    dest = dest or RAW / "interests.jsonl"
    skip, total = 0, None
    with dest.open("w", encoding="utf-8") as fh:
        while total is None or skip < total:
            payload = _get(
                f"{INTERESTS_API}/Interests", Skip=skip, Take=page_size
            )
            total = payload.get("totalResults", 0)
            items = payload.get("items", [])
            if not items:
                break
            for item in items:
                fh.write(json.dumps(item) + "\n")
            skip += len(items)
            print(f"  fetched {skip}/{total}", end="\r")
            time.sleep(sleep)
    print()
    return dest


def fetch_latest(json_fallback: bool = False) -> Path:
    if json_fallback:
        return fetch_interests_json()
    errors: list[str] = []
    for reg_id in candidate_register_ids()[:6]:
        try:
            print(f"Trying register id={reg_id} "
                  "(CSV is generated server-side; this can take a minute)...")
            path = download_register_csv(reg_id)
            size = path.stat().st_size
            if size < 5_000:  # zips compress well; tiny files are error pages
                path.unlink()
                errors.append(f"id={reg_id}: suspiciously small ({size} B)")
                continue
            print(f"Saved {path} ({size/1e6:.1f} MB)")
            return path
        except Exception as e:  # noqa: BLE001 — try the next id
            errors.append(f"id={reg_id}: {e}")
    raise RuntimeError(
        "No register id yielded a CSV. Tried:\n  " + "\n  ".join(errors)
        + "\nFallback: `sw fetch --json`."
    )
