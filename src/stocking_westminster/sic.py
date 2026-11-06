"""SIC 2007 spine.

Companies House returns 5-digit SIC 2007 codes ('64110'). The first two
digits are the *division*; divisions roll up into 21 lettered *sections*.
Sections are the coarse layer; narrative buckets (buckets.yaml) key off
divisions and full codes for finer control.
"""

from __future__ import annotations

# Section letter -> (name, [division ranges])
SECTIONS: dict[str, tuple[str, list[tuple[int, int]]]] = {
    "A": ("Agriculture, forestry and fishing", [(1, 3)]),
    "B": ("Mining and quarrying", [(5, 9)]),
    "C": ("Manufacturing", [(10, 33)]),
    "D": ("Electricity, gas, steam and air conditioning", [(35, 35)]),
    "E": ("Water supply; sewerage and waste", [(36, 39)]),
    "F": ("Construction", [(41, 43)]),
    "G": ("Wholesale and retail trade", [(45, 47)]),
    "H": ("Transportation and storage", [(49, 53)]),
    "I": ("Accommodation and food service", [(55, 56)]),
    "J": ("Information and communication", [(58, 63)]),
    "K": ("Financial and insurance activities", [(64, 66)]),
    "L": ("Real estate activities", [(68, 68)]),
    "M": ("Professional, scientific and technical", [(69, 75)]),
    "N": ("Administrative and support services", [(77, 82)]),
    "O": ("Public administration and defence", [(84, 84)]),
    "P": ("Education", [(85, 85)]),
    "Q": ("Human health and social work", [(86, 88)]),
    "R": ("Arts, entertainment and recreation", [(90, 93)]),
    "S": ("Other service activities", [(94, 96)]),
    "T": ("Households as employers", [(97, 98)]),
    "U": ("Extraterritorial organisations", [(99, 99)]),
}

_DIV_TO_SECTION: dict[int, str] = {}
for letter, (_name, ranges) in SECTIONS.items():
    for lo, hi in ranges:
        for d in range(lo, hi + 1):
            _DIV_TO_SECTION[d] = letter


def division(sic_code: str) -> int | None:
    s = str(sic_code).strip()
    if not s or not s[:2].isdigit():
        return None
    return int(s[:2])


def section(sic_code: str) -> str | None:
    d = division(sic_code)
    return _DIV_TO_SECTION.get(d) if d is not None else None


def section_name(letter: str | None) -> str | None:
    if letter is None:
        return None
    entry = SECTIONS.get(letter)
    return entry[0] if entry else None
