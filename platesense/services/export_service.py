"""Export detections to CSV / JSON / TXT and annotated images."""
from __future__ import annotations

import csv
import json
import logging
import os
import shutil
from pathlib import Path
from typing import Iterable, List

from database.database import DetectionRecord

LOGGER = logging.getLogger(__name__)

FIELDS = ["id", "plate_number", "normalized_plate", "state", "state_code",
          "detection_confidence", "ocr_confidence", "overall_confidence",
          "processing_time", "vehicle_type", "notes", "valid", "created_at"]


def _ensure_dir(path: str) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def export_csv(records: Iterable[DetectionRecord], out_path: str) -> str:
    _ensure_dir(os.path.dirname(out_path) or ".")
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for r in records:
            writer.writerow({k: r.to_dict().get(k) for k in FIELDS})
    LOGGER.info("Exported CSV to %s", out_path)
    return out_path


def export_json(records: Iterable[DetectionRecord], out_path: str) -> str:
    _ensure_dir(os.path.dirname(out_path) or ".")
    data = [{k: r.to_dict().get(k) for k in FIELDS} for r in records]
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    LOGGER.info("Exported JSON to %s", out_path)
    return out_path


def export_txt(records: Iterable[DetectionRecord], out_path: str) -> str:
    _ensure_dir(os.path.dirname(out_path) or ".")
    lines: List[str] = []
    for r in records:
        lines.append(
            f"{r.normalized_plate:<16} {r.state or '-':<28} "
            f"conf={r.overall_confidence * 100:5.1f}%  "
            f"time={r.processing_time:.2f}s  "
            f"date={r.created_at}"
        )
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    LOGGER.info("Exported TXT to %s", out_path)
    return out_path


def export_annotated_image(record: DetectionRecord, out_path: str) -> str:
    """Copy the annotated image to an export location."""
    if not record.annotated_path or not os.path.exists(record.annotated_path):
        raise FileNotFoundError("Annotated image not found for this detection.")
    _ensure_dir(os.path.dirname(out_path) or ".")
    shutil.copy2(record.annotated_path, out_path)
    return out_path


def export_record(record: DetectionRecord, fmt: str, out_dir: str) -> str:
    """Export a single record in the requested format."""
    out_dir_p = _ensure_dir(out_dir)
    safe_plate = record.normalized_plate.replace(" ", "_")
    fmt = fmt.lower()
    if fmt == "csv":
        return export_csv([record], str(out_dir_p / f"{safe_plate}.csv"))
    if fmt == "json":
        return export_json([record], str(out_dir_p / f"{safe_plate}.json"))
    if fmt == "txt":
        return export_txt([record], str(out_dir_p / f"{safe_plate}.txt"))
    if fmt in ("jpg", "jpeg", "png", "image"):
        ext = "jpg" if fmt in ("jpg", "jpeg", "image") else "png"
        return export_annotated_image(record, str(out_dir_p / f"{safe_plate}_annotated.{ext}"))
    raise ValueError(f"Unsupported export format: {fmt}")
