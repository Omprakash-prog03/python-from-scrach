"""Application-wide logging setup."""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .settings import config


def setup_logging(level: int = logging.INFO) -> None:
    """Configure root logger with console and rotating file handlers."""
    log_dir: Path = config.log_dir
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "platesense.log"

    fmt = logging.Formatter(
        "%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(level)
    # Prevent duplicate handlers on reload
    if any(isinstance(h, RotatingFileHandler) for h in root.handlers):
        return

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    console.setLevel(level)

    file_handler = RotatingFileHandler(
        log_file, maxBytes=2_000_000, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    file_handler.setLevel(level)

    root.addHandler(console)
    root.addHandler(file_handler)

    # Lower the noise from third-party libraries
    logging.getLogger("PIL").setLevel(logging.WARNING)
    logging.getLogger("matplotlib").setLevel(logging.WARNING)
