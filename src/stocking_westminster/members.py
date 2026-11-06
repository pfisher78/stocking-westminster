"""MP metadata: MNIS ID -> name/party via the Members API. JSON-file cached.

GET https://members-api.parliament.uk/api/Members/{id}
No auth. ~650 distinct IDs per register, so one full pass is trivial.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import requests

from .config import CACHE, MEMBERS_API, USER_AGENT

CACHE_PATH = CACHE / "members.json"


class Members:
    def __init__(self, cache_path: Path = CACHE_PATH):
        self._path = cache_path
        self._cache: dict[str, dict] = (
            json.loads(cache_path.read_text()) if cache_path.exists() else {}
        )
        self._session = requests.Session()
        self._session.headers["User-Agent"] = USER_AGENT

    def _save(self) -> None:
        self._path.write_text(json.dumps(self._cache))

    def get(self, mnis_id: str | int) -> dict:
        key = str(int(float(mnis_id)))  # tolerate '4514.0' from CSV round-trip
        if key in self._cache:
            return self._cache[key]
        r = self._session.get(f"{MEMBERS_API}/Members/{key}", timeout=30)
        if r.status_code == 404:
            info = {"name": None, "party": None}
        else:
            r.raise_for_status()
            v = r.json().get("value", {})
            info = {
                "name": v.get("nameDisplayAs"),
                "party": (v.get("latestParty") or {}).get("name"),
            }
        self._cache[key] = info
        self._save()
        time.sleep(0.05)
        return info

    def party(self, mnis_id: str | int) -> str | None:
        return self.get(mnis_id).get("party")
