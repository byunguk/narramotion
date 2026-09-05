#!/usr/bin/env bash
set -euo pipefail

echo "==> 1. Python syntax check"
python -m compileall -q src/narramotion narramotion_main.py

echo "==> 2. Pytest"
pytest

echo "==> 3. Git diff check"
git diff --check

echo "==> 4. Shell script syntax"
bash -n scripts/build_macos.sh
bash -n scripts/package_release.sh

echo "==> 5. Old package-name check"

if grep -RInE \
  --exclude-dir=.git \
  --exclude-dir=.venv \
  --exclude-dir=.build-venv \
  --exclude-dir=.narramotion \
  --exclude-dir=build \
  --exclude-dir=dist \
  --exclude-dir='*.egg-info' \
  --exclude=README.md \
  --exclude=verify_release.sh \
  'bible_video_maker|bible-video|\.bvm-work' \
  src tests scripts homebrew narramotion_main.py pyproject.toml project.example.yaml 2>/dev/null; then

  echo
  echo "ERROR: old package-name references found."
  exit 1
fi

echo "==> 6. Secret pattern check"
if git grep -n -E \
  'GEMINI_API_KEY=.+' \
  -- ':!README.md' ':!project.example.yaml'; then
  echo
  echo "ERROR: possible Gemini API key assignment found."
  exit 1
fi

echo
echo "All source checks passed."