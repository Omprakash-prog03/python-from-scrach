"""Tests for the database layer."""
import os
import tempfile
from datetime import datetime, timezone

import pytest

from database.database import DatabaseManager, DetectionRecord


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "test.sqlite"
    return DatabaseManager(str(path))


def _record(**kw):
    defaults = dict(
        id=None, plate_number="MH 12 AB 4821", normalized_plate="MH 12 AB 4821",
        state="Maharashtra", state_code="MH",
        detection_confidence=0.98, ocr_confidence=0.95, overall_confidence=0.97,
        image_path=None, plate_crop_path=None, annotated_path=None,
        processing_time=0.42, vehicle_type="Car", notes=None, valid=True,
        created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    defaults.update(kw)
    return DetectionRecord(**defaults)


def test_insert_and_retrieve(db):
    rid = db.insert_detection(_record())
    assert rid > 0
    got = db.get_detection(rid)
    assert got is not None
    assert got.normalized_plate == "MH 12 AB 4821"
    assert got.state == "Maharashtra"


def test_search(db):
    db.insert_detection(_record(normalized_plate="MH 12 AB 4821", state_code="MH"))
    db.insert_detection(_record(normalized_plate="OD 02 CJ 7734", state_code="OD"))
    db.insert_detection(_record(normalized_plate="KA 01 MN 6190", state_code="KA"))

    all_recs = db.list_detections()
    assert len(all_recs) == 3

    mh = db.list_detections(state_code="MH")
    assert len(mh) == 1
    assert mh[0].normalized_plate == "MH 12 AB 4821"

    q = db.list_detections(search="CJ")
    assert len(q) == 1
    assert q[0].state_code == "OD"


def test_stats(db):
    db.insert_detection(_record(overall_confidence=0.9, processing_time=0.4))
    db.insert_detection(_record(overall_confidence=0.8, processing_time=0.6))
    s = db.stats()
    assert s["total"] == 2
    assert 0.7 < s["avg_confidence"] < 0.9
    assert s["avg_processing_time"] > 0


def test_delete(db):
    rid = db.insert_detection(_record())
    assert db.get_detection(rid) is not None
    db.delete_detection(rid)
    assert db.get_detection(rid) is None


def test_count(db):
    assert db.count() == 0
    db.insert_detection(_record())
    assert db.count() == 1
