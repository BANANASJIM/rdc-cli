#!/usr/bin/env bash
# End-to-end test: runs real rdc commands against a capture file.
# Usage: pixi run e2e
# Requires: renderdoc Python module available on system Python.
#
# NOTE: Uses pip install --break-system-packages because renderdoc is a
# compiled .so only available to system Python, not inside uv/pixi venvs.
# This is intentional for e2e — we test the real user environment.
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'
PASS=0
FAIL=0
CAPTURE="tests/fixtures/hello_triangle.rdc"

if [ ! -f "$CAPTURE" ]; then
  echo -e "${RED}error: fixture not found: $CAPTURE${NC}"
  echo "Run from repo root: pixi run e2e"
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
  rdc close > /dev/null 2>&1 || true
}
trap cleanup EXIT

# --- Verify system rdc is current (run pixi run dev-install first) ---
echo "=== Layer 0: Version ==="
check_output "rdc --version" "0." rdc --version
check "rdc --help" rdc --help

# --- Doctor ---
echo ""
echo "=== Layer 1: Doctor ==="
check "rdc doctor" rdc doctor

# --- Session lifecycle ---
echo ""
echo "=== Layer 2: Session lifecycle ==="
rdc close > /dev/null 2>&1 || true
check "rdc open" rdc open "$CAPTURE"
check_output "rdc status" "hello_triangle" rdc status

# --- Read-only queries ---
echo ""
echo "=== Layer 3: Read-only queries ==="
check_nonzero "rdc info" rdc info
check_nonzero "rdc stats" rdc stats
check_nonzero "rdc events" rdc events
check_nonzero "rdc draws" rdc draws
check_nonzero "rdc passes" rdc passes
check_nonzero "rdc resources" rdc resources
check_nonzero "rdc shaders" rdc shaders

# --- VFS ---
echo ""
echo "=== Layer 4: VFS ==="
check_nonzero "rdc ls /" rdc ls /
check_nonzero "rdc ls /draws" rdc ls /draws
check_nonzero "rdc tree / --depth 1" rdc tree / --depth 1
check_nonzero "rdc cat /info" rdc cat /info
check_nonzero "rdc cat /stats" rdc cat /stats

# --- VFS completion ---
echo ""
echo "=== Layer 5: VFS completion ==="
check_nonzero "complete /" rdc _complete /
check_nonzero "complete /d" rdc _complete /d
check_output "complete /d → /draws/" "/draws/" rdc _complete /d
COMP_OUTPUT=$(env _RDC_COMPLETE=bash_complete COMP_WORDS="rdc ls /d" COMP_CWORD=2 rdc 2>&1 || true)
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
check "rdc completion bash" rdc completion bash
check "rdc completion zsh" rdc completion zsh
check "rdc completion fish" rdc completion fish

# --- Close ---
echo ""
echo "=== Layer 7: Close ==="
check "rdc close" rdc close
check_output "rdc status (after close)" "no active session" rdc status

# --- Summary ---
echo ""
echo "================================"
echo -e "  ${GREEN}$PASS passed${NC}, ${RED}$FAIL failed${NC}"
echo "================================"

[ "$FAIL" -eq 0 ] || exit 1
