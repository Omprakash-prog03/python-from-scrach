#!/usr/bin/env bash
# Build a standalone PlateSense distributable for the current platform.
# Usage: scripts/build.sh [--onefile]
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HERE"

python - <<'PY'
import sys
if not ((3, 11) <= sys.version_info[:2] <= (3, 13)):
    print(f"[ERROR] Unsupported Python {sys.version.split()[0]}. "
          "Python 3.11, 3.12 or 3.13 is required.")
    print("Install one from https://www.python.org/downloads/ and try again.")
    sys.exit(1)
PY

if [ ! -d ".venv" ]; then
    echo "[setup] Creating virtual environment..."
    python3 -m venv .venv
fi

# shellcheck disable=SC1091
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
elif [ -f ".venv/Scripts/activate" ]; then
    # MSYS/Git-bash on Windows
    source .venv/Scripts/activate
fi

python -m pip install --upgrade pip
echo "[setup] Installing runtime + build dependencies..."
python -m pip install -r requirements-dev.txt

ONEFILE=""
if [ "${1:-}" = "--onefile" ]; then
    ONEFILE="--onefile"
fi

echo "[build] Running PyInstaller..."
pyinstaller PlateSense.spec --clean --noconfirm $ONEFILE

echo ""
echo "============================================================"
echo " Build finished successfully."
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo " Output: $HERE/dist/PlateSense.app"
elif [[ "$OSTYPE" == "msys"* || "$OSTYPE" == "cygwin"* ]]; then
    echo " Output: $HERE/dist/PlateSense/PlateSense.exe"
else
    echo " Output: $HERE/dist/PlateSense/PlateSense"
fi
echo "============================================================"
