"""Tests for export service."""
import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from database.database import DetectionRecord
from services import export_service


def _rec():
    return DetectionRecord(
        id=1, plate_number="MH12AB4821", normalized_plate="MH 12 AB 4821",
        state="Maharashtra", state_code="MH",
        detection_confidence=0.99, ocr_confidence=0.96, overall_confidence=0.98,
        image_path=None, plate_crop_path=None, annotated_path=None,
        processing_time=0.4, vehicle_type="Car", notes=None, valid=True,
        created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


def test_export_csv(tmp_path):
    out = str(tmp_path / "out.csv")
    export_service.export_csv([_rec()], out)
    assert os.path.exists(out)
    with open(out, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["normalized_plate"] == "MH 12 AB 4821"


def test_export_json(tmp_path):
    out = str(tmp_path / "out.json")
    export_service.export_json([_rec()], out)
    data = json.loads(Path(out).read_text())
    assert data[0]["state"] == "Maharashtra"


def test_export_txt(tmp_path):
    out = str(tmp_path / "out.txt")
    export_service.export_txt([_rec()], out)
    text = Path(out).read_text()
    assert "MH 12 AB 4821" in text
    assert "Maharashtra" in text
