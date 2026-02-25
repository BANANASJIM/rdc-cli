# Test Plan — B43 & B44 Fixes

## Scope

1. `scripts/build_renderdoc.py` and `pixi run setup-renderdoc` on macOS (both arm64 and x86_64).
2. Split-mode capture and remote commands routed through JSON-RPC when `pid == 0`.

## Test Matrix

| ID | Area | Scenario | Expected |
|----|------|----------|----------|
| T1 | B43 | Fresh macOS pixi env (`pixi run sync` + `pixi run setup-renderdoc`) | Command succeeds without manual Homebrew installs; build artifacts copied to `.local/renderdoc`. |
| T2 | B43 | Remove `cmake` from PATH and run script | Script exits with `ERROR: missing required tools: cmake` before doing work, referencing pixi dependency. |
| T3 | B43 | Assert extracted SWIG `custom_swig/autogen.sh` is executable | `stat` shows `+x` bit set; no exit 126. |
| T4 | B43 | Run script twice | Second run prints "renderdoc already exists" guard; no rebuild. |
| T5 | B44 | Local mode capture (`pid>0`) | Behavior unchanged; CLI uses local renderdoc and passes tests. |
| T6 | B44 | Split mode capture: `rdc open --connect ...`, run `rdc capture -- json` | CLI sends `capture_run` RPC, daemon performs capture; JSON output contains path, no ImportError on client. |
| T7 | B44 | Split mode `rdc remote list` / `remote capture` | Commands succeed via RPC; daemon handles renderdoc imports. |
| T8 | B44 | Split mode `rdc capture --trigger` | Trigger/inject path works; CLI receives `ident` info serialized from daemon result. |
| T9 | B44 | Split mode errors (e.g., target missing) | Daemon error propagates as single stderr line / JSON error object; no double-printing. |
| T10 | B44 | Regression: local `rdc remote capture` still works (`pid>0`) | CLI uses current path; ensures RPC path not required locally. |
| T11 | B44 | Split mode `rdc remote connect` (pid==0 client invoking CLI command) | CLI routes through daemon RPC (no local renderdoc import), saved state/JSON output still match current format, and command succeeds against existing remote daemon. |

## Automation

- Extend unit tests:
  - Mock split session in `tests/unit/test_capture.py` verifying RPC invocation when `pid == 0`.
  - Extend `tests/unit/test_remote_commands.py` for split mode path.
  - Add tests covering new handlers (serialize `CaptureResult`).
- Add integration smoke test for `scripts/build_renderdoc.py` using GitHub Actions macOS runner once feasible (optional; manual verification acceptable for now but include instructions in tasks).
