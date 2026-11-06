"""Map SIC codes -> narrative buckets defined in buckets.yaml."""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path

import yaml

from . import sic


def load_buckets(path: Path | None = None) -> list[dict]:
    text = (
        path.read_text()
        if path
        else files("stocking_westminster").joinpath("buckets.yaml").read_text()
    )
    return yaml.safe_load(text)["buckets"]


class Bucketer:
    def __init__(self, buckets: list[dict] | None = None):
        self.buckets = buckets or load_buckets()

    def bucket_for_code(self, sic_code: str) -> str | None:
        """Most-specific match wins: exact code, then division, then section —
        evaluated across all buckets at each specificity level, in file order."""
        code = str(sic_code).strip()
        div = sic.division(code)
        sec = sic.section(code)
        for b in self.buckets:
            if code in [str(c) for c in b.get("codes", [])]:
                return b["name"]
        for b in self.buckets:
            if div is not None and div in b.get("divisions", []):
                return b["name"]
        for b in self.buckets:
            if sec is not None and sec in b.get("sections", []):
                return b["name"]
        return None

    def bucket_for_codes(self, sic_codes: list[str]) -> str | None:
        """A company can carry up to 4 SIC codes; take the first that maps,
        else fall back to the first code's section name."""
        for c in sic_codes:
            hit = self.bucket_for_code(c)
            if hit:
                return hit
        for c in sic_codes:
            name = sic.section_name(sic.section(c))
            if name:
                return name
        return None
