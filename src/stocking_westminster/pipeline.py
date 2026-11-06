"""Enrichment pipeline: register rows -> +company +SIC +bucket +party."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .buckets import Bucketer
from .companies import CompaniesHouse, Company
from .load import load_register
from .members import Members
from . import sic


def enrich(
    df: pd.DataFrame,
    companies: dict[str, Company],
    members: Members | None = None,
) -> pd.DataFrame:
    """Pure function over a loaded register frame + resolved companies.
    `members` is optional so tests can run fully offline."""
    bucketer = Bucketer()
    out = df.copy()

    def _sic_codes(num):
        c = companies.get(num)
        return c.sic_codes if c and c.found else []

    def _ch_name(num):
        c = companies.get(num)
        return c.name if c and c.found else None

    out["sic_codes"] = out["company_number"].map(_sic_codes)
    out["ch_company_name"] = out["company_number"].map(_ch_name)
    out["sic_section"] = out["sic_codes"].map(
        lambda codes: sic.section(codes[0]) if codes else None
    )
    out["sic_section_name"] = out["sic_section"].map(sic.section_name)
    out["bucket"] = out["sic_codes"].map(
        lambda codes: bucketer.bucket_for_codes(codes) if codes else None
    )

    if members is not None and "mnis_id" in out.columns:
        parties = {
            m: members.party(m)
            for m in out["mnis_id"].dropna().unique()
        }
        out["party"] = out["mnis_id"].map(parties)
    elif "party" not in out.columns:
        out["party"] = None
    return out


def run(register_csv: Path, offline_companies: dict[str, Company] | None = None,
        with_party: bool = True) -> pd.DataFrame:
    df = load_register(register_csv)
    numbers = df["company_number"].dropna().unique().tolist()
    if offline_companies is not None:
        companies = offline_companies
    else:
        companies = CompaniesHouse().resolve_all(numbers)
    members = Members() if with_party else None
    return enrich(df, companies, members)
