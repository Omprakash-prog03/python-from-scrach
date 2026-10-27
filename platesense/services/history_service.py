"""HistoryService – thin wrapper over DatabaseManager plus convenience
methods used by the UI (recent items, stats, etc.)."""
from __future__ import annotations

import logging
from typing import List, Optional

from database.database import DatabaseManager, DetectionRecord
from config.settings import config

LOGGER = logging.getLogger(__name__)


class HistoryService:
    def __init__(self, db: Optional[DatabaseManager] = None):
        self.db = db or DatabaseManager(config.settings.database_path)

    def add(self, record: DetectionRecord) -> int:
        return self.db.insert_detection(record)

    def recent(self, limit: int = 5) -> List[DetectionRecord]:
        return self.db.list_detections(limit=limit, order_by="created_at",
                                       descending=True)

    def search(self, query: str = "", state_code: Optional[str] = None,
               min_confidence: Optional[float] = None,
               order_by: str = "created_at", descending: bool = True,
               limit: int = 500) -> List[DetectionRecord]:
        return self.db.list_detections(
            search=query or None,
            state_code=state_code,
            min_confidence=min_confidence,
            order_by=order_by,
            descending=descending,
            limit=limit,
        )

    def get(self, detection_id: int) -> Optional[DetectionRecord]:
        return self.db.get_detection(detection_id)

    def delete(self, detection_id: int) -> None:
        self.db.delete_detection(detection_id)

    def stats(self) -> dict:
        return self.db.stats()
