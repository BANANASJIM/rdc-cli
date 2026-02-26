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
TMP_CAPTURE_BASE=""
RDC="uv run rdc"
OS_NAME=$(uname -s)
REPLAY_READY=0

if [ ! -f "$CAPTURE" ]; then
  echo -e "${RED}error: fixture not found: $CAPTURE${NC}"
  echo "Run from repo root: pixi run e2e"
  exit 1
fi

if [ ! -f ".local/renderdoc/renderdoc.so" ] && [ "$OS_NAME" != "Darwin" ]; then
  echo -e "${RED}error: renderdoc.so not found${NC}"
  echo "Run: pixi run setup-renderdoc"
  exit 1
fi

if command -v /usr/bin/vkcube > /dev/null 2>&1; then
  TMP_CAPTURE_BASE="/tmp/rdc-e2e-$$.rdc"
  if $RDC capture --output "$TMP_CAPTURE_BASE" -- /usr/bin/vkcube > /dev/null 2>&1; then
    if [ -f "${TMP_CAPTURE_BASE%.rdc}_frame0.rdc" ]; then
      CAPTURE="${TMP_CAPTURE_BASE%.rdc}_frame0.rdc"
    fi
  fi
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
  if [ -n "$TMP_CAPTURE_BASE" ]; then
    rm -f "$TMP_CAPTURE_BASE" "${TMP_CAPTURE_BASE%.rdc}_frame0.rdc" > /dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

# --- Version ---
echo "=== Layer 0: Version ==="
check_output "rdc --version" "0." $RDC --version
check "rdc --help" $RDC --help

# --- Doctor ---
echo ""
echo "=== Layer 1: Doctor ==="
DOCTOR_OUTPUT=$($RDC doctor 2>&1 || true)
if echo "$DOCTOR_OUTPUT" | grep -q "replay-support: renderdoc replay API surface found"; then
  REPLAY_READY=1
fi
if echo "$DOCTOR_OUTPUT" | grep -q "replay-support:"; then
  echo -e "  ${GREEN}✓${NC} rdc doctor"
  PASS=$((PASS + 1))
else
  echo -e "  ${RED}✗${NC} rdc doctor"
  FAIL=$((FAIL + 1))
fi

# --- Session lifecycle ---
echo ""
echo "=== Layer 2: Session lifecycle ==="
$RDC close > /dev/null 2>&1 || true
check "rdc open" $RDC open "$CAPTURE"
check_output "rdc status" "capture:" $RDC status

# --- Read-only queries ---
echo ""
echo "=== Layer 3: Read-only queries ==="
if [ "$REPLAY_READY" -eq 1 ]; then
  check_nonzero "rdc info" $RDC info
  check_nonzero "rdc stats" $RDC stats
  check_nonzero "rdc events" $RDC events
  check_nonzero "rdc draws" $RDC draws
  check_nonzero "rdc passes" $RDC passes
  check_nonzero "rdc resources" $RDC resources
  check_nonzero "rdc shaders" $RDC shaders
else
  check_output "rdc info (no replay)" "no replay loaded" $RDC info
  check_output "rdc stats (no replay)" "no replay loaded" $RDC stats
  check_output "rdc draws (no replay)" "no replay loaded" $RDC draws
fi

# --- VFS ---
echo ""
echo "=== Layer 4: VFS ==="
check_nonzero "rdc ls /" $RDC ls /
check_nonzero "rdc ls /draws" $RDC ls /draws
check_nonzero "rdc tree / --depth 1" $RDC tree / --depth 1
if [ "$REPLAY_READY" -eq 1 ]; then
  check_nonzero "rdc cat /info" $RDC cat /info
  check_nonzero "rdc cat /stats" $RDC cat /stats
else
  check_output "rdc cat /info (no replay)" "no replay loaded" $RDC cat /info
  check_output "rdc cat /stats (no replay)" "no replay loaded" $RDC cat /stats
fi

# --- VFS completion ---
echo ""
echo "=== Layer 5: VFS completion ==="
check_nonzero "complete /" $RDC _complete /
check_nonzero "complete /d" $RDC _complete /d
if [ "$REPLAY_READY" -eq 1 ]; then
  check_output "complete /d → /draws/" "/draws/" $RDC _complete /d
else
  check_output "complete /d (no replay)" "no replay loaded" $RDC _complete /d
fi
 COMP_OUTPUT=$(env _RDC_COMPLETE=bash_complete COMP_WORDS="rdc ls /d" COMP_CWORD=2 $RDC 2>&1 || true)
 if [ "$REPLAY_READY" -eq 1 ] && echo "$COMP_OUTPUT" | grep -Eq "(/draws/|dir,/draws)"; then
   echo -e "  ${GREEN}✓${NC} click shell_complete /d"
   PASS=$((PASS + 1))
elif [ "$REPLAY_READY" -eq 0 ] && echo "$COMP_OUTPUT" | grep -q "no replay loaded"; then
  echo -e "  ${GREEN}✓${NC} click shell_complete /d (no replay)"
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
