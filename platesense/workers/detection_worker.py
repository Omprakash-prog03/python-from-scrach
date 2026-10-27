"""QThread-based worker for running detection without freezing the UI."""
from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from services.detection_service import DetectionResult, DetectionService


class DetectionWorker(QThread):
    stage_changed = Signal(str, float)   # (stage_name, progress 0..1)
    finished_success = Signal(object)    # DetectionResult
    failed = Signal(str, str)            # (message, error_code)

    def __init__(self, service: DetectionService, image_path: str, parent=None):
        super().__init__(parent)
        self.service = service
        self.image_path = image_path
        self._abort = False

    def abort(self) -> None:
        self._abort = True

    def run(self) -> None:  # noqa: D401 - Qt override
        try:
            def cb(stage: str, progress: float):
                if self._abort:
                    raise RuntimeError("aborted")
                self.stage_changed.emit(stage, progress)

            result: DetectionResult = self.service.detect_from_path(
                self.image_path, on_stage=cb,
            )
            if result.success:
                self.finished_success.emit(result)
            else:
                self.failed.emit(result.message, result.error_code or "error")
        except Exception as exc:  # pragma: no cover
            self.failed.emit(f"Unexpected error: {exc}", "unexpected")
