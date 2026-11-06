"""Offline tests: fixture CSV + mocked Companies House. No network."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from stocking_westminster import sic
from stocking_westminster.buckets import Bucketer
from stocking_westminster.companies import Company
from stocking_westminster.load import (
    load_register,
    normalise_company_number,
    parse_value,
)
from stocking_westminster.pipeline import enrich
from stocking_westminster import views

FIXTURE = Path(__file__).parent / "fixture_register.csv"

MOCK_COMPANIES = {
    "00345678": Company("00345678", "BIGBANK LTD", ["64191"], "active", True),
    "SC123456": Company("SC123456", "OILCO PLC", ["06100"], "active", True),
    "87654321": Company("87654321", "BETWIN GROUP LTD", ["92000"], "active", True),
    "11223344": Company("11223344", "MEDIACORP LTD", ["58130"], "active", True),
    "99887766": Company("99887766", None, [], None, False),  # 404
}


# ---- load ------------------------------------------------------------------

def test_parse_value():
    assert parse_value("£20,000.00") == 20000.0
    assert parse_value("2500") == 2500.0
    assert parse_value("") is None
    assert parse_value(None) is None
    assert parse_value("£75.00") == 75.0


def test_normalise_company_number():
    assert normalise_company_number("345678") == "00345678"      # zero-pad
    assert normalise_company_number("SC123456") == "SC123456"    # Scottish
    assert normalise_company_number("not-a-company-number") is None
    assert normalise_company_number("") is None
    assert normalise_company_number(None) is None


def test_load_register_shapes():
    df = load_register(FIXTURE)
    assert len(df) == 7
    assert "member" in df.columns and "value" in df.columns
    assert df["value"].max() == 20000.0
    # Non-CH identifier source must be dropped
    row_1006 = df[df["interest_id"] == "1006"].iloc[0]
    assert pd.isna(row_1006["company_number"])
    # Dates parse
    assert pd.notna(df["registered"]).all()


# ---- sic -------------------------------------------------------------------

def test_sic_sections_cover_all_divisions():
    covered = set()
    for _l, (_n, ranges) in sic.SECTIONS.items():
        for lo, hi in ranges:
            covered.update(range(lo, hi + 1))
    # SIC 2007 has no divisions 04, 34, 40, 44, 48, 54, 57, 67, 76, 83, 89
    gaps = {4, 34, 40, 44, 48, 54, 57, 67, 76, 83, 89}
    assert covered == set(range(1, 100)) - gaps


def test_sic_lookup():
    assert sic.section("64191") == "K"
    assert sic.section("06100") == "B"
    assert sic.section_name("K") == "Financial and insurance activities"
    assert sic.section("garbage") is None


# ---- buckets ---------------------------------------------------------------

def test_bucketer_precedence_and_fallback():
    b = Bucketer()
    assert b.bucket_for_code("92000") == "Gambling"
    assert b.bucket_for_code("06100") == "Fossil fuels"
    assert b.bucket_for_code("64191") == "Banking & finance"
    assert b.bucket_for_code("58130") == "Media & publishing"
    # Unbucketed code falls back to section name via bucket_for_codes
    assert b.bucket_for_codes(["33110"]) == "Manufacturing"


# ---- pipeline + views ------------------------------------------------------

@pytest.fixture()
def enriched():
    df = load_register(FIXTURE)
    return enrich(df, MOCK_COMPANIES, members=None)


def test_enrich_joins_sic_and_bucket(enriched):
    by_id = enriched.set_index("interest_id")
    assert by_id.loc["1001", "bucket"] == "Banking & finance"
    assert by_id.loc["1002", "bucket"] == "Fossil fuels"
    assert by_id.loc["1003", "bucket"] == "Gambling"
    assert pd.isna(by_id.loc["1005", "bucket"])   # CH 404 -> no bucket
    assert pd.isna(by_id.loc["1007", "bucket"])   # individual donor


def test_views(enriched):
    top = views.top_payments(enriched, n=3)
    assert top.iloc[0]["value"] == 20000.0

    totals = views.mp_totals(enriched)
    alice = totals[totals["member"] == "Alice Example"].iloc[0]
    assert alice["total"] == 33000.0  # 20000 + 5000 + 8000

    sect = views.sector_totals(enriched)
    assert set(sect["bucket"]) == {
        "Banking & finance", "Fossil fuels", "Gambling", "Media & publishing"
    }

    rr = views.resolution_rate(enriched)
    assert rr["rows"] == 7
    assert rr["with_bucket"] == 4


# ---- zip loading (Parliament ships a ZIP of per-category CSVs) -------------

def test_load_register_from_zip():
    df = load_register(Path(__file__).parent / "fixture_register.zip")
    assert len(df) == 7
    assert df["value"].max() == 20000.0
    assert "company_number" in df.columns
