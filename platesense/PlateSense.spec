# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for building a standalone PlateSense executable.

Usage (from inside platesense/ after installing dev dependencies):

    pyinstaller PlateSense.spec --clean --noconfirm

Produces a distributable app in ``dist/``:

* Windows -> ``dist/PlateSense/PlateSense.exe``
* macOS   -> ``dist/PlateSense.app``
* Linux   -> ``dist/PlateSense/PlateSense``
"""
from __future__ import annotations

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

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


# Static data files we ship inside the bundle.
datas = [
    (ASSETS, "assets"),
    (MODELS, "models"),
]

binaries = []
hiddenimports = []


def _collect_safe(pkg, include_submodules=True):
    """Collect data files (and optionally submodules) for a package if installed.

    We deliberately avoid collect_all() because it pulls binaries (e.g. CUDA
    libs for torch) which are enormous and not needed for a CPU-only build.
    """
    global datas, hiddenimports
    try:
        datas += collect_data_files(pkg)
    except Exception as exc:
        print(f"[spec] Note: collect_data_files({pkg}): {exc}")
    if include_submodules:
        try:
            hiddenimports += collect_submodules(pkg)
        except Exception as exc:
            print(f"[spec] Note: collect_submodules({pkg}): {exc}")


# EasyOCR pulls several packages that use dynamic imports and plugin patterns.
for _pkg in ("easyocr", "shapely", "skimage", "scipy", "cv2", "PIL"):
    _collect_safe(_pkg)

# Let PyInstaller's built-in hooks handle torch / torchvision / PySide6 / numpy
# (they are heavy and shipped with their own hook configs; adding collect_all
# tends to balloon the bundle with test binaries and CUDA libs).

# Exclude heavy/dev modules we never use (keeps binary smaller & avoids hook issues).
excludes = [
    "tkinter",
    "unittest",
    "pytest",
    "pytest_mock",
    "distutils",
    "numpy.f2py",
    "pytesseract",
    # PySide6 modules we don't use
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
    "PySide6.Qt3DCore", "PySide6.QtQuick3D", "PySide6.QtQml",
    "PySide6.QtBluetooth", "PySide6.QtMultimedia", "PySide6.QtNetwork",
    "PySide6.QtCharts", "PySide6.QtDataVisualization",
    # IPython/notebook/training junk that easyocr sometimes pulls in
    "IPython", "jupyter", "notebook", "matplotlib",
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
    upx=False,                # UPX corrupts PySide6 DLLs on Windows; keep off.
    console=False,
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
