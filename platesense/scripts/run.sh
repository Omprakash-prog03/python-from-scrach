#!/usr/bin/env bash
# Run PlateSense from a source checkout.
set -e
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HERE"

if [ ! -d ".venv" ]; then
    echo "No virtual environment found. Creating one..."
    python3 -m venv .venv
    # shellcheck disable=SC1091
    source .venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
else
    # shellcheck disable=SC1091
    source .venv/bin/activate 2>/dev/null || . .venv/Scripts/activate
fi

exec python app.py "$@"
