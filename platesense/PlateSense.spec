# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for building a standalone PlateSense executable.

Usage (from inside platesense/ after installing dev dependencies):

    pyinstaller PlateSense.spec --clean --noconfirm

Produces a distributable app in ``dist/``:

* Windows -> ``dist/PlateSense/PlateSense.exe``  (or ``--onefile`` for a single exe)
* macOS   -> ``dist/PlateSense.app``
* Linux   -> ``dist/PlateSense/PlateSense``
"""

import sys
from pathlib import Path

block_cipher = None

ROOT = Path(SPECPATH).resolve()
ASSETS = str(ROOT / "assets")
MODELS = str(ROOT / "models")

# Include all data files that must ship inside the bundle.
datas = [
    (ASSETS, "assets"),
    (MODELS, "models"),
]

# Packages that PyInstaller sometimes misses in automatic detection.
hiddenimports = [
    "easyocr",
    "easyocr.model",
    "easyocr.model.model",
    "easyocr.detection",
    "easyocr.recognition",
    "easyocr.utils",
    "shapely",
    "shapely.geometry",
    "skimage",
    "cv2",
    "PIL",
    "numpy",
]

# Some packages (torch/nvidia) pull in CUDA shared libs that are huge and not
# required for CPU-only inference. On CPU-only builds these binaries can be
# excluded to keep the distributable smaller.
excludes = [
    "tkinter",
    "unittest",
    "pytest",
    "distutils",
]

a = Analysis(
    [str(ROOT / "app.py")],
    pathex=[str(ROOT)],
    binaries=[],
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

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PlateSense",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,             # No terminal window on Windows/macOS
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / "assets/icons/app_icon.icns") if sys.platform == "darwin" else
         str(ROOT / "assets/icons/app_icon.ico") if sys.platform.startswith("win") else
         None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="PlateSense",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="PlateSense.app",
        icon=str(ROOT / "assets/icons/app_icon.icns") if (ROOT / "assets/icons/app_icon.icns").exists() else None,
        bundle_identifier="ai.platesense.desktop",
        info_plist={
            "CFBundleName": "PlateSense",
            "CFBundleDisplayName": "PlateSense",
            "CFBundleVersion": "1.0.0",
            "CFBundleShortVersionString": "1.0.0",
            "NSHighResolutionCapable": "True",
            "NSSupportsAutomaticGraphicsSwitching": "True",
            "NSRequiresAquaSystemAppearance": False,  # allow dark mode
            "CFBundleDocumentTypes": [{
                "CFBundleTypeName": "Image",
                "CFBundleTypeRole": "Viewer",
                "LSItemContentTypes": ["public.image"],
            }],
        },
    )
