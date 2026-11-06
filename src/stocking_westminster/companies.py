"""Companies House lookup: company number -> SIC codes, cached in sqlite.

Auth: HTTP Basic with the API key as username, blank password.
Free tier: 600 requests / 5 minutes — we throttle to stay under it.
~650 MPs' donors resolve to a few thousand distinct company numbers, so a
full resolve pass fits comfortably in under an hour on first run and is
instant thereafter (cache).
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

import requests

from .config import (
    CACHE,
    CH_MAX_PER_WINDOW,
    CH_WINDOW_SECONDS,
    COMPANIES_HOUSE_API,
    USER_AGENT,
    ch_api_key,
)

DB_PATH = CACHE / "companies.sqlite"


@dataclass
class Company:
    number: str
    name: str | None
    sic_codes: list[str]
    status: str | None
    found: bool


class CompaniesHouse:
    def __init__(self, api_key: str | None = None, db_path: Path = DB_PATH):
        self._key = api_key
        self._db = sqlite3.connect(db_path)
        self._db.execute(
            """CREATE TABLE IF NOT EXISTS companies (
                   number TEXT PRIMARY KEY,
                   name TEXT,
                   sic_codes TEXT,   -- JSON list
                   status TEXT,
                   found INTEGER NOT NULL,
                   fetched_at REAL NOT NULL
               )"""
        )
        self._session = requests.Session()
        self._session.headers["User-Agent"] = USER_AGENT
        self._times: list[float] = []  # request timestamps for throttling

    # -- cache -------------------------------------------------------------

    def _cached(self, number: str) -> Company | None:
        row = self._db.execute(
            "SELECT name, sic_codes, status, found FROM companies WHERE number=?",
            (number,),
        ).fetchone()
        if row is None:
            return None
        name, sic_json, status, found = row
        return Company(number, name, json.loads(sic_json or "[]"), status, bool(found))

    def _store(self, c: Company) -> None:
        self._db.execute(
            "INSERT OR REPLACE INTO companies VALUES (?,?,?,?,?,?)",
            (c.number, c.name, json.dumps(c.sic_codes), c.status,
             int(c.found), time.time()),
        )
        self._db.commit()

    # -- rate limiting -----------------------------------------------------

    def _throttle(self) -> None:
        now = time.time()
        self._times = [t for t in self._times if now - t < CH_WINDOW_SECONDS]
        if len(self._times) >= CH_MAX_PER_WINDOW - 10:  # safety margin
            wait = CH_WINDOW_SECONDS - (now - self._times[0]) + 1
            print(f"  [rate limit] sleeping {wait:.0f}s")
            time.sleep(max(wait, 0))
        self._times.append(time.time())

    # -- lookup ------------------------------------------------------------

    def get(self, number: str) -> Company:
        cached = self._cached(number)
        if cached is not None:
            return cached
        self._throttle()
        key = self._key or ch_api_key()
        r = self._session.get(
            f"{COMPANIES_HOUSE_API}/company/{number}",
            auth=(key, ""),
            timeout=30,
        )
        if r.status_code == 404:
            c = Company(number, None, [], None, found=False)
        elif r.status_code == 429:
            time.sleep(30)
            return self.get(number)
        else:
            r.raise_for_status()
            j = r.json()
            c = Company(
                number=number,
                name=j.get("company_name"),
                sic_codes=[str(s) for s in j.get("sic_codes", [])],
                status=j.get("company_status"),
                found=True,
            )
        self._store(c)
        return c

    def resolve_all(self, numbers: list[str]) -> dict[str, Company]:
        out: dict[str, Company] = {}
        todo = [n for n in dict.fromkeys(numbers) if n]
        for i, n in enumerate(todo, 1):
            out[n] = self.get(n)
            if i % 50 == 0:
                print(f"  resolved {i}/{len(todo)}")
        return out
