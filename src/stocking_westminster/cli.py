"""CLI: `sw fetch`, `sw resolve`, `sw report`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from . import views
from .companies import CompaniesHouse
from .config import OUT, RAW
from .fetch import fetch_latest
from .load import load_register
from .pipeline import enrich
from .members import Members


def _latest_raw() -> Path:
    candidates = (
        sorted(RAW.glob("register_*.csv"))
        + sorted(RAW.glob("register_*.zip"))
        + sorted(RAW.glob("*.csv"))
        + sorted(RAW.glob("*.zip"))
    )
    if not candidates:
        sys.exit("No register CSV/zip in data/raw/ — run `sw fetch` first.")
    return candidates[-1]


def cmd_fetch(args) -> None:
    fetch_latest(json_fallback=args.json)


def cmd_resolve(args) -> None:
    df = load_register(_latest_raw())
    numbers = df["company_number"].dropna().unique().tolist()
    print(f"{len(df)} rows, {len(numbers)} distinct company numbers")
    ch = CompaniesHouse()
    ch.resolve_all(numbers)
    print("Done — cached in data/cache/companies.sqlite")


def cmd_report(args) -> None:
    raw = _latest_raw()
    df = load_register(raw)
    numbers = df["company_number"].dropna().unique().tolist()
    ch = CompaniesHouse()
    companies = {n: ch.get(n) for n in numbers}
    members = None if args.no_party else Members()
    e = enrich(df, companies, members)

    outputs = {
        "top_payments.csv": views.top_payments(e, n=50),
        "mp_totals.csv": views.mp_totals(e, n=100),
        "sector_by_party.csv": views.sector_by_party(e),
        "sector_totals.csv": views.sector_totals(e),
    }
    for name, frame in outputs.items():
        frame.to_csv(OUT / name, index=False)

    rr = views.resolution_rate(e)
    pd.set_option("display.width", 120)

    print(f"\nSource: {raw.name} — {rr['rows']} rows, "
          f"{rr['pct_bucketed']}% attributable to a sector "
          f"({rr['with_company_number']} rows carry a company number)\n")

    print("=== HEADLINE 1: biggest single registered payments ===")
    print(views.top_payments(e, n=5).to_string(index=False, max_colwidth=40))
    print("\n=== HEADLINE 2: sector totals ===")
    print(views.sector_totals(e).head(10).to_string(index=False))
    print("\n=== HEADLINE 3: top MPs by registered value ===")
    print(views.mp_totals(e, n=10).to_string(index=False))
    print(f"\nFull tables written to {OUT}/")
    print("Those three tables are the pitch. Send the pitch.")


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="sw", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fetch", help="download latest register CSV")
    f.add_argument("--json", action="store_true",
                   help="paginate the JSON Interests endpoint instead")
    f.set_defaults(func=cmd_fetch)

    r = sub.add_parser("resolve", help="resolve company numbers via Companies House")
    r.set_defaults(func=cmd_resolve)

    rep = sub.add_parser("report", help="build aggregate views + print headlines")
    rep.add_argument("--no-party", action="store_true",
                     help="skip the Members API party join")
    rep.set_defaults(func=cmd_report)

    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
