#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

IDENTITY="${APPLE_CODESIGN_IDENTITY:-}"

if [[ -z "$IDENTITY" ]]; then
  echo "APPLE_CODESIGN_IDENTITY is not set" >&2
  echo 'Example:' >&2
  echo '  export APPLE_CODESIGN_IDENTITY="Developer ID Application: Gndsoft LLC (4ANJ4SUYK4)"' >&2
  exit 1
fi

APP_DIR="dist/narramotion"

if [[ ! -d "$APP_DIR" ]]; then
  echo "Build output not found: $APP_DIR" >&2
  echo "Run ./scripts/build_macos.sh first" >&2
  exit 1
fi

if [[ ! -x "$APP_DIR/narramotion" ]]; then
  echo "Main executable not found: $APP_DIR/narramotion" >&2
  exit 1
fi

echo "Signing nested Mach-O files..."

find "$APP_DIR" -type f -print0 | while IFS= read -r -d '' FILEPATH; do
  if file "$FILEPATH" | grep -q "Mach-O"; then
    echo "  signing: $FILEPATH"

    codesign \
      --force \
      --options runtime \
      --timestamp \
      --sign "$IDENTITY" \
      "$FILEPATH"
  fi
done

echo
echo "Signing main executable..."

codesign \
  --force \
  --options runtime \
  --timestamp \
  --sign "$IDENTITY" \
  "$APP_DIR/narramotion"

echo
echo "Verifying main executable..."

codesign \
  --verify \
  --verbose=4 \
  "$APP_DIR/narramotion"

echo
echo "Signature details:"
codesign \
  -dv \
  --verbose=4 \
  "$APP_DIR/narramotion" 2>&1

echo
echo "Signing complete."