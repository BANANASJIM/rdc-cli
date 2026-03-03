"""Cross-platform e2e smoke test for rdc CLI.

Replaces scripts/e2e-test.sh with a portable Python implementation.
Usage: pixi run e2e   (or: uv run python scripts/e2e_test.py)
"""

from __future__ import annotations

import atexit
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Globals
# ---------------------------------------------------------------------------

_pass_count = 0
_fail_count = 0
_replay_ready = False
_tmp_captures: list[Path] = []

_USE_COLOR = sys.stdout.isatty() and not os.environ.get("NO_COLOR")
_GREEN = "\033[0;32m" if _USE_COLOR else ""
_RED = "\033[0;31m" if _USE_COLOR else ""
_NC = "\033[0m" if _USE_COLOR else ""

_RDC = ["uv", "run", "rdc"]
_REPO_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------


def _emit(msg: str) -> None:
    sys.stdout.write(msg + "\n")
    sys.stdout.flush()


def _pass(desc: str) -> None:
    global _pass_count
    _pass_count += 1
    _emit(f"  {_GREEN}[ok]{_NC} {desc}")


def _fail(desc: str, detail: str = "") -> None:
    global _fail_count
    _fail_count += 1
    suffix = f" ({detail})" if detail else ""
    _emit(f"  {_RED}[FAIL]{_NC} {desc}{suffix}")


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _run(*cmd: str, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(cmd),
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _run_env(
    env_extra: dict[str, str],
    *cmd: str,
    timeout: int = 30,
) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, **env_extra}
    return subprocess.run(
        list(cmd),
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )


def _check(desc: str, *cmd: str) -> None:
    """Pass if command exits 0."""
    try:
        r = _run(*cmd)
        if r.returncode == 0:
            _pass(desc)
        else:
            _fail(desc, f"exit {r.returncode}")
    except Exception as exc:
        _fail(desc, str(exc))


def _check_output(desc: str, expected: str, *cmd: str) -> None:
    """Pass if *expected* appears in combined stdout+stderr."""
    try:
        r = _run(*cmd)
        combined = r.stdout + r.stderr
        if expected in combined:
            _pass(desc)
        else:
            first_line = combined.strip().split("\n")[0] if combined.strip() else "(empty)"
            _fail(desc, f"expected '{expected}', got '{first_line}'")
    except Exception as exc:
        _fail(desc, str(exc))


def _check_nonzero(desc: str, *cmd: str) -> None:
    """Pass if command exits 0 and produces non-empty output."""
    try:
        r = _run(*cmd)
        combined = (r.stdout + r.stderr).strip()
        if r.returncode == 0 and combined:
            _pass(desc)
        elif r.returncode != 0:
            _fail(desc, f"exit {r.returncode}")
        else:
            _fail(desc, "empty output")
    except Exception as exc:
        _fail(desc, str(exc))


# ---------------------------------------------------------------------------
# Self-capture
# ---------------------------------------------------------------------------


def _try_self_capture(fallback: Path) -> Path:
    """Attempt vkcube self-capture; return capture path."""
    vkcube = shutil.which("vkcube")
    if not vkcube:
        return fallback

    tmp_base = Path(tempfile.gettempdir()) / f"rdc-e2e-{os.getpid()}.rdc"
    try:
        _run(*_RDC, "capture", "--output", str(tmp_base), "--", vkcube, timeout=30)
        frame0 = tmp_base.with_name(tmp_base.stem + "_frame0.rdc")
        _tmp_captures.append(tmp_base)
        if frame0.exists():
            _tmp_captures.append(frame0)
            return frame0
    except Exception as exc:
        _emit(f"  self-capture failed: {exc}")
    _tmp_captures.append(tmp_base)
    return fallback


def _cleanup_captures() -> None:
    for p in _tmp_captures:
        try:
            p.unlink(missing_ok=True)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Layers
# ---------------------------------------------------------------------------


def _layer0_version() -> None:
    _emit("=== Layer 0: Version ===")
    _check_output("rdc --version", "0.", *_RDC, "--version")
    _check("rdc --help", *_RDC, "--help")


def _layer1_doctor() -> None:
    global _replay_ready
    _emit("\n=== Layer 1: Doctor ===")
    try:
        r = _run(*_RDC, "doctor")
        combined = r.stdout + r.stderr
        if "replay-support: renderdoc replay API surface found" in combined:
            _replay_ready = True
        if "replay-support:" in combined:
            _pass("rdc doctor")
        else:
            _fail("rdc doctor")
    except Exception as exc:
        _fail("rdc doctor", str(exc))


def _layer2_session(capture: Path) -> None:
    _emit("\n=== Layer 2: Session lifecycle ===")
    # ensure clean state
    _run(*_RDC, "close")
    _check("rdc open", *_RDC, "open", str(capture))
    _check_output("rdc status", "capture:", *_RDC, "status")


def _layer3_queries() -> None:
    _emit("\n=== Layer 3: Read-only queries ===")
    if _replay_ready:
        for cmd in ("info", "stats", "events", "draws", "passes", "resources", "shaders"):
            _check_nonzero(f"rdc {cmd}", *_RDC, cmd)
    else:
        for cmd in ("info", "stats", "draws"):
            _check_output(f"rdc {cmd} (no replay)", "no replay loaded", *_RDC, cmd)


def _layer4_vfs() -> None:
    _emit("\n=== Layer 4: VFS ===")
    _check_nonzero("rdc ls /", *_RDC, "ls", "/")
    _check_nonzero("rdc ls /draws", *_RDC, "ls", "/draws")
    _check_nonzero("rdc tree / --depth 1", *_RDC, "tree", "/", "--depth", "1")
    if _replay_ready:
        _check_nonzero("rdc cat /info", *_RDC, "cat", "/info")
        _check_nonzero("rdc cat /stats", *_RDC, "cat", "/stats")
    else:
        _check_output("rdc cat /info (no replay)", "no replay loaded", *_RDC, "cat", "/info")
        _check_output("rdc cat /stats (no replay)", "no replay loaded", *_RDC, "cat", "/stats")


def _layer5_completion() -> None:
    _emit("\n=== Layer 5: VFS completion ===")
    _check_nonzero("complete /", *_RDC, "_complete", "/")
    _check_nonzero("complete /d", *_RDC, "_complete", "/d")

    if _replay_ready:
        _check_output("complete /d -> /draws/", "/draws/", *_RDC, "_complete", "/d")
    else:
        _check_output("complete /d (no replay)", "no replay loaded", *_RDC, "_complete", "/d")

    # Click shell_complete env var test
    env_extra = {
        "_RDC_COMPLETE": "bash_complete",
        "COMP_WORDS": "rdc ls /d",
        "COMP_CWORD": "2",
    }
    try:
        r = _run_env(env_extra, *_RDC, timeout=10)
        combined = r.stdout + r.stderr
        if _replay_ready and ("/draws/" in combined or "dir,/draws" in combined):
            _pass("click shell_complete /d")
        elif not _replay_ready and "no replay loaded" in combined:
            _pass("click shell_complete /d (no replay)")
        else:
            first_line = combined.strip().split("\n")[0] if combined.strip() else "(empty)"
            _fail("click shell_complete /d", f"got '{first_line}'")
    except Exception as exc:
        _fail("click shell_complete /d", str(exc))


def _layer6_completion_scripts() -> None:
    _emit("\n=== Layer 6: Completion scripts ===")
    for shell in ("bash", "zsh", "fish"):
        _check(f"rdc completion {shell}", *_RDC, "completion", shell)


def _layer7_close() -> None:
    _emit("\n=== Layer 7: Close ===")
    _check("rdc close", *_RDC, "close")
    _check_output("rdc status (after close)", "no active session", *_RDC, "status")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    """Run all e2e smoke-test layers and return exit code."""
    fallback = _REPO_ROOT / "tests" / "fixtures" / "hello_triangle.rdc"
    if not fallback.exists():
        _emit(f"{_RED}error: fixture not found: {fallback}{_NC}")
        _emit("Run from repo root: pixi run e2e")
        return 1

    # Check renderdoc availability
    if sys.platform == "linux":
        rd = _REPO_ROOT / ".local" / "renderdoc" / "renderdoc.so"
    elif sys.platform == "win32":
        rd = _REPO_ROOT / ".local" / "renderdoc" / "renderdoc.pyd"
    else:
        rd = None  # macOS: skip check
    if rd is not None and not rd.exists():
        _emit(f"{_RED}error: {rd.name} not found{_NC}")
        _emit("Run: pixi run setup-renderdoc")
        return 1

    atexit.register(_cleanup_captures)
    capture = _try_self_capture(fallback)

    _layer0_version()
    _layer1_doctor()
    _layer2_session(capture)
    _layer3_queries()
    _layer4_vfs()
    _layer5_completion()
    _layer6_completion_scripts()
    _layer7_close()

    _emit("")
    _emit("================================")
    _emit(f"  {_GREEN}{_pass_count} passed{_NC}, {_RED}{_fail_count} failed{_NC}")
    _emit("================================")

    return 1 if _fail_count > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
