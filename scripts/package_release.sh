#!/usr/bin/env bash
#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

VERSION="${1:-0.1.0}"

ARCH="$(uname -m)"

case "$ARCH" in
  arm64) LABEL=arm64 ;;
  x86_64) LABEL=x64 ;;
  *)
    echo "Unsupported architecture: $ARCH" >&2
    exit 1
    ;;
esac

APP_DIR="dist/narramotion"
BINARY="$APP_DIR/narramotion"

[[ -x "$BINARY" ]] || {
  echo "Run scripts/build_macos.sh first" >&2
  exit 1
}

OUT="dist/narramotion-${VERSION}-macos-${LABEL}.tar.gz"

rm -f "$OUT"

tar -C dist -czf "$OUT" narramotion

echo
echo "SHA256:"
shasum -a 256 "$OUT"

echo
echo "Release artifact: $OUT"
echo "Version: $VERSION"
echo "Architecture: $LABEL"