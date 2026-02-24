# Phase M: macOS Support — Proposal

## Summary

Phase M adds macOS as a first-class platform for rdc-cli, covering Homebrew path discovery,
doctor checks, CI validation, README install docs, and a `/proc`-free `is_pid_alive()`.
macOS is treated as a **remote replay thin client** only — local capture is not supported
(upstream RenderDoc does not support macOS capture).

## Motivation

Phase 6/7 remote capture and replay work over TCP; macOS users can connect to a Linux/Windows
host running `rdc serve` without needing GPU-side capture support. Without platform plumbing
the `doctor` command mis-reports macOS as healthy when renderdoc is missing, path discovery
silently skips Homebrew locations, and `is_pid_alive()` silently degrades on macOS.

## Design

### M1: Homebrew search paths (`_platform.py`)

`renderdoc_search_paths()` gains darwin-specific entries inserted before the generic Linux
fallbacks: `/opt/homebrew/opt/renderdoc/lib` (ARM), `/usr/local/opt/renderdoc/lib` (Intel),
and `~/.local/renderdoc` (user build output from `build_renderdoc.py`).
`renderdoccmd_search_paths()` similarly gains `/opt/homebrew/bin/renderdoccmd`.

### M2: Doctor macOS checks (`doctor.py`)

Three new sub-checks gated on `sys.platform == "darwin"`:
- `_check_mac_xcode_cli()` — verifies `xcode-select -p` exits 0.
- `_check_mac_homebrew()` — verifies `brew` is on PATH.
- `_check_mac_renderdoc_dylib()` — verifies at least one `.so`/`.dylib` found via M1 paths.

`_make_build_hint()` gains a darwin branch with Homebrew install instructions.
`run_doctor()` calls these checks when `sys.platform == "darwin"`.

### M3: CI matrix (`macos-latest`)

macOS runner added to the test matrix but restricted to `workflow_dispatch` trigger and
release tag pushes to contain cost (~10× ubuntu price). Only Python 3.12 runs on macOS.
The job is `continue-on-error: false` so release gates are enforced.

### M4: README + docs macOS install guide

A new "macOS" section in `README.md` covers: `pip install rdc-cli`, remote replay workflow
(`rdc connect`, `rdc replay`), and an optional local build note pointing to
`build_renderdoc.py`. No new doc pages; README only.

### M5: `is_pid_alive()` macOS optimization (`_platform.py`)

On darwin, fall back from `/proc/{pid}/cmdline` (Linux-only) to
`subprocess.check_output(["ps", "-p", str(pid), "-o", "command="])`, preserving the
command-name tag check that the kill-signal-only path loses. Timeout set to 1 s; any
`CalledProcessError` or `TimeoutExpired` returns `False`.

## Out of Scope

- macOS local GPU capture (not supported by upstream RenderDoc).
- Arm64 native wheel distribution / PyPI platform tags.
- macOS full CI on every push/PR (cost-prohibitive).
- Lavapipe or software-renderer GPU tests on macOS.

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Homebrew path layout changes in future RenderDoc formula | Low | Medium | Paths configurable via `RENDERDOC_PYTHON_PATH` env override |
| `macos-latest` runner image switches arch (ARM vs Intel) | Medium | Low | Paths cover both; M1 paths checked first |
| `ps` output format differs across macOS versions | Low | Low | Wrap in try/except; degrade to kill-only on error |
| CI minutes budget spike on accidental `workflow_dispatch` | Low | Medium | Matrix restricted; document in CI comments |
| `xcode-select` present but Command Line Tools incomplete | Low | Low | Doctor check reports warning, not hard failure |
