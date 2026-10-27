#!/usr/bin/env bash
# Run PlateSense from a source checkout.
set -e
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HERE"
exec python app.py "$@"
