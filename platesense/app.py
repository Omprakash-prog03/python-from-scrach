#!/usr/bin/env python3
"""PlateSense entry point."""
from __future__ import annotations

import ctypes
import logging
import os
import sys
from pathlib import Path


def _ensure_on_path() -> None:
    # Allow running from a cloned checkout: put the app directory on sys.path
    here = Path(__file__).resolve().parent
    if str(here) not in sys.path:
        sys.path.insert(0, str(here))


def _preload_runtime_stubs() -> None:
    """On minimal systems missing libGL/EGL (e.g. stripped containers) inject
    the bundled .stubs directory into LD_LIBRARY_PATH and relaunch so that
    the dynamic linker finds our shim libraries.

    On normal desktop systems (macOS, Windows, regular Linux distros with
    Mesa installed) this is a no-op."""
    here = Path(__file__).resolve().parent
    stub_dir = here / ".stubs"

    # If the libraries can already be loaded, nothing to do.
    needed = ("libGL.so.1", "libEGL.so.1", "libxkbcommon.so.0")
    missing = False
    for lib in needed:
        try:
            ctypes.CDLL(lib)
        except OSError:
            missing = True
            break
    if not missing:
        return
    if not stub_dir.exists():
        return
    if os.environ.get("PLATESENSE_RUNTIME_SET") == "1":
        # Already relaunched, give up
        return
    existing = os.environ.get("LD_LIBRARY_PATH", "")
    paths = [p for p in existing.split(os.pathsep) if p]
    if str(stub_dir) not in paths:
        paths.insert(0, str(stub_dir))
    os.environ["LD_LIBRARY_PATH"] = os.pathsep.join(paths)
    os.environ["PLATESENSE_RUNTIME_SET"] = "1"
    # Re-exec with updated environment
    os.execv(sys.executable, [sys.executable, sys.argv[0] if sys.argv else __file__, *sys.argv[1:]])


def main() -> int:
    _preload_runtime_stubs()
    _ensure_on_path()
    from config.logging_config import setup_logging
    setup_logging(logging.INFO)
    LOGGER = logging.getLogger("platesense")
    LOGGER.info("Starting PlateSense…")

    # First-run housekeeping
    from config.settings import config
    for d in (config.data_dir, config.db_dir, config.img_dir,
              config.export_dir, config.log_dir, config.models_dir):
        Path(d).mkdir(parents=True, exist_ok=True)

    # Apply retention
    try:
        from database.database import DatabaseManager
        db = DatabaseManager(config.settings.database_path)
        if config.settings.history_retention_days > 0:
            removed = db.apply_retention(config.settings.history_retention_days)
            if removed:
                LOGGER.info("Retention removed %d old record(s).", removed)
    except Exception as exc:
        LOGGER.warning("DB init failed: %s", exc)

    from ui.main_window import run
    return run()


if __name__ == "__main__":
    sys.exit(main())
