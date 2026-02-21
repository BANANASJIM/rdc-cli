#!/usr/bin/env bash
# Packaging verification script — runs locally before release.
# Usage: ./scripts/verify-package.sh
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'
PASS=0
FAIL=0

check() {
  local desc="$1"; shift
  if "$@" > /dev/null 2>&1; then
    echo -e "  ${GREEN}✓${NC} $desc"
    PASS=$((PASS + 1))
  else
    echo -e "  ${RED}✗${NC} $desc"
    FAIL=$((FAIL + 1))
  fi
}

check_output() {
  local desc="$1"; local expected="$2"; shift 2
  local output
  output=$("$@" 2>&1) || true
  if echo "$output" | grep -q "$expected"; then
    echo -e "  ${GREEN}✓${NC} $desc"
    PASS=$((PASS + 1))
  else
    echo -e "  ${RED}✗${NC} $desc (expected '$expected')"
    FAIL=$((FAIL + 1))
  fi
}

VERSION=$(grep -m1 '^version' pyproject.toml | sed 's/.*"\(.*\)".*/\1/')
TEST_ENV=$(mktemp -d)
trap 'rm -rf "$TEST_ENV"' EXIT

echo "=== Layer 0: Code quality ==="
check "ruff check"            uv run ruff check src tests
check "ruff format"           uv run ruff format --check src tests
check "mypy"                  uv run mypy src
check "pytest (653+ tests)"   uv run pytest tests/unit -q --cov=rdc --cov-fail-under=80

echo ""
echo "=== Layer 1: Build validation ==="
rm -rf dist/
check "uv build"              uv build
check "twine check"           uvx twine check dist/*
check "wheel contents"        uvx check-wheel-contents dist/*.whl
check "sdist exists"          test -f dist/*.tar.gz
check "wheel exists"          test -f dist/*.whl

echo ""
echo "=== Layer 2: Install + smoke test ==="
uv venv "$TEST_ENV/venv" > /dev/null 2>&1
PYTHON="$TEST_ENV/venv/bin/python"
RDC="$TEST_ENV/venv/bin/rdc"
check "clean venv install"    uv pip install dist/*.whl --python "$PYTHON"
check_output "rdc --version"  "$VERSION"  "$RDC" --version
check "rdc --help"            "$RDC" --help
check "import rdc.cli"        "$PYTHON" -c "from rdc.cli import main"
check "import rdc.daemon_server" "$PYTHON" -c "from rdc.daemon_server import _handle_request"
check "rdc completion bash"   "$RDC" completion bash
check "rdc completion zsh"    "$RDC" completion zsh
check "rdc completion fish"   "$RDC" completion fish

echo ""
echo "=== Layer 3: Version consistency ==="
INIT_VERSION=$("$PYTHON" -c "from rdc import __version__; print(__version__)")
check_output "pyproject.toml version"  "$VERSION"      echo "$VERSION"
check_output "__init__.py version"     "$VERSION"      echo "$INIT_VERSION"

echo ""
echo "================================"
echo -e "  ${GREEN}$PASS passed${NC}, ${RED}$FAIL failed${NC}"
echo "================================"

[ "$FAIL" -eq 0 ] || exit 1
