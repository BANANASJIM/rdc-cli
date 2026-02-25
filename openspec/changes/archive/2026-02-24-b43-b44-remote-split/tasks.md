# Tasks — B43 & B44

## B43: setup-renderdoc macOS dependencies

1. Update `pixi.toml` to add macOS-specific dependencies (`cmake`, `ninja`, `autoconf`, `automake`, `libtool`, `pkg-config`, `m4`).
2. Extend `scripts/build_renderdoc.py`:
   - Require the above tools in `check_prerequisites()` on macOS.
   - Run `cmake --version` and `ninja --version` after prerequisite checks.
   - Ensure the SWIG archive extraction sets executable bits; fallback to `Path(...).chmod(0o755)` for `custom_swig/autogen.sh`.
   - Use `subprocess.run(["autoreconf", "-fi"], cwd=swig_dir / "custom_swig")` before cmake configure.
3. Document the new behavior in script help text (mention pixi-managed deps).
4. Manual validation on macOS arm64 (and x86_64 if available): run `pixi run sync` then `pixi run setup-renderdoc` from a clean env; capture logs.

## B44: Split-mode capture routing

1. Add helper to detect active split session (pid==0) in `rdc.commands._helpers` or a new module.
2. Define new JSON-RPC methods `capture_run` and `remote_capture_run` in `设计/交互模式.md` (SSoT) and implement handlers under `src/rdc/handlers/capture.py` or new handler module.
3. Serialize `CaptureResult` to dict for RPC responses (add helper if needed).
4. Update CLI commands:
   - `rdc capture`: when split session active, send RPC; support `--json`, `--trigger`, etc.
   - `rdc remote connect/list/capture`: when split session active, call RPC wrappers instead of `require_renderdoc()`.
5. Extend `rdc.remote_core` or new service functions used by daemon handlers; ensure they run within daemon context.
6. Update tests (`tests/unit`) to cover split and local modes.
7. Manual verification: start daemon on Linux, connect from macOS, run capture/remote commands (document results in test report).
