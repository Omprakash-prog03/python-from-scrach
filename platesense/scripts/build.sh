#!/usr/bin/env bash
# Build a standalone PlateSense distributable for the current platform.
# Usage: scripts/build.sh [--onefile]
set -e
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HERE"

if [ ! -d ".venv" ]; then
    python -m venv .venv
fi
# Activate
# shellcheck disable=SC1091
source .venv/bin/activate 2>/dev/null || .venv/Scripts/activate.bat

pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

ONEFILE=""
if [ "${1:-}" = "--onefile" ]; then
    ONEFILE="--onefile"
fi

pyinstaller PlateSense.spec --clean --noconfirm $ONEFILE

echo ""
echo "Build finished. Output:"
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "  $HERE/dist/PlateSense.app"
elif [[ "$OSTYPE" == "msys"* || "$OSTYPE" == "cygwin"* ]]; then
    echo "  $HERE/dist/PlateSense/PlateSense.exe"
else
    echo "  $HERE/dist/PlateSense/PlateSense"
fi
