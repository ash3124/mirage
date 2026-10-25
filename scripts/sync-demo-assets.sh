#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
SOURCE_DIR="$REPO_ROOT/demo-assets"
DESTINATION_DIR="$REPO_ROOT/frontend/public/demo"

if [ ! -f "$SOURCE_DIR/manifest.json" ]; then
  echo "Demo manifest not found at $SOURCE_DIR/manifest.json. Generate demo assets first." >&2
  exit 1
fi

mkdir -p "$DESTINATION_DIR"
cp -R "$SOURCE_DIR/." "$DESTINATION_DIR/"
echo "Demo assets synced to $DESTINATION_DIR"
