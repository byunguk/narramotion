#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m venv .build-venv
source .build-venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
rm -rf build dist
pyinstaller --clean --onefile --name narramotion src/narramotion/cli.py
printf '\nBuilt: %s/dist/narramotion\n' "$PWD"
