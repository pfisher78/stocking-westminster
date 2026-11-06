"""Aggregate views. Each returns a tidy DataFrame ready for a chart.

These are the product. Everything else is plumbing.
"""

from __future__ import annotations

import pandas as pd

MONEY_CATEGORIES_HINT = (
    "Aggregations sum `value` only where present; registrable interests "
    "without a monetary value (e.g. some shareholdings) are counted, not summed."
)


def _money(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["value"].notna() & (df["value"] > 0)]


def top_payments(df: pd.DataFrame, n: int = 20) -> pd.DataFrame:
    """Biggest single registered payments/donations."""
    cols = [c for c in ["member", "party", "category", "donor_name",
                        "donor_company_name", "bucket", "value",
                        "received_date", "summary"] if c in df.columns]
    return (
        _money(df)[cols]
        .sort_values("value", ascending=False)
        .head(n)
        .reset_index(drop=True)
    )


def mp_totals(df: pd.DataFrame, n: int = 25) -> pd.DataFrame:
    """Per-MP total registered value (all categories with a value)."""
    g = (
        _money(df)
        .groupby(["member", "party"], dropna=False)["value"]
        .agg(total="sum", entries="count")
        .sort_values("total", ascending=False)
        .head(n)
        .reset_index()
    )
    return g


def sector_by_party(df: pd.DataFrame) -> pd.DataFrame:
    """Total value by narrative bucket x party. The headline chart."""
    d = _money(df)
    d = d[d["bucket"].notna()]
    return (
        d.pivot_table(
            index="bucket", columns="party", values="value",
            aggfunc="sum", fill_value=0.0,
        )
        .assign(total=lambda x: x.sum(axis=1))
        .sort_values("total", ascending=False)
        .reset_index()
    )


def sector_totals(df: pd.DataFrame) -> pd.DataFrame:
    d = _money(df)
    d = d[d["bucket"].notna()]
    return (
        d.groupby("bucket")["value"]
        .agg(total="sum", entries="count", mps=("nunique"))
        .sort_values("total", ascending=False)
        .reset_index()
    )


def resolution_rate(df: pd.DataFrame) -> dict:
    """Honesty metric for the pitch: how much of the register we can
    actually attribute to a sector. Quote this, don't hide it."""
    total = len(df)
    with_num = int(df["company_number"].notna().sum())
    with_sic = int(df["sic_codes"].map(bool).sum()) if "sic_codes" in df else 0
    with_bucket = int(df["bucket"].notna().sum()) if "bucket" in df else 0
    return {
        "rows": total,
        "with_company_number": with_num,
        "with_sic": with_sic,
        "with_bucket": with_bucket,
        "pct_bucketed": round(100 * with_bucket / total, 1) if total else 0.0,
    }
