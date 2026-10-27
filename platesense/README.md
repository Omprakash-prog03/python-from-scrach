# PlateSense

> Local-first vehicle number-plate detection and recognition, designed for
> Indian number plates.

PlateSense is a professional desktop application built with Python, PySide6,
OpenCV and EasyOCR. It detects vehicle number plates from an uploaded photo,
localises and crops them, reads the plate text, validates it against Indian
state codes, estimates confidence, and maintains a searchable history — all
locally on your machine, no cloud required.

![PlatSense screenshot placeholder](assets/images/screenshot.png)

## Features

- **Apple-inspired interface** with light and dark mode, soft shadows, rounded
  cards, and subtle animations.
- **Drag-and-drop upload** with validation (JPG/JPEG/PNG/WEBP/BMP, ≤20 MB).
- **Real detection pipeline** — no fake results:
  - Optional YOLO detector (used automatically when weights are installed)
  - Classical edge+morphology+contour detector (always available, model-free)
  - OpenCV Haar-cascade plate detector as a secondary prior
- **Plate preprocessing** — upscale, bilateral de-noise, CLAHE contrast, Otsu
  and adaptive thresholding, sharpening, multiple variants scored and the
  best OCR result selected.
- **EasyOCR** text recognition with pytesseract as an optional fallback.
- **Indian plate validation** with state/UT codes, contextual OCR error
  correction (O/0, I/1, B/8, S/5, …), and normalisation to the canonical
  `XX 00 XX 0000` format.
- **Region detection** — displays the state name (Maharashtra, Odisha,
  Karnataka, Delhi, …) derived from the plate code.
- **Per-result confidence** — detection, OCR and overall scores.
- **Multiple-plate support** — if several plates are found you can pick one.
- **Zoomable annotated image viewer** with pan, zoom, fit-to-screen, reset.
- **SQLite history** with search, filtering, sorting, deletion.
- **Export** detections to CSV, JSON, TXT or save the annotated JPEG.
- **Background processing** on a dedicated `QThread` — the UI stays responsive.
- **Graceful error states** for corrupt files, missing plates, low confidence,
  missing OCR model, permission errors, database errors, etc.
- **Settings** for theme, thresholds, OCR engine, storage paths and performance.
- **Logging** to `~/.local/share/PlateSense/logs/platesense.log`.
- **Architecture ready for video/camera** expansion (see below).

## Requirements

- **Python 3.11, 3.12 or 3.13** (Python 3.14 is **not** yet supported by
  PySide6 / PyTorch / EasyOCR. If you have 3.14 installed, install Python
  3.12 side-by-side — the virtual env will pick it up automatically.)
- Linux, macOS or Windows (Windows/macOS ship system libGL normally; on
  Linux you need `libgl1-mesa-glx`, `libxkbcommon0`, `libdbus-1-3`,
  `libegl1` from your package manager — standard on desktop distros).

## Installation

> **Note for Windows users:** when you install Python from
> [python.org](https://www.python.org/downloads/windows/) tick the box
> labelled **"Add Python.exe to PATH"**. If you see a `PySide6==6.8.0.2`
> "no matching version" error, it almost always means you installed
> Python 3.14 — install Python 3.12 instead, delete the `.venv` folder
> and re-run the steps below.

```bash
git clone https://github.com/Omprakash-prog03/python-from-scrach.git
cd python-from-scrach/platesense

python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate

pip install --upgrade pip
pip install -r requirements.txt
```

The first launch will create a user data directory at:

- Linux:   `~/.local/share/PlateSense`
- macOS:   `~/Library/Application Support/PlateSense`
- Windows: `%APPDATA%\PlateSense`

The SQLite database and saved images live there automatically.

## Running

```bash
python app.py
```

Or use the helper script:

```bash
./scripts/run.sh     # Linux/macOS
scripts\run.bat      # Windows
```

### Command-line shortcuts

- `Ctrl/Cmd + O` — open an image
- `Esc` — reset the Detect page

## Packaging & deployment (desktop installable)

PlateSense can be packaged into a standalone, double-clickable desktop
application using PyInstaller — no Python install required on the target
machine.

### 1. Install build tools (once)

```bash
pip install -r requirements.txt
pip install pyinstaller
```

### 2. Build

```bash
# Linux / macOS
./scripts/build.sh            # produces dist/PlateSense/ (folder build)
./scripts/build.sh --onefile  # produces a single executable

# Windows (PowerShell / cmd)
scripts\build.bat
scripts\build.bat --onefile
```

The PyInstaller spec at `PlateSense.spec` bundles the `assets/` and `models/`
directories, hides a terminal window on Windows/macOS, and (on macOS)
produces a proper `.app` bundle with high-DPI and dark-mode enabled.

### 3. Output

| Platform | Output                                             |
|----------|----------------------------------------------------|
| Windows  | `dist\PlateSense\PlateSense.exe`                   |
| macOS    | `dist/PlateSense.app`                              |
| Linux    | `dist/PlateSense/PlateSense`                       |

The folder build (`dist/PlateSense/`) is recommended for distribution because
it starts faster; the `--onefile` variant unpacks itself to a temp directory
on every launch.

### 4. Distribute

- **Windows** — zip the `dist/PlateSense/` folder and share; optionally wrap
  in an installer (e.g. Inno Setup, NSIS).
- **macOS** — code-sign, notarize and distribute `PlateSense.app` (or dmg).
- **Linux** — create a `.deb` / `.AppImage` / flatpak around the `dist/PlateSense/`
  directory, or just ship the directory and add a `.desktop` launcher.

### 5. Shipping a YOLO model

Place `license_plate_detector.pt` inside `models/` *before* running the build
and it will be bundled into the application. Users can still override the
path from **Settings → Detection → Model path**, and any model copied into
the user-data `models/` directory takes priority over the bundled one.

### Runtime data locations

Packaged builds write their database, logs and saved images to the same
per-user data directory used in development:

- Windows: `%APPDATA%\PlateSense`
- macOS:   `~/Library/Application Support/PlateSense`
- Linux:   `~/.local/share/PlateSense`

Uninstalling the app does not delete that folder (use the Settings retention
controls to prune data).

## How the detection pipeline works

```
Input Image
    ↓
File/extension/size validation
    ↓
Image normalisation + max-dimension downscale
    ↓
Plate detection (YOLO → Cascade → Classical; NMS merge)
    ↓
Plate crop (with small padding)
    ↓
Multi-variant enhancement (gray / CLAHE / Otsu / adaptive / sharpen)
    ↓
OCR per variant (EasyOCR default)
    ↓
Text cleaning + Indian plate validation + contextual correction
    ↓
Confidence fusion (detection + OCR + validation)
    ↓
Annotation (green box + label)
    ↓
Optional persistence to SQLite + image storage
```

## Model requirements

### Out of the box

The classical detector needs no weights and works offline. It is fast but can
be fooled by complex backgrounds or oblique plates.

### Recommended: YOLO detector

For production-level accuracy, drop a YOLOv5/YOLOv8 `.pt` weights file at:

```
models/license_plate_detector.pt
```

and install ultralytics:

```bash
pip install ultralytics
```

If the weights are missing the app still runs and shows a friendly "model
not installed" state on the Models page.

### OCR

EasyOCR downloads its English detection/recognition models on first run.
If that machine does not have internet access, copy the model files from
another machine into `~/.EasyOCR/model/`. See `models/README.md`.

## Testing

```bash
pip install pytest
PYTHONPATH=. pytest tests -v
```

Tests cover the Indian-plate validator (including common OCR confusions),
database CRUD, image preprocessing and export.

## Project layout

```
platesense/
├── app.py                     # Application entry point
├── requirements.txt
├── config/                    # Settings + logging
├── ui/                        # PySide6 UI (main window, pages, widgets)
│   ├── widgets/               # Drop area, image viewer, stat card, toast
│   ├── dashboard.py
│   ├── detect_page.py
│   ├── history_page.py
│   ├── models_page.py
│   ├── settings_page.py
│   ├── help_page.py
│   └── main_window.py
├── vision/                    # Detection, preprocessing, annotation
│   ├── detector.py            # YOLO / Cascade / Classical detectors
│   ├── preprocessing.py
│   └── annotator.py
├── ocr/                       # OCR backends and validation
│   ├── engine.py              # EasyOCR + pytesseract adapters
│   ├── preprocessing.py       # Plate-image variants for OCR
│   └── validator.py           # Indian plate validation/state codes
├── database/                  # SQLite persistence
├── services/                  # Orchestration: detection, history, export
├── workers/                   # QThread workers (no UI freezing)
├── models/                    # Put YOLO weights here (see README)
├── assets/                    # Icons / images
├── tests/                     # pytest suite
└── data/                      # Project-local data (not used by default)
```

## Roadmap / Future improvements

PlateSense is structured to allow future video/camera support with minimal
refactoring. The detector operates on a single BGR frame today — a video
pipeline can add frame extraction, simple tracking (IoU-based), result
aggregation and video annotation on top. Planned navigation entries:

- Detect Image (current)
- Detect Video
- Live Camera

Other planned improvements:

- Batch processing (folder watch)
- Export to PDF report
- Per-plate manual correction
- Additional state-code edge cases (BH series, defence plates, etc.)
- Fine-tuned OCR vocab restricted to Indian-plate characters

## Troubleshooting

- **"libGL.so.1 not found" on Linux** – install `libgl1-mesa-glx` (Debian/Ubuntu)
  or `mesa-libGL` (Fedora). On macOS/Windows the standard PySide6 wheels
  include everything needed.
- **"EasyOCR model download failed"** – see `models/README.md` for how to
  pre-place the model files offline. The app will still locate plates and
  show crops, but text recognition will be disabled until OCR is available.
- **Low confidence / wrong plate** – try a clearer photo (straight-on, even
  lighting, no glare). Installing a YOLO detector dramatically improves
  localisation on busy backgrounds.
- **Logs** – inspect `~/.local/share/PlateSense/logs/platesense.log`.

## License

This project is provided as-is for educational and personal use. See
`LICENSE` for details (when added).

## Credits

Detection structure inspired in part by
[souravrs999/License-Plate-Recognition](https://github.com/souravrs999/License-Plate-Recognition),
with a complete rewrite focused on a native desktop UI, local history, Indian
plate validation and graceful fallbacks when no model is installed.
