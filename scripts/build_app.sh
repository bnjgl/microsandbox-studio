#!/usr/bin/env bash
# Builds the desktop app for the current OS into dist/ (on macOS: dist/Microsandbox Studio.app).
set -euo pipefail
cd "$(dirname "$0")/.."

(cd frontend && npm ci --include=optional && npm run build)
uv run python scripts/fetch_shpool.py

extra=()
icon=()
case "$(uname -s)" in
  Darwin) icon=(--icon src/microsandbox_studio/assets/icon.icns) ;;
  MINGW* | MSYS* | CYGWIN*) icon=(--icon src/microsandbox_studio/assets/icon.ico) ;;
  # GTK cannot be bundled, so the Linux build uses the self-contained Qt backend
  Linux) extra=(--with "pywebview[qt]") ;;
esac

uv run --with pyinstaller ${extra[@]+"${extra[@]}"} pyinstaller \
  --name "Microsandbox Studio" --windowed --noconfirm ${icon[@]+"${icon[@]}"} \
  --collect-data microsandbox_studio \
  --collect-all microsandbox \
  scripts/launcher.py
