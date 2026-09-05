#!/usr/bin/env bash
set -euo pipefail

rm -rf build dist

pyinstaller \
  --clean \
  --onedir \
  --name narramotion \
  narramotion_main.py

printf '\nBuilt: %s/dist/narramotion/narramotion\n' "$PWD"