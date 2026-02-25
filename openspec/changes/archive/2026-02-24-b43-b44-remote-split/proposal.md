# Fix B43 (setup-renderdoc deps) and B44 (Split capture)

## Summary

B43: `pixi run setup-renderdoc` fails on macOS because the build script assumes `cmake`, `ninja`, and GNU autotools are already installed and because the SWIG staging directory is not prepared correctly. `custom_swig/autogen.sh` also lacks executable permissions, so even after installing dependencies manually the script stops with exit 126.

B44: In Split mode (`rdc open --connect`), Tier-1 CLI commands `rdc capture` and `rdc remote *` still import the local `renderdoc` module. On thin clients (macOS laptops) where RenderDoc is not installed, these commands crash with `ImportError`/SIGSEGV even though the daemon (Tier-2) already hosts renderdoc. Split mode is supposed to be fully RPC-driven.

## Motivation

Both bugs block thin-client workflows:

- B43 prevents macOS developers from bootstrapping RenderDoc inside pixi unless they manually install cmake/ninja/autotools and patch the SWIG directory by hand. This breaks the "single command dev setup" assumption documented in the OpenSpec for the pixi workflow.
- B44 violates the Split-mode guarantee spelled out in `设计/远程Split模式.md`: Tier-1 CLI must be renderdoc-independent. As soon as a user connects to a remote daemon, every capture/remote command should go through JSON-RPC; importing renderdoc locally defeats the purpose and crashes on machines without RenderDoc.

---

## Bug Analysis & Proposed Fixes

### B43: macOS `setup-renderdoc` missing build dependencies (P2)

#### Current behavior

1. `scripts/build_renderdoc.py` checks for `cmake`, `git`, and (on non-Windows) `ninja`. It does not check `autoconf`, `automake`, `libtool`, or `pkg-config` even though RenderDoc's custom SWIG fork needs them.
2. `pixi run setup-renderdoc` does not ensure those packages exist in the pixi env. Users must install `brew install cmake ninja automake autoconf libtool pkg-config` manually, defeating reproducibility.
3. The script downloads `renderdoc-swig` but expects a `renderdoc-swig` directory with custom symlink layout. On macOS the extracted `custom_swig` tree lacks executable bits (`autogen.sh`), so invoking it fails with exit 126.
4. The legacy shell script `scripts/setup-renderdoc.sh` handled some of these quirks, but the Python port regressed them.

#### Proposed fix

1. **pixi Dependencies:** Add macOS-specific dependencies in `pixi.toml` under `[target.osx-64.dependencies]` and `[target.osx-arm64.dependencies]` (pixi supports target-specific sections). Required packages: `cmake`, `ninja`, `autoconf`, `automake`, `libtool`, `pkg-config`, `m4`. Keep Linux unaffected.
2. **Script prerequisite checks:** Extend `check_prerequisites()` to require the above tools on macOS. Emit actionable errors that point users to `pixi run sync` rather than Homebrew.
3. **SWIG staging:** Mirror the shell script's logic—after extracting `SWIG_SUBDIR`, copy or symlink its `custom_swig` into `renderdoc/custom_swig` before running cmake. Ensure `_safe_extractall` preserves file modes so `autogen.sh` is executable; if not, explicitly `chmod +x` the script.
4. **Autotools bootstrap:** Instead of calling `autogen.sh` directly, run `autoreconf -fi` inside `renderdoc-swig/Lib/renderdoc` so missing execute bits are irrelevant. `autoreconf` uses the installed autotools.
5. **Smoke test hook:** Teach `scripts/build_renderdoc.py` to run a lightweight `cmake --version` and `ninja --version` command after `check_prerequisites()` to prove pixi supplied them (fail fast).

### B44: Split-mode capture still imports local renderdoc (P1)

#### Current behavior

- `src/rdc/commands/capture.py` directly calls `find_renderdoc()` and `execute_and_capture()` in all cases. If `find_renderdoc()` returns None it falls back to spawning `renderdoccmd`, but that still requires RenderDoc to be installed locally.
- `src/rdc/commands/remote.py` uses `require_renderdoc()` to load the module for every subcommand, ignoring whether an active session exists. Split clients (pid==0) have no local renderdoc, so `require_renderdoc()` exits with error.
- JSON-RPC already covers replay operations once a session is open, but capture/remote commands bypass the daemon entirely.

#### Proposed fix

1. **Session-aware routing:** Introduce a helper (`is_split_session()` or reuse `require_session()`) that reports whether the current session has `pid == 0`. If true, `rdc capture` should refuse to use local renderdoc and instead send an RPC to the daemon to request a capture.
2. **Daemon handlers:** Add new JSON-RPC methods (e.g., `capture_run` and `remote_capture_run`) handled inside the daemon process. These handlers will wrap the existing Python capture logic (`execute_and_capture` and `remote_capture`) because the daemon already imports renderdoc.
3. **CLI integration:**
   - Update `capture_cmd`: when not connected to a session, behavior stays as-is (local capture). When a split session is active, send `capture_run` RPC with the CLI options and let the daemon handle both launching and target control.
   - Update `remote_*` commands: if `pid == 0`, they must call RPCs on the daemon rather than `require_renderdoc()`. For local sessions (pid>0) they can still call renderdoc directly since the daemon is local and shareable.
4. **Protocol definition:** Document the new methods in `设计/交互模式.md` and ensure parameters mirror existing CLI flags. Results can reuse `CaptureResult` serialization (already dataclass serializable).
5. **Error handling:** The CLI should display daemon errors verbatim; JSON mode should continue returning structured responses. Ensure `--json` works in split mode.
6. **Security guardrails:** The daemon already authenticates via `_token`. No new networking surface is exposed.

---

## Risk Assessment

- **B43 fixes** are low risk: they add dependency declarations and sanity checks, but the script's core logic remains the same. Explicit tool installation improves determinism. Using `autoreconf` is standard for SWIG builds and eliminates the permission issue.
- **B44 fixes** touch CLI/daemon protocol, so medium risk. However, Split-mode already depends on JSON-RPC, and the new handlers reuse proven capture functions. Strict feature parity tests (local vs split) mitigate regressions.

## Alternatives Considered

- **For B43:** Bundling prebuilt renderdoc artifacts for macOS. Rejected because RenderDoc releases are GPL-incompatible for redistribution within this project; building from source remains required.
- **For B44:** Running renderdoc via a background helper binary on the thin client even in split mode. Rejected because it contradicts the architecture doc; users explicitly requested renderdoc-free clients.
