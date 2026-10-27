"""Tests for Indian plate validation."""
from ocr.validator import normalize_plate_text, validate_plate


def test_clean_plate_basic():
    r = validate_plate("MH12AB4821")
    assert r.valid is True
    assert r.normalized_text == "MH 12 AB 4821"
    assert r.region == "Maharashtra"
    assert r.state_code == "MH"
    assert r.confidence > 0.7


def test_od_plate():
    r = validate_plate("OD 02 CJ 7734")
    assert r.valid
    assert r.state_code == "OD"
    assert r.region == "Odisha"


def test_ka_plate_separators():
    r = validate_plate("KA-01-MN-6190")
    assert r.valid
    assert r.normalized_text == "KA 01 MN 6190"


def test_dl_plate():
    r = validate_plate("DL05CA1234")
    assert r.valid
    assert r.normalized_text == "DL 05 CA 1234"
    assert r.region == "Delhi"


def test_invalid_plate():
    r = validate_plate("INVALID123")
    assert not r.valid
    assert r.confidence < 0.5


def test_empty():
    r = validate_plate("")
    assert not r.valid
    assert r.normalized_text == ""


def test_ocr_confusion_zero():
    # "O" should not always be converted, but in numeric context like
    # a district "O2" -> "02", and in trailing number "482O" -> "4820"
    r = validate_plate("MH O2 AB 482O")
    assert r.valid
    assert r.normalized_text == "MH 02 AB 4820"


def test_state_table_completeness():
    from ocr.validator import STATE_CODES
    # Spot-check well known states
    for code in ["MH", "OD", "KA", "DL", "TN", "GJ", "UP", "WB", "RJ"]:
        assert code in STATE_CODES


def test_normalize_helper():
    assert normalize_plate_text("tn-22-az-9999").startswith("TN 22 AZ")
