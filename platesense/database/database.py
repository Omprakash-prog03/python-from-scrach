"""SQLite persistence for PlateSense.

The database is created automatically inside the user data directory.
All queries are parameterized and access is wrapped so the UI layer never
talks to SQLite directly.
"""
from __future__ import annotations

import logging
import os
import shutil
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone


def _utcnow() -> datetime:
    """Timezone-aware UTC now (works on Python 3.11–3.13)."""
    return datetime.now(timezone.utc)
from pathlib import Path
from typing import Any, Dict, List, Optional

LOGGER = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS detections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plate_number TEXT NOT NULL,
    normalized_plate TEXT NOT NULL,
    state TEXT,
    state_code TEXT,
    detection_confidence REAL,
    ocr_confidence REAL,
    overall_confidence REAL,
    image_path TEXT,
    plate_crop_path TEXT,
    annotated_path TEXT,
    processing_time REAL,
    vehicle_type TEXT,
    notes TEXT,
    valid INTEGER DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_detections_plate ON detections(normalized_plate);
CREATE INDEX IF NOT EXISTS idx_detections_created ON detections(created_at);
CREATE INDEX IF NOT EXISTS idx_detections_state ON detections(state_code);
"""


@dataclass
class DetectionRecord:
    id: Optional[int]
    plate_number: str
    normalized_plate: str
    state: Optional[str]
    state_code: Optional[str]
    detection_confidence: float
    ocr_confidence: float
    overall_confidence: float
    image_path: Optional[str]
    plate_crop_path: Optional[str]
    annotated_path: Optional[str]
    processing_time: float
    vehicle_type: Optional[str]
    notes: Optional[str]
    valid: bool
    created_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DatabaseManager:
    """Thin data-access layer around SQLite."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA)
        LOGGER.info("Database initialised at %s", self.db_path)

    # ------------- writes -------------
    def insert_detection(self, record: DetectionRecord) -> int:
        created_at = record.created_at or _utcnow().isoformat(timespec="seconds")
        with self._connect() as conn:
            cur = conn.execute(
                """INSERT INTO detections
                   (plate_number, normalized_plate, state, state_code,
                    detection_confidence, ocr_confidence, overall_confidence,
                    image_path, plate_crop_path, annotated_path,
                    processing_time, vehicle_type, notes, valid, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    record.plate_number, record.normalized_plate, record.state,
                    record.state_code, record.detection_confidence,
                    record.ocr_confidence, record.overall_confidence,
                    record.image_path, record.plate_crop_path, record.annotated_path,
                    record.processing_time, record.vehicle_type, record.notes,
                    1 if record.valid else 0, created_at,
                ),
            )
            rid = cur.lastrowid
        LOGGER.info("Inserted detection id=%s plate=%s", rid, record.normalized_plate)
        return rid

    def delete_detection(self, detection_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM detections WHERE id = ?", (detection_id,))

    def update_notes(self, detection_id: int, notes: str) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE detections SET notes = ? WHERE id = ?",
                         (notes, detection_id))

    def apply_retention(self, days: int) -> int:
        cutoff = (_utcnow() - timedelta(days=days)).isoformat(timespec="seconds")
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM detections WHERE created_at < ?", (cutoff,))
            return cur.rowcount

    # ------------- reads -------------
    def get_detection(self, detection_id: int) -> Optional[DetectionRecord]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM detections WHERE id = ?", (detection_id,)
            ).fetchone()
        return _row_to_record(row) if row else None

    def list_detections(
        self,
        search: Optional[str] = None,
        state_code: Optional[str] = None,
        min_confidence: Optional[float] = None,
        order_by: str = "created_at",
        descending: bool = True,
        limit: int = 500,
        offset: int = 0,
    ) -> List[DetectionRecord]:
        allowed_order = {"created_at", "overall_confidence", "normalized_plate",
                         "processing_time"}
        order_col = order_by if order_by in allowed_order else "created_at"
        direction = "DESC" if descending else "ASC"

        clauses: List[str] = []
        params: List[Any] = []
        if search:
            clauses.append("(normalized_plate LIKE ? OR plate_number LIKE ? OR notes LIKE ?)")
            like = f"%{search}%"
            params.extend([like, like, like])
        if state_code:
            clauses.append("state_code = ?")
            params.append(state_code)
        if min_confidence is not None:
            clauses.append("overall_confidence >= ?")
            params.append(min_confidence)

        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = f"SELECT * FROM detections {where} ORDER BY {order_col} {direction} LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [_row_to_record(r) for r in rows]

    def count(self) -> int:
        with self._connect() as conn:
            r = conn.execute("SELECT COUNT(*) AS c FROM detections").fetchone()
            return int(r["c"]) if r else 0

    def stats(self) -> Dict[str, float]:
        with self._connect() as conn:
            week_ago = (_utcnow() - timedelta(days=7)).isoformat(timespec="seconds")
            total = conn.execute("SELECT COUNT(*) c FROM detections").fetchone()["c"]
            week = conn.execute("SELECT COUNT(*) c FROM detections WHERE created_at >= ?",
                                (week_ago,)).fetchone()["c"]
            avg_conf = conn.execute("SELECT AVG(overall_confidence) a FROM detections").fetchone()["a"] or 0.0
            avg_time = conn.execute("SELECT AVG(processing_time) a FROM detections").fetchone()["a"] or 0.0
        return {
            "total": int(total),
            "week": int(week),
            "avg_confidence": float(avg_conf),
            "avg_processing_time": float(avg_time),
        }


def _row_to_record(row: sqlite3.Row) -> DetectionRecord:
    return DetectionRecord(
        id=row["id"],
        plate_number=row["plate_number"],
        normalized_plate=row["normalized_plate"],
        state=row["state"],
        state_code=row["state_code"],
        detection_confidence=row["detection_confidence"],
        ocr_confidence=row["ocr_confidence"],
        overall_confidence=row["overall_confidence"],
        image_path=row["image_path"],
        plate_crop_path=row["plate_crop_path"],
        annotated_path=row["annotated_path"],
        processing_time=row["processing_time"],
        vehicle_type=row["vehicle_type"],
        notes=row["notes"],
        valid=bool(row["valid"]),
        created_at=row["created_at"],
    )
