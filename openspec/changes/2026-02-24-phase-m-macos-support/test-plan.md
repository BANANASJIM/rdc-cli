# Phase M: macOS Support — Test Plan

## Scope

**In:** `_platform.py` darwin paths, `doctor.py` macOS checks, `_platform.is_pid_alive()` darwin branch.
**Out:** CI YAML validation (manual review), README/docs changes (M3, M4 — no unit tests).

## Test Matrix

| Layer | File | New Cases |
|-------|------|-----------|
| Unit | `tests/unit/test_platform.py` | 10 |
| Unit | `tests/unit/test_doctor.py` | 7 |
| **Total** | | **17** |

## Test Cases

### M1: Homebrew search paths (`_platform.py`)

| ID | Description |
|----|-------------|
| M1-01 | `renderdoc_search_paths()` on darwin includes `/opt/homebrew/opt/renderdoc/lib` |
| M1-02 | `renderdoc_search_paths()` on darwin includes `/usr/local/opt/renderdoc/lib` |
| M1-03 | `renderdoc_search_paths()` on darwin includes `~/.local/renderdoc` (expanded) |
| M1-04 | `renderdoccmd_search_paths()` on darwin includes `/opt/homebrew/bin/renderdoccmd` (ARM) |
| M1-05 | `renderdoccmd_search_paths()` on darwin includes `/usr/local/bin/renderdoccmd` (Intel) |
| M1-06 | `renderdoc_search_paths()` on linux excludes Homebrew paths (no regression) |

### M2: Doctor macOS checks (`doctor.py`)

| ID | Description |
|----|-------------|
| M2-01 | `_check_mac_xcode_cli()` returns OK when `xcode-select -p` exits 0 |
| M2-02 | `_check_mac_xcode_cli()` returns FAIL when `xcode-select -p` exits non-zero |
| M2-03 | `_check_mac_homebrew()` returns OK when `brew --version` succeeds |
| M2-04 | `_check_mac_homebrew()` returns FAIL when `shutil.which("brew")` returns None |
| M2-05 | `_check_mac_renderdoc_dylib()` returns OK when a `.dylib` or `.so` exists at any search path |
| M2-06 | `_check_mac_renderdoc_dylib()` returns FAIL when no library found at any path |
| M2-07 | `_make_build_hint("darwin")` output contains Homebrew install instructions |

### M3: CI macOS matrix

No unit tests — validate YAML structure manually during PR review.

### M4: README/docs

No unit tests — documentation only.

### M5: `is_pid_alive()` darwin optimization (`_platform.py`)

| ID | Description |
|----|-------------|
| M5-01 | On darwin, `is_pid_alive(pid, tag)` returns True when `ps` output contains tag |
| M5-02 | On darwin, `is_pid_alive(pid, tag)` returns False when `ps` output does not contain tag |
| M5-03 | On darwin, `is_pid_alive(pid, tag)` falls back to kill-check when `ps` raises `subprocess.SubprocessError` |
| M5-04 | On linux, `is_pid_alive()` behavior unchanged (no regression) |

## Coverage Target

Existing coverage maintained (≥95%). All 17 new cases must pass; no GPU fixtures required.
