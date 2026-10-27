# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for building a standalone PlateSense executable.

Usage (from inside platesense/ after installing dev dependencies):

    pyinstaller PlateSense.spec --clean --noconfirm

Produces a distributable app in ``dist/``:

* Windows -> ``dist/PlateSense/PlateSense.exe``  (or ``--onefile`` for a single exe)
* macOS   -> ``dist/PlateSense.app``
* Linux   -> ``dist/PlateSense/PlateSense``
"""

from __future__ import annotations

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None

ROOT = Path(SPECPATH).resolve()
ASSETS = str(ROOT / "assets")
MODELS = str(ROOT / "models")


def _pick_icon():
    """Return a platform-appropriate icon if one exists, else None."""
    candidates = []
    if sys.platform == "darwin":
        candidates = [ROOT / "assets/icons/app_icon.icns"]
    elif sys.platform.startswith("win"):
        candidates = [ROOT / "assets/icons/app_icon.ico"]
    else:
        candidates = [ROOT / "assets/icons/app_icon.png",
                      ROOT / "assets/icons/app_icon.ico"]
    for c in candidates:
        if c.exists():
            return str(c)
    return None


# Include all data files that must ship inside the bundle.
datas = [
    (ASSETS, "assets"),
    (MODELS, "models"),
]

binaries = []
hiddenimports = []


def _collect(pkg_name):
    """Safely collect a package's data, binaries and submodules (skip if missing)."""
    global datas, binaries, hiddenimports
    try:
        d, b, h = collect_all(pkg_name)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception as exc:
        print(f"[spec] Note: could not collect {pkg_name}: {exc}")


# Collect dynamic-import-heavy packages in full so PyInstaller sees them.
for pkg in ("easyocr", "shapely", "skimage", "scipy", "cv2", "PIL", "numpy"):
    _collect(pkg)

# Optional: torch/torchvision only if installed (pulled in transitively by easyocr).
for pkg in ("torch", "torchvision", "pyclipper"):
    try:
        hiddenimports += collect_submodules(pkg)
    except Exception:
        pass

# Exclude heavy/dev modules we never use to keep the binary small.
excludes = [
    "tkinter",
    "unittest",
    "pytest",
    "pytest_mock",
    "distutils",
    "numpy.f2py",
    # Optional OCR engine — avoid bundling tesseract by default.
    "pytesseract",
]

a = Analysis(
    [str(ROOT / "app.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

icon_path = _pick_icon()

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PlateSense",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                # UPX can corrupt PySide6 DLLs on Windows
    console=False,            # No terminal window on Windows/macOS
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="PlateSense",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="PlateSense.app",
        icon=icon_path,
        bundle_identifier="ai.platesense.desktop",
        info_plist={
            "CFBundleName": "PlateSense",
            "CFBundleDisplayName": "PlateSense",
            "CFBundleVersion": "1.0.0",
            "CFBundleShortVersionString": "1.0.0",
            "NSHighResolutionCapable": "True",
            "NSSupportsAutomaticGraphicsSwitching": "True",
            "NSRequiresAquaSystemAppearance": False,
            "CFBundleDocumentTypes": [{
                "CFBundleTypeName": "Image",
                "CFBundleTypeRole": "Viewer",
                "LSItemContentTypes": ["public.image"],
            }],
        },
    )
