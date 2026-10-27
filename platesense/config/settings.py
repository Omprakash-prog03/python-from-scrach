"""PlateSense central configuration.

All runtime paths, thresholds and tunables are defined here.
The configuration is loaded lazily and can be overridden via a user
JSON file located in the user data directory.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict

APP_NAME = "PlateSense"
APP_VERSION = "1.0.0"
APP_SUBTITLE = "Vehicle intelligence"

LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def _resource_root() -> Path:
    """Return the directory where bundled resources live.

    In normal source runs this is the ``platesense/`` package directory.
    In a PyInstaller one-file build it points to the extracted ``_MEIPASS``
    bundle so that bundled model files, icons etc. are discoverable.
    """
    if getattr(sys, "frozen", False):  # pragma: no cover - only in frozen app
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parent.parent


def _app_data_root() -> Path:
    """Return a per-user data directory (cross-platform)."""
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / APP_NAME


@dataclass
class Settings:
    """All user-configurable and runtime settings for PlateSense."""

    # Appearance
    theme: str = "light"  # "light" | "dark" | "system"

    # Detection
    model_path: str = ""         # path to YOLO .pt weights (optional)
    cascade_path: str = ""       # optional Haar cascade path
    confidence_threshold: float = 0.45
    nms_threshold: float = 0.45
    max_detections: int = 5
    use_classical_detector: bool = True
    use_cascade_detector: bool = True

    # OCR
    ocr_engine: str = "easyocr"  # "easyocr" | "pytesseract"
    ocr_language: str = "en"
    preprocessing_mode: str = "auto"  # "auto" | "minimal" | "aggressive"
    min_ocr_confidence: float = 0.4

    # Storage
    database_path: str = ""
    image_storage_path: str = ""
    history_retention_days: int = 365

    # Performance
    max_image_dim: int = 2400          # downscale very large inputs
    device: str = "cpu"                # "cpu" | "cuda"
    ocr_use_gpu: bool = False

    # Application
    first_run: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Settings":
        valid_keys = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in valid_keys})


class Config:
    """Singleton-like application configuration."""

    def __init__(self) -> None:
        self.app_dir = Path(__file__).resolve().parent.parent
        self.resource_dir = _resource_root()
        self.data_dir = _app_data_root()
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Default sub-directories inside the data directory
        self.db_dir = self.data_dir / "database"
        self.img_dir = self.data_dir / "images"
        self.export_dir = self.data_dir / "exports"
        self.log_dir = self.data_dir / "logs"
        for d in (self.db_dir, self.img_dir, self.export_dir, self.log_dir):
            d.mkdir(parents=True, exist_ok=True)

        # Models directory lives next to the application resources.
        # In a source checkout this is <repo>/platesense/models.
        # In a frozen app it is the bundled resources/models folder; the user
        # can still override this path in Settings.
        self.models_dir = self.resource_dir / "models"
        try:
            self.models_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            # When bundled read-only, fall back to a user-writable dir
            self.models_dir = self.data_dir / "models"
            self.models_dir.mkdir(parents=True, exist_ok=True)

        self.user_config_path = self.data_dir / "settings.json"

        # Default model path: first prefer a model next to user data (so users
        # can drop in their own without modifying the bundle), then the bundled
        # model.
        user_model = self.data_dir / "models" / "license_plate_detector.pt"
        bundled_model = self.resource_dir / "models" / "license_plate_detector.pt"
        default_model = str(user_model if user_model.exists() else bundled_model)

        self.settings = Settings(
            model_path=default_model,
            database_path=str(self.db_dir / "platesense.sqlite"),
            image_storage_path=str(self.img_dir),
        )
        self.load()

    # ----- persistence -----
    def load(self) -> None:
        if self.user_config_path.exists():
            try:
                data = json.loads(self.user_config_path.read_text(encoding="utf-8"))
                self.settings = Settings.from_dict(data)
                LOGGER.info("Loaded user settings from %s", self.user_config_path)
            except Exception as exc:  # pragma: no cover - defensive
                LOGGER.warning("Failed to read settings: %s", exc)

    def save(self) -> None:
        try:
            self.user_config_path.write_text(
                json.dumps(self.settings.to_dict(), indent=2), encoding="utf-8"
            )
            LOGGER.info("Saved settings to %s", self.user_config_path)
        except Exception as exc:  # pragma: no cover
            LOGGER.error("Could not save settings: %s", exc)

    def update(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            if hasattr(self.settings, key):
                setattr(self.settings, key, value)
        self.save()

    # ----- computed -----
    @property
    def supported_exts(self):
        return {".jpg", ".jpeg", ".png", ".webp", ".bmp"}

    @property
    def max_file_size(self) -> int:
        return 20 * 1024 * 1024  # 20 MB


config = Config()
