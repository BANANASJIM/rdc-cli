# Phase W2: Tasks

## Prerequisites

- [x] Phase W1 merged (PR #124 -- `src/rdc/_platform.py` exists)
- [x] OpenSpec reviewed and approved by Jim

## Implementation Tasks

### T1 -- Create `scripts/build_renderdoc.py`

File: `scripts/build_renderdoc.py`

Implement in this order (each function is independently testable):

1. Constants block at module top:
   ```python
   RDOC_TAG = "v1.41"
   SWIG_URL = "https://github.com/baldurk/swig/archive/renderdoc-modified-7.zip"
   SWIG_SHA256 = "9d7e5013ada6c42ec95ab167a34db52c1cc8c09b89c8e9373631b1f10596c648"
   SWIG_SUBDIR = "swig-renderdoc-modified-7"
   ```

2. `_platform() -> str` -- returns `"linux"`, `"macos"`, or `"windows"`

3. `default_install_dir() -> Path` -- `~/.local/renderdoc` or `%LOCALAPPDATA%\renderdoc`

4. `check_prerequisites(plat: str) -> None` -- verifies required tools per platform

5. `clone_renderdoc(build_dir: Path) -> None` -- idempotent `git clone --depth 1 --branch RDOC_TAG`

6. `download_swig(build_dir: Path) -> None` -- idempotent download + SHA256 verify + unzip + rename

7. `strip_lto(env: dict) -> dict` -- removes `-flto=auto` from `CFLAGS`/`CXXFLAGS`/`LDFLAGS`

8. `configure_build(build_dir, swig_dir, plat) -> None` -- cmake configure; strips LTO on ALL Linux

9. `run_build(build_dir, plat, jobs) -> None` -- `cmake --build` with platform-specific parallelism

10. `copy_artifacts(build_dir, install_dir, plat) -> None` -- copies platform-specific artifacts; macOS `.dylib` fallback

11. `main(argv) -> None` -- `argparse` entry point; short-circuits if artifacts already present

Constraints:
- stdlib only (no third-party imports)
- Python 3.10+ syntax
- No `print()` -- use `sys.stdout.write()`
- Use `subprocess.run(..., check=True)` throughout

### T2 -- Add deprecation notices to bash scripts

File: `scripts/build-renderdoc.sh`, line 2 (after shebang):
```bash
# DEPRECATED: use scripts/build_renderdoc.py instead.
# Kept for curl-pipe users on systems without Python 3.10+.
```

File: `scripts/setup-renderdoc.sh`, line 2 (after shebang):
```bash
# DEPRECATED: use scripts/build_renderdoc.py instead.
# Kept for curl-pipe users on systems without Python 3.10+.
```

### T3 -- Update `pixi.toml`

Replace the `setup-renderdoc` task:

```toml
setup-renderdoc = "python scripts/build_renderdoc.py .local/renderdoc --build-dir .local/renderdoc-build"
```

### T4 -- SKIPPED (moved to W3)

`_platform.py` Windows stubs implementation deferred to Phase W3 per review.

## Testing Tasks

### T5 -- Write `tests/unit/test_build_renderdoc.py`

Cover all test cases from `test-plan.md`. Target: full branch coverage of `scripts/build_renderdoc.py`.

### T6 -- Scaffold `tests/integration/test_build_renderdoc_integration.py`

Single skipped test function. No CI execution.

## Documentation Tasks

### T7 -- Archive OpenSpec (post-merge)

After PR merge: `mv openspec/changes/2026-02-23-phase-w2-build-script openspec/changes/archive/`
