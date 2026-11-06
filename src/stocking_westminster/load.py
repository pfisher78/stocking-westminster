"""Load and clean the register CSV.

Published CSV headers (confirmed against Parliament's CSV release):

    ID, Summary, Parent Interest ID, Registered, Published, Updated_1,
    Category, MNIS ID, Member, Appg, PaymentType, PaymentDescription, Value,
    ReceivedDate, AcceptedDate, ReceivedEndDate, IsSoleBeneficiary,
    DonorName, DonorPublicAddress, DonorStatus, DonorCompanyName,
    DonorCompanyUrl, DonorCompanyIdentifier, DonorCompanyIdentifierSource,
    DonorTrustDetails, DonorOtherDetails, Link, Updated_2

We normalise to snake_case and parse dates/values. Everything downstream
works off the columns listed in CANON — extra columns pass through untouched
so schema additions don't break the pipeline.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

CANON = {
    "ID": "interest_id",
    "Summary": "summary",
    "Parent Interest ID": "parent_interest_id",
    "Registered": "registered",
    "Published": "published",
    "Category": "category",
    "MNIS ID": "mnis_id",
    "Member": "member",
    "Appg": "appg",
    "PaymentType": "payment_type",
    "PaymentDescription": "payment_description",
    "Value": "value",
    "ReceivedDate": "received_date",
    "AcceptedDate": "accepted_date",
    "ReceivedEndDate": "received_end_date",
    "IsSoleBeneficiary": "is_sole_beneficiary",
    "DonorName": "donor_name",
    "DonorPublicAddress": "donor_public_address",
    "DonorStatus": "donor_status",
    "DonorCompanyName": "donor_company_name",
    "DonorCompanyUrl": "donor_company_url",
    "DonorCompanyIdentifier": "donor_company_identifier",
    "DonorCompanyIdentifierSource": "donor_company_identifier_source",
    "DonorTrustDetails": "donor_trust_details",
    "DonorOtherDetails": "donor_other_details",
    "Link": "link",
}

DATE_COLS = ["registered", "published", "received_date", "accepted_date",
             "received_end_date"]


def _snake(col: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", col.strip().lower()).strip("_")


_MONEY = re.compile(r"[^\d.\-]")


def parse_value(v) -> float | None:
    """'£1,234.56' / '1234' / '' -> float or None."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    s = _MONEY.sub("", str(v))
    if s in ("", "-", ".", "-."):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def normalise_company_number(raw) -> str | None:
    """Companies House numbers: 8 chars. Pure digits get zero-padded
    ('345678' -> '00345678'); alpha prefixes (SC, NI, OC, RC, ...) kept as-is.
    Returns None for blanks and obvious non-CH identifiers."""
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    s = str(raw).strip().upper().replace(" ", "")
    if not s:
        return None
    if s.isdigit():
        if len(s) > 8:
            return None
        return s.zfill(8)
    if re.fullmatch(r"[A-Z]{2}\d{6}", s):
        return s
    return None


def _read_frames(path: Path) -> list[pd.DataFrame]:
    """Parliament's /Interests/csv endpoint returns a ZIP of per-category
    CSVs (PublishedInterest-Category_*.csv). Accept a zip, a directory of
    CSVs, or a single CSV — regardless of file extension (sniff PK magic)."""
    import io
    import zipfile

    if path.is_dir():
        return [pd.read_csv(p, dtype=str) for p in sorted(path.glob("*.csv"))]
    head = path.open("rb").read(4)
    if head[:2] == b"PK":
        frames = []
        with zipfile.ZipFile(path) as z:
            for name in sorted(z.namelist()):
                if name.lower().endswith(".csv"):
                    frames.append(
                        pd.read_csv(io.BytesIO(z.read(name)), dtype=str)
                    )
        return frames
    return [pd.read_csv(path, dtype=str)]


def load_register(path: Path) -> pd.DataFrame:
    frames = _read_frames(path)
    if not frames:
        raise RuntimeError(f"No CSV content found in {path}")
    df = pd.concat(frames, ignore_index=True)
    rename = {}
    canon_by_snake = {_snake(k): v for k, v in CANON.items()}
    for col in df.columns:
        key = _snake(col)
        # 'Updated' appears twice in the published file; pandas suffixes them.
        key = re.sub(r"_\d+$", "", key) if key.startswith("updated") else key
        rename[col] = canon_by_snake.get(key, key)
    df = df.rename(columns=rename)
    # De-duplicate any collided 'updated' columns
    df = df.loc[:, ~df.columns.duplicated()]

    if "value" in df.columns:
        df["value"] = df["value"].map(parse_value)
    for c in DATE_COLS:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce", format="mixed")
    if "donor_company_identifier" in df.columns:
        df["company_number"] = df["donor_company_identifier"].map(
            normalise_company_number
        )
        # Only trust the number when Parliament says it's a Companies House id
        # (or the source column is absent/blank — early registers).
        src = df.get("donor_company_identifier_source")
        if src is not None:
            bad = src.fillna("").str.strip().ne("") & ~src.fillna("").str.contains(
                "companies house", case=False
            )
            df.loc[bad, "company_number"] = None
    else:
        df["company_number"] = None
    return df
