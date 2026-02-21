#!/usr/bin/env bash
# End-to-end test: runs rdc commands via uv dev environment.
# Usage: pixi run e2e
# Requires: pixi run setup-renderdoc (one-time)
#
# Uses RENDERDOC_PYTHON_PATH set by pixi activation to find renderdoc.so
# in .local/renderdoc/. Fully isolated — system Python is never modified.
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'
PASS=0
FAIL=0
CAPTURE="tests/fixtures/hello_triangle.rdc"
RDC="uv run rdc"

if [ ! -f "$CAPTURE" ]; then
  echo -e "${RED}error: fixture not found: $CAPTURE${NC}"
  echo "Run from repo root: pixi run e2e"
  exit 1
fi

if [ ! -f ".local/renderdoc/renderdoc.so" ]; then
  echo -e "${RED}error: renderdoc.so not found${NC}"
  echo "Run: pixi run setup-renderdoc"
  exit 1
fi

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
    echo -e "  ${RED}✗${NC} $desc (expected '$expected', got '$(echo "$output" | head -1)')"
    FAIL=$((FAIL + 1))
  fi
}

check_nonzero() {
  local desc="$1"; shift
  local output
  output=$("$@" 2>&1) || true
  if [ -n "$output" ]; then
    echo -e "  ${GREEN}✓${NC} $desc"
    PASS=$((PASS + 1))
  else
    echo -e "  ${RED}✗${NC} $desc (empty output)"
    FAIL=$((FAIL + 1))
  fi
}

cleanup() {
  $RDC close > /dev/null 2>&1 || true
}
trap cleanup EXIT

# --- Version ---
echo "=== Layer 0: Version ==="
check_output "rdc --version" "0." $RDC --version
check "rdc --help" $RDC --help

# --- Doctor ---
echo ""
echo "=== Layer 1: Doctor ==="
check "rdc doctor" $RDC doctor

# --- Session lifecycle ---
echo ""
echo "=== Layer 2: Session lifecycle ==="
$RDC close > /dev/null 2>&1 || true
check "rdc open" $RDC open "$CAPTURE"
check_output "rdc status" "hello_triangle" $RDC status

# --- Read-only queries ---
echo ""
echo "=== Layer 3: Read-only queries ==="
check_nonzero "rdc info" $RDC info
check_nonzero "rdc stats" $RDC stats
check_nonzero "rdc events" $RDC events
check_nonzero "rdc draws" $RDC draws
check_nonzero "rdc passes" $RDC passes
check_nonzero "rdc resources" $RDC resources
check_nonzero "rdc shaders" $RDC shaders

# --- VFS ---
echo ""
echo "=== Layer 4: VFS ==="
check_nonzero "rdc ls /" $RDC ls /
check_nonzero "rdc ls /draws" $RDC ls /draws
check_nonzero "rdc tree / --depth 1" $RDC tree / --depth 1
check_nonzero "rdc cat /info" $RDC cat /info
check_nonzero "rdc cat /stats" $RDC cat /stats

# --- VFS completion ---
echo ""
echo "=== Layer 5: VFS completion ==="
check_nonzero "complete /" $RDC _complete /
check_nonzero "complete /d" $RDC _complete /d
check_output "complete /d → /draws/" "/draws/" $RDC _complete /d
COMP_OUTPUT=$(env _RDC_COMPLETE=bash_complete COMP_WORDS="rdc ls /d" COMP_CWORD=2 $RDC 2>&1 || true)
if echo "$COMP_OUTPUT" | grep -q "/draws/"; then
  echo -e "  ${GREEN}✓${NC} click shell_complete /d → /draws/"
  PASS=$((PASS + 1))
else
  echo -e "  ${RED}✗${NC} click shell_complete /d (got '$COMP_OUTPUT')"
  FAIL=$((FAIL + 1))
fi

# --- Shell completion scripts ---
echo ""
echo "=== Layer 6: Completion scripts ==="
check "rdc completion bash" $RDC completion bash
check "rdc completion zsh" $RDC completion zsh
check "rdc completion fish" $RDC completion fish

# --- Close ---
echo ""
echo "=== Layer 7: Close ==="
check "rdc close" $RDC close
check_output "rdc status (after close)" "no active session" $RDC status

# --- Summary ---
echo ""
echo "================================"
echo -e "  ${GREEN}$PASS passed${NC}, ${RED}$FAIL failed${NC}"
echo "================================"

[ "$FAIL" -eq 0 ] || exit 1
