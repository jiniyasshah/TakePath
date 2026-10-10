#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python -m pip install 'pyinstaller>=6,<7'
python -m PyInstaller --noconfirm --clean --windowed --name TakePath \
    --add-data 'assets:assets' --add-data 'examples:examples' main.py
printf '\nExecutable bundle: dist/TakePath/TakePath\n'
# AppImage packaging is handled by the GitHub release job because it needs
# appimagetool and an AppDir structure, not simply a PyInstaller executable.
