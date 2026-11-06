"""Paths and endpoints. Everything configurable lives here."""

from __future__ import annotations

import os
from pathlib import Path

# Project root = two levels up from this file when installed editable,
# else current working directory.
_here = Path(__file__).resolve()
ROOT = Path(os.environ.get("SW_ROOT", Path.cwd()))

DATA = ROOT / "data"
RAW = DATA / "raw"
CACHE = DATA / "cache"
OUT = DATA / "out"

for _d in (RAW, CACHE, OUT):
    _d.mkdir(parents=True, exist_ok=True)

INTERESTS_API = "https://interests-api.parliament.uk/api/v1"
MEMBERS_API = "https://members-api.parliament.uk/api"
COMPANIES_HOUSE_API = "https://api.company-information.service.gov.uk"

CH_API_KEY_ENV = "COMPANIES_HOUSE_API_KEY"

USER_AGENT = "stocking-westminster/0.2 (civic-tech; Open Parliament Licence reuse)"

# Companies House: 600 requests / 5 minutes on the free tier.
CH_MAX_PER_WINDOW = 600
CH_WINDOW_SECONDS = 300


def ch_api_key() -> str:
    key = os.environ.get(CH_API_KEY_ENV, "").strip()
    if not key:
        raise RuntimeError(
            f"Set {CH_API_KEY_ENV}. Free key from "
            "https://developer.company-information.service.gov.uk/"
        )
    return key
