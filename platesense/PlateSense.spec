# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for building a standalone PlateSense executable.

Usage (from inside platesense/ after installing dev dependencies):
    pyinstaller PlateSense.spec --clean --noconfirm
"""
from __future__ import annotations

import sys
from pathlib import Path

block_cipher = None

ROOT = Path(SPECPATH).resolve()
ASSETS = str(ROOT / "assets")
MODELS = str(ROOT / "models")


def _pick_icon():
    if sys.platform == "darwin":
        cand = ROOT / "assets/icons/app_icon.icns"
    elif sys.platform.startswith("win"):
        cand = ROOT / "assets/icons/app_icon.ico"
    else:
        cand = ROOT / "assets/icons/app_icon.png"
    return str(cand) if cand.exists() else None


# Data files shipped inside the bundle.
datas = [(ASSETS, "assets"), (MODELS, "models")]

# Exclude modules we never use (keeps binary smaller and avoids hook issues).
excludes = [
    "tkinter", "unittest", "pytest", "pytest_mock", "distutils",
    "pytesseract",
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebEngineQuick", "PySide6.Qt3DCore", "PySide6.QtQuick3D",
    "PySide6.QtQml", "PySide6.QtBluetooth", "PySide6.QtMultimedia",
    "PySide6.QtNetwork", "PySide6.QtCharts", "PySide6.QtDataVisualization",
    "IPython", "jupyter", "notebook", "matplotlib",
]

a = Analysis(
    [str(ROOT / "app.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=[],
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
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path,
)

coll = COLLECT(
    exe, a.binaries, a.zipfiles, a.datas,
    strip=False, upx=False, upx_exclude=[], name="PlateSense",
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
        },
    )
