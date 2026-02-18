#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <output-name> <executable> [args...]" >&2
  exit 1
fi

OUT_NAME="$1"
shift

if ! command -v renderdoccmd >/dev/null 2>&1; then
  echo "error: renderdoccmd not found" >&2
  exit 1
fi

mkdir -p tests/fixtures
OUT_PATH="tests/fixtures/${OUT_NAME}.rdc"

renderdoccmd capture -c "$OUT_PATH" -- "$@"

echo "fixture written: $OUT_PATH"
