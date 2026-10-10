#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m pip install 'pyinstaller>=6,<7'
python3 -m PyInstaller --noconfirm --clean --windowed --name TakePath \
    --icon assets/takepath.icns \
    --osx-bundle-identifier org.takepath.app \
    --add-data 'assets:assets' --add-data 'examples:examples' main.py
printf '\nApp bundle: dist/TakePath.app\n'
# Not signed/not notarized. macOS Gatekeeper will ask users to approve it.
