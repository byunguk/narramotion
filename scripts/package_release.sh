#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
VERSION="${1:-0.1.0}"
ARCH="$(uname -m)"
case "$ARCH" in
  arm64) LABEL=arm64 ;;
  x86_64) LABEL=x64 ;;
  *) echo "Unsupported architecture: $ARCH" >&2; exit 1 ;;
esac
[[ -x dist/narramotion ]] || { echo "Run scripts/build_macos.sh first" >&2; exit 1; }
OUT="narramotion-macos-${LABEL}.tar.gz"
tar -C dist -czf "$OUT" narramotion
shasum -a 256 "$OUT"
echo "Release artifact: $OUT (version $VERSION)"
