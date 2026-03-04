# W6: Windows Bugfix Batch

## Motivation

Windows VM retest on `master@491531b` (2026-03-04) found 4 issues:

| Bug | Severity | Summary |
|-----|----------|---------|
| BUG-2 | HIGH | `rdc capture` fails with relative executable path |
| BUG-1 | HIGH | Git Bash MSYS path conversion breaks VFS commands |
| BUG-4 | LOW | pytest tmp_path PermissionError blocks 24% of Windows unit tests |
| BUG-3 | MEDIUM | Capture injection timeout — investigation aid only |

## Design

### BUG-2: Resolve executable path

`rd.ExecuteAndInject()` requires an absolute path on Windows. The CLI passes `ctx.args[0]` unchanged.

**Fix**: In `capture_core.py:execute_and_capture()`, resolve `app` to an absolute path before calling `ExecuteAndInject`. Resolution strategy depends on the form of `app`:
- **Bare executable name** (no directory separator, e.g. `vulkan_samples.exe`): use `shutil.which()` for PATH lookup, keeping the original name if not found.
- **Relative path** (contains separator but not absolute, e.g. `bin/app`): resolve against `workdir` if provided, otherwise against CWD.
- **Absolute path**: passed through unchanged.

This is the single point through which all callers (CLI direct, split mode handler, remote) pass.

### BUG-1: MSYS path recovery

Git Bash (MSYS2) converts any argument starting with `/` to a Windows path like `C:/Program Files/Git/...`. This happens *before* the Python process receives the argument — we cannot prevent it.

**Fix**: Add a `_recover_msys_path()` helper invoked inside VFS command handlers (`ls`, `cat`, `tree`) that detects MSYS-mangled paths and strips the Windows prefix. Detection logic:
1. If path already starts with `/`, return unchanged.
2. If path matches `<drive>:/.../Git|msys64|msys32|cygwin64|cygwin/...` (regex token match), strip the matched prefix.
3. Fallback: check `EXEPATH` env var (set by Git Bash), use its parent as root with path-separator boundary check (`norm == root or norm.startswith(root + "/")`), and strip that prefix.

### BUG-4: pytest tmp_path retention

pytest's `tmp_path` cleanup fails on Windows when directory permissions are restrictive.

**Fix**: Set `tmp_path_retention_policy = "none"` in `pyproject.toml` `[tool.pytest.ini_options]`.

### BUG-3: Diagnostic logging

Capture injection succeeds but `NewCapture` message never arrives. Cause unclear.

**Fix**: Add `logging.debug()` calls in `run_target_control_loop()` to log each received message type. Aids future debugging on Windows VM.

## Risks

- MSYS detection heuristic might false-positive on paths that legitimately contain "Program Files/Git"
- `tmp_path_retention_policy = "none"` means pytest never cleans up temp dirs (acceptable — CI runners do their own cleanup)
