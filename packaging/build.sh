#!/usr/bin/env bash
# Builds a standalone Voice-to-Text executable and installs it for the current user:
#   ~/.local/opt/voice-to-text/voice-to-text        (the app bundle)
#   ~/.local/bin/voice-to-text                       (symlink, for terminal use)
#   ~/.local/share/applications/voice-to-text.desktop (app menu / search entry)
#
# Usage: packaging/build.sh [--no-install]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PY=".venv/bin/python"
if [[ ! -x "$PY" ]]; then
  echo ">> Creating build venv (.venv, Python 3.12)"
  uv venv --python 3.12 .venv
fi
echo ">> Installing dependencies"
uv pip install --python "$PY" -r requirements.txt pyinstaller nvidia-cublas-cu12 "nvidia-cudnn-cu12>=9,<10"

echo ">> Building"
"$PY" -m PyInstaller --noconfirm --clean \
  --distpath build/dist --workpath build/work \
  packaging/voice-to-text.spec

[[ "${1:-}" == "--no-install" ]] && { echo "Built: build/dist/voice-to-text/voice-to-text"; exit 0; }

DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
INSTALL_DIR="$HOME/.local/opt/voice-to-text"

echo ">> Installing to $INSTALL_DIR"
rm -rf "$INSTALL_DIR"
mkdir -p "$(dirname "$INSTALL_DIR")" "$HOME/.local/bin" "$DATA_HOME/applications" "$DATA_HOME/icons/hicolor/scalable/apps"
cp -a build/dist/voice-to-text "$INSTALL_DIR"
ln -sf "$INSTALL_DIR/voice-to-text" "$HOME/.local/bin/voice-to-text"
# New icon name: GNOME Shell caches icons by name until the session restarts, so a new name shows the new artwork at once
rm -f "$DATA_HOME/icons/hicolor/scalable/apps/voice-to-text.svg"
cp assets/icon.svg "$DATA_HOME/icons/hicolor/scalable/apps/voice-to-text-app.svg"

# Carry over history/settings from the dev database on first install
if [[ -f transcriptions.db && ! -f "$DATA_HOME/voice-to-text/transcriptions.db" ]]; then
  mkdir -p "$DATA_HOME/voice-to-text"
  cp transcriptions.db "$DATA_HOME/voice-to-text/transcriptions.db"
  echo ">> Copied existing transcriptions.db to $DATA_HOME/voice-to-text/"
fi

cat > "$DATA_HOME/applications/voice-to-text.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Voice to Text
GenericName=Speech to Text
Comment=Local Whisper transcription with a global hotkey
Exec=$INSTALL_DIR/voice-to-text
Icon=voice-to-text-app
Terminal=false
Categories=Utility;
Keywords=voice;speech;transcription;whisper;dictation;voz;transcrição;
StartupNotify=false
StartupWMClass=voice-to-text
EOF

update-desktop-database "$DATA_HOME/applications" 2>/dev/null || true
gtk-update-icon-cache -q "$DATA_HOME/icons/hicolor" 2>/dev/null || true

echo ">> Done. Search for \"Voice to Text\" in the app menu."
