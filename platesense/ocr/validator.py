"""Indian number-plate validation and normalization.

Indian plates generally follow the pattern::

    <STATE_CODE><DISTRICT><SERIES><NUMBER>
    e.g. MH 12 AB 4821

This module cleans OCR output, applies contextual corrections for common
OCR confusions (O/0, I/1, B/8, S/5…), validates against the state-code table
and returns region information along with a heuristic 0..1 confidence.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

# ---------------------------------------------------------------------------
# State / UT codes (source: Ministry of Road Transport, Govt. of India)
# ---------------------------------------------------------------------------
STATE_CODES = {
    "AN": "Andaman and Nicobar Islands",
    "AP": "Andhra Pradesh",
    "AR": "Arunachal Pradesh",
    "AS": "Assam",
    "BR": "Bihar",
    "CH": "Chandigarh",
    "CG": "Chhattisgarh",
    "DD": "Dadra and Nagar Haveli and Daman and Diu",
    "DL": "Delhi",
    "DN": "Dadra and Nagar Haveli",
    "GA": "Goa",
    "GJ": "Gujarat",
    "HR": "Haryana",
    "HP": "Himachal Pradesh",
    "JH": "Jharkhand",
    "JK": "Jammu and Kashmir",
    "KA": "Karnataka",
    "KL": "Kerala",
    "LA": "Ladakh",
    "LD": "Lakshadweep",
    "MH": "Maharashtra",
    "ML": "Meghalaya",
    "MN": "Manipur",
    "MP": "Madhya Pradesh",
    "MZ": "Mizoram",
    "NL": "Nagaland",
    "OD": "Odisha",
    "OR": "Odisha (Orissa)",
    "PB": "Punjab",
    "PY": "Puducherry",
    "RJ": "Rajasthan",
    "SK": "Sikkim",
    "TN": "Tamil Nadu",
    "TS": "Telangana",
    "TR": "Tripura",
    "UK": "Uttarakhand",
    "UP": "Uttar Pradesh",
    "WB": "West Bengal",
}

ALPHA_TO_DIGIT = {"O": "0", "Q": "0", "I": "1", "L": "1", "T": "1",
                  "Z": "2", "S": "5", "B": "8"}
DIGIT_TO_ALPHA = {"0": "O", "1": "I", "8": "B", "5": "S", "2": "Z", "6": "G"}

PLATE_REGEX = re.compile(
    r"^([A-Z]{2})-?(\d{1,2})-?([A-Z]{1,3})-?(\d{1,4})$"
)


@dataclass
class PlateValidationResult:
    valid: bool
    raw_text: str
    normalized_text: str
    region: Optional[str]
    state_code: Optional[str]
    confidence: float
    issues: List[str]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _basic_clean(text: str) -> str:
    if text is None:
        return ""
    t = text.strip().upper()
    t = re.sub(r"[\-\_\.\|\:\;\,\*\#\@\!\?\(\)\[\]\{\}/\\\"]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _force_alpha(ch: str) -> str:
    return DIGIT_TO_ALPHA.get(ch, ch) if not ch.isalpha() else ch


def _force_digit(ch: str) -> str:
    return ALPHA_TO_DIGIT.get(ch, ch) if not ch.isdigit() else ch


def _try_parse(compact: str) -> Optional[Tuple[str, str, str, str]]:
    """Attempt to parse *compact* (no spaces) into (state, district, series, number).

    Works from both ends: first 2 chars -> state; last 4 chars -> number;
    2 digits before series -> district; letters in between -> series.
    Returns None if it can't be coerced.
    """
    if len(compact) < 7 or len(compact) > 12:
        return None

    # state (first 2)
    state = "".join(_force_alpha(c) for c in compact[:2])
    if not state.isalpha():
        return None

    # number (last 4)
    number = "".join(_force_digit(c) for c in compact[-4:])
    if not number.isdigit():
        return None

    middle = compact[2:-4]
    if len(middle) < 2:
        return None

    # district: up to 2 leading digits (OCR-confused letters coerced to digits).
    district_chars: List[str] = []
    i = 0
    while i < len(middle) and len(district_chars) < 2:
        ch = middle[i]
        if ch.isdigit():
            district_chars.append(ch)
            i += 1
        elif ch in ALPHA_TO_DIGIT and (district_chars or i == 0):
            # allow a confused letter as a digit only at the start of district
            district_chars.append(ALPHA_TO_DIGIT[ch])
            i += 1
        else:
            break

    if len(district_chars) == 0:
        return None

    # series: the rest of the middle must be letters (OCR-confused digits coerced).
    series_part = middle[i:]
    if len(series_part) < 1 or len(series_part) > 3:
        # try shifting one digit from district to series, e.g. "DL05CA1234" middle="05CA"
        # gave district="05", series="CA" -> len 2 OK. Good.
        # But if series_part is empty or >3, maybe district captured too much/little.
        if len(district_chars) == 2 and len(series_part) == 0:
            # e.g. MH12AB1234 middle="12AB" → district took 12 but series empty because length=4 - 0
            pass
        # else fallthrough and let regex decide
    series = "".join(_force_alpha(c) for c in series_part)
    if not series.isalpha():
        return None
    if not (1 <= len(series) <= 3):
        return None

    return state, "".join(district_chars), series, number


def _contextual_fix(cleaned: str) -> Tuple[str, List[str]]:
    issues: List[str] = []
    compact = re.sub(r"\s+", "", cleaned)
    if not compact:
        return "", ["empty"]

    parsed = _try_parse(compact)
    if not parsed:
        issues.append("parse_failed")
        return cleaned.upper(), issues

    state, district, series, number = parsed
    state_issue = False
    if state not in STATE_CODES:
        # Try a few common state-code OCR confusions
        candidates = []
        for code in STATE_CODES:
            if code[0] == state[0] and (code[1] == state[1] or
                                        _force_alpha(state[1]) == code[1]):
                candidates.append(code)
        if len(candidates) == 1:
            state = candidates[0]
        else:
            state_issue = True

    normalized = f"{state} {district.zfill(2)} {series} {number.zfill(4)}"
    if state_issue:
        issues.append("unknown_state_code")
    return normalized, issues


def validate_plate(text: str) -> PlateValidationResult:
    raw = text or ""
    cleaned = _basic_clean(raw)
    issues: List[str] = []

    if not cleaned:
        return PlateValidationResult(
            valid=False, raw_text=raw, normalized_text="", region=None,
            state_code=None, confidence=0.0, issues=["empty"],
        )

    normalized, fix_issues = _contextual_fix(cleaned)
    issues.extend(fix_issues)

    m = PLATE_REGEX.match(re.sub(r"\s+", "", normalized))
    state_code: Optional[str] = None
    region: Optional[str] = None
    confidence = 0.0
    valid = False

    if m:
        state_c, dist, series, num = m.groups()
        state_code = state_c
        region = STATE_CODES.get(state_c)
        normalized = f"{state_c} {dist.zfill(2)} {series} {num.zfill(4)}"
        valid = region is not None and 1 <= len(series) <= 3 and len(num) <= 4
        # Confidence heuristic
        score = 0.5
        if region is not None:
            score += 0.3
        if len(dist) == 2:
            score += 0.05
        if 1 <= len(series) <= 3 and series.isalpha():
            score += 0.05
        if len(num) == 4 and num.isdigit():
            score += 0.1
        if cleaned.replace(" ", "") == normalized.replace(" ", ""):
            score += 0.05
        confidence = round(min(score, 0.99), 3)
    else:
        issues.append("format_mismatch")
        # Best-effort: pull out state code if we can
        prefix = re.sub(r"\s+", "", normalized)[:2]
        if prefix.isalpha() and prefix in STATE_CODES:
            state_code = prefix
            region = STATE_CODES[prefix]
            confidence = 0.25
            issues.append("partial_match")

    return PlateValidationResult(
        valid=valid, raw_text=raw, normalized_text=normalized,
        region=region, state_code=state_code,
        confidence=confidence, issues=issues,
    )


def normalize_plate_text(text: str) -> str:
    return validate_plate(text).normalized_text
