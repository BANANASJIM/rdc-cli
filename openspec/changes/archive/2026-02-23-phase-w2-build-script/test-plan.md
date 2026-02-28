# Phase W2: Test Plan

## Unit Tests

File: `tests/unit/test_build_renderdoc.py`

All tests use `unittest.mock` to avoid network and filesystem side-effects. The script is imported as a module after adding `scripts/` to `sys.path`.

### Platform detection

| Test | Description |
|------|-------------|
| `test_platform_linux` | `sys.platform = "linux"` -> `_platform()` returns `"linux"` |
| `test_platform_macos` | `sys.platform = "darwin"` -> `_platform()` returns `"macos"` |
| `test_platform_windows` | `sys.platform = "win32"` -> `_platform()` returns `"windows"` |

### Default install dir

| Test | Description |
|------|-------------|
| `test_default_install_dir_linux` | `_platform()` mocked to `"linux"` -> `Path.home() / ".local/renderdoc"` |
| `test_default_install_dir_macos` | `_platform()` mocked to `"macos"` -> `Path.home() / ".local/renderdoc"` |
| `test_default_install_dir_windows` | `_platform()` mocked to `"windows"`, `LOCALAPPDATA` set -> `Path(LOCALAPPDATA) / "renderdoc"` |
| `test_default_install_dir_windows_no_localappdata` | `LOCALAPPDATA` unset -> falls back to `Path.home() / "renderdoc"` |

### Prerequisite checking

| Test | Description |
|------|-------------|
| `test_check_prerequisites_all_present_linux` | All tools found -> no exception |
| `test_check_prerequisites_missing_cmake` | `cmake` not in PATH -> `SystemExit(1)` |
| `test_check_prerequisites_missing_ninja_linux` | `ninja` missing on Linux -> `SystemExit(1)` |
| `test_check_prerequisites_windows_no_ninja` | Windows does not require ninja -> no error |
| `test_check_prerequisites_windows_vswhere_empty` | `vswhere.exe` returns empty -> `SystemExit(1)` |
| `test_check_prerequisites_windows_vswhere_missing` | `vswhere.exe` not found -> `SystemExit(1)` |

### Clone renderdoc

| Test | Description |
|------|-------------|
| `test_clone_renderdoc_fresh` | Target dir absent -> `git clone` called with `--depth 1 --branch v1.41` |
| `test_clone_renderdoc_idempotent` | Target dir exists -> `git clone` not called |

### SWIG download

| Test | Description |
|------|-------------|
| `test_download_swig_fresh_ok` | Dir absent, SHA256 matches -> extracted and renamed |
| `test_download_swig_idempotent` | `renderdoc-swig` exists -> download skipped |
| `test_download_swig_sha256_mismatch` | Hash differs -> `SystemExit(1)`, archive deleted |

### LTO flag stripping

| Test | Description |
|------|-------------|
| `test_strip_lto_removes_flag` | env has `-flto=auto` in all three vars -> stripped |
| `test_strip_lto_no_flags_present` | No `-flto=auto` -> no change |
| `test_strip_lto_does_not_mutate_original` | Original dict unchanged |

### CMake configuration

| Test | Description |
|------|-------------|
| `test_configure_linux_uses_ninja` | Linux -> `-G Ninja` |
| `test_configure_macos_uses_ninja` | macOS -> `-G Ninja` |
| `test_configure_windows_uses_vs` | Windows -> `-G "Visual Studio 17 2022" -A x64` |
| `test_configure_common_flags` | All -> `-DENABLE_PYRENDERDOC=ON` etc. present |
| `test_configure_swig_package_path` | `-DRENDERDOC_SWIG_PACKAGE` set correctly |
| `test_configure_linux_strips_lto` | Linux env `-flto=auto` stripped |

### Build

| Test | Description |
|------|-------------|
| `test_run_build_parallel_flag_linux` | Linux -> `-j N` |
| `test_run_build_parallel_flag_windows` | Windows -> `/m:N` after `--` |

### Artifact copy

| Test | Description |
|------|-------------|
| `test_copy_artifacts_linux` | Linux -> copies `renderdoc.so` and `librenderdoc.so` |
| `test_copy_artifacts_macos` | macOS -> same as Linux |
| `test_copy_artifacts_macos_dylib_fallback` | macOS `.dylib` fallback works |
| `test_copy_artifacts_windows` | Windows -> copies `.pyd` and `.dll` |
| `test_copy_artifacts_missing_source` | Missing artifact -> `SystemExit(1)` |

### CLI argument parsing

| Test | Description |
|------|-------------|
| `test_main_default_install_dir` | No args -> `default_install_dir()` used |
| `test_main_custom_install_dir` | Positional arg -> used as install dir |
| `test_main_custom_build_dir` | `--build-dir` -> passed through |
| `test_main_idempotent_skip` | Artifacts present -> all build steps skipped |

## Integration Tests

File: `tests/integration/test_build_renderdoc_integration.py`

Single `@pytest.mark.skip` test. No CI execution. Manual verification only.

## Manual Verification

### Linux (primary target)

1. `rm -rf ~/.local/renderdoc ~/.local/renderdoc-build`
2. `python scripts/build_renderdoc.py`
3. Confirm `~/.local/renderdoc/renderdoc.so` and `librenderdoc.so` present
4. Run again: must print "already exists" and exit without rebuilding

### Linux (pixi task path)

1. `rm -rf .local/renderdoc .local/renderdoc-build`
2. `pixi run setup-renderdoc`
3. Confirm `.local/renderdoc/renderdoc.so` exists
