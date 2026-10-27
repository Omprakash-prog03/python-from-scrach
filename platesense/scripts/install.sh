#!/usr/bin/env bash
# PlateSense one-command installer for Linux / macOS.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/Omprakash-prog03/python-from-scrach/main/platesense/scripts/install.sh | bash
#
# Or for a specific version:
#   curl -fsSL <url> | VERSION=v1.0.0 bash
#
# What it does (from-source install, since we don't ship Linux/macOS binaries
# in this release):
#   1. Clones (or updates) the repo into ~/.platesense-src
#   2. Creates a venv at ~/.local/share/PlateSense/venv
#   3. Installs runtime deps
#   4. Creates a launcher at ~/.local/bin/platesense
#   5. Creates a desktop entry on Linux

set -euo pipefail

REPO="Omprakash-prog03/python-from-scrach"
SRC_DIR="${PLATESENSE_SRC:-$HOME/.platesense-src}"
INSTALL_DIR="${PLATESENSE_HOME:-$HOME/.local/share/PlateSense}"
BIN_DIR="${PLATESENSE_BIN:-$HOME/.local/bin}"
VERSION="${VERSION:-main}"

log()  { printf '\033[36m[platesense]\033[0m %s\n' "$*"; }
ok()   { printf '           \033[32m%s\033[0m\n' "$*"; }
warn() { printf '           \033[33m%s\033[0m\n' "$*"; }
die()  { printf '           \033[31m%s\033[0m\n' "$*" >&2; exit 1; }

log "PlateSense installer (Linux/macOS)"

# --- Check python -----------------------------------------------------------
PY=""
for cand in python3.12 python3.11 python3.13 python3; do
    if command -v "$cand" >/dev/null 2>&1; then
        ver=$("$cand" -c 'import sys; print("%d.%d" % sys.version_info[:2])')
        case "$ver" in
            3.11|3.12|3.13) PY="$cand"; break;;
            *) ;;
        esac
    fi
done
if [ -z "$PY" ]; then
    die "Python 3.11, 3.12 or 3.13 is required. Install from https://www.python.org/ or your package manager first."
fi
ok "Using $($PY --version | head -n1)"

# --- Clone / update source --------------------------------------------------
if [ ! -d "$SRC_DIR/.git" ]; then
    log "Cloning PlateSense ($VERSION) into $SRC_DIR"
    git clone --depth 1 --branch "$VERSION" "https://github.com/$REPO.git" "$SRC_DIR" 2>/dev/null || \
        git clone --depth 1 "https://github.com/$REPO.git" "$SRC_DIR"
else
    log "Updating existing clone at $SRC_DIR"
    git -C "$SRC_DIR" fetch --tags
    git -C "$SRC_DIR" checkout "$VERSION" 2>/dev/null || git -C "$SRC_DIR" checkout main
    git -C "$SRC_DIR" pull --ff-only || warn "Pull failed; continuing with existing checkout."
fi

APP_DIR="$SRC_DIR/platesense"
[ -d "$APP_DIR" ] || die "Expected $APP_DIR to exist."

# --- Venv + deps ------------------------------------------------------------
VENV_DIR="$INSTALL_DIR/venv"
mkdir -p "$INSTALL_DIR"
if [ ! -d "$VENV_DIR" ]; then
    log "Creating virtual environment at $VENV_DIR"
    "$PY" -m venv "$VENV_DIR"
fi
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
python -m pip install --upgrade pip
log "Installing dependencies..."
python -m pip install -r "$APP_DIR/requirements.txt"

# --- Launcher ---------------------------------------------------------------
mkdir -p "$BIN_DIR"
LAUNCHER="$BIN_DIR/platesense"
cat > "$LAUNCHER" <<EOF
#!/usr/bin/env bash
source "$VENV_DIR/bin/activate"
exec python "$APP_DIR/app.py" "\$@"
EOF
chmod +x "$LAUNCHER"
ok "Launcher: $LAUNCHER"

case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *) warn "$BIN_DIR is not on your PATH. Add it to your shell rc:"
       warn "   echo 'export PATH=\"$BIN_DIR:\$PATH\"' >> ~/.bashrc"
       ;;
esac

# --- Linux desktop entry ----------------------------------------------------
if [ "$(uname -s)" = "Linux" ]; then
    APPS="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
    mkdir -p "$APPS"
    ICON_SRC="$APP_DIR/assets/icons/app_icon.png"
    ICON_DST="$INSTALL_DIR/app_icon.png"
    if [ -f "$ICON_SRC" ]; then cp "$ICON_SRC" "$ICON_DST"; fi
    cat > "$APPS/platesense.desktop" <<EOF
[Desktop Entry]
Name=PlateSense
Comment=Indian number-plate detection
Exec=$LAUNCHER
Icon=$ICON_DST
Terminal=false
Type=Application
Categories=Utility;Graphics;
EOF
    ok "Desktop entry installed."
fi

cat <<EOS

============================================================
 PlateSense installed successfully.
 Install dir : $INSTALL_DIR
 Run command : platesense
============================================================
EOS
echo
