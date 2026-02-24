# Phase W2: Cross-Platform Build Script

## Motivation

Two near-identical bash scripts currently handle the renderdoc build:

- `scripts/build-renderdoc.sh` — standalone, curl-pipe install pattern, installs to `~/.local/renderdoc/`
- `scripts/setup-renderdoc.sh` — pixi dev env, installs to `.local/renderdoc/` (relative to repo root)

The differences are cosmetic: output path and whether SHA256 verification is performed. Both will break on Windows (no bash, no `nproc`, no `.so` artifacts). Phase W1 added `src/rdc/_platform.py`; W2 extends platform-awareness to the build tooling by replacing both scripts with a single Python script.

## Scope

- New file: `scripts/build_renderdoc.py` (stdlib only, Python 3.10+)
- `pixi.toml`: update `setup-renderdoc` task to call the Python script
- `scripts/build-renderdoc.sh` and `scripts/setup-renderdoc.sh`: retained, marked deprecated
- `scripts/ensure-renderdoc.sh`: unchanged (worktree symlink helper, bash-only is fine)

## Design

### Script Architecture

The script is a single self-contained Python file with no third-party imports. It is structured as a sequence of functions called from `main()`:

```
main()
  check_prerequisites()
  clone_renderdoc()
  download_swig()
  configure_build()
  run_build()
  copy_artifacts()
```

Top-level constants mirror those in the bash scripts:

```python
RDOC_TAG = "v1.41"
SWIG_URL = "https://github.com/baldurk/swig/archive/renderdoc-modified-7.zip"
SWIG_SHA256 = "9d7e5013ada6c42ec95ab167a34db52c1cc8c09b89c8e9373631b1f10596c648"
SWIG_SUBDIR = "swig-renderdoc-modified-7"
```

`main()` accepts an optional positional argument `INSTALL_DIR`; if omitted, `default_install_dir()` is used. `--build-dir` is also accepted to override the build cache location.

### Platform Detection

A private helper `_platform()` returns one of `"linux"`, `"macos"`, `"windows"`:

```python
import sys

def _platform() -> str:
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "linux"
```

### Build Flow

**`check_prerequisites()`**

Required tools per platform:

| Tool | Linux | macOS | Windows |
|------|-------|-------|---------|
| `cmake` | yes | yes | yes |
| `git` | yes | yes | yes |
| `python3` / `python` | yes | yes | yes |
| `ninja` | yes | yes | no |
| `vswhere.exe` | no | no | yes |

On Windows, the function also verifies Visual Studio Build Tools are present by running `vswhere -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -format value -property installationPath` and confirming a non-empty result.

**`clone_renderdoc(build_dir: Path)`**

Idempotent: skips if `build_dir / "renderdoc"` exists. Uses `git clone --depth 1 --branch RDOC_TAG`.

**`download_swig(build_dir: Path)`**

Idempotent: skips if `build_dir / "renderdoc-swig"` exists.

Uses `urllib.request.urlretrieve` (stdlib). After download, verifies SHA256 with `hashlib`. Extracts with `zipfile.ZipFile`. Raises `SystemExit(1)` on checksum mismatch and deletes the corrupt archive.

**`configure_build(build_dir: Path)`**

CMake flags common to all platforms:

```
-DCMAKE_BUILD_TYPE=Release
-DENABLE_PYRENDERDOC=ON
-DENABLE_QRENDERDOC=OFF
-DENABLE_RENDERDOCCMD=OFF
-DENABLE_GL=OFF
-DENABLE_GLES=OFF
-DENABLE_VULKAN=ON
-DRENDERDOC_SWIG_PACKAGE=<build_dir>/renderdoc-swig
```

Generator selection:

- Linux/macOS: `-G Ninja`
- Windows: `-G "Visual Studio 17 2022" -A x64`

On ALL Linux, strips `-flto=auto` from `CFLAGS`, `CXXFLAGS`, `LDFLAGS` in the environment passed to `subprocess.run`.

**`run_build(build_dir: Path)`**

Runs `cmake --build <build_dir>/renderdoc/build`. Uses `os.cpu_count()` for parallelism.

On Linux/macOS: `-j <n>`. On Windows: `--` `/m:<n>` (MSBuild parallel flag).

**`copy_artifacts(build_dir: Path, out_dir: Path)`**

Artifact paths by platform:

| Platform | Source | Destination |
|----------|--------|-------------|
| Linux | `build/lib/renderdoc.so`, `build/lib/librenderdoc.so` | `out_dir/` |
| macOS | `build/lib/renderdoc.so`, `build/lib/librenderdoc.so` (or `.dylib`) | `out_dir/` |
| Windows | `build/Release/renderdoc.pyd`, `build/Release/renderdoc.dll` | `out_dir/` |

Uses `shutil.copy2`.

### Output Paths

`default_install_dir()` returns the renderdoc artifact directory:

```python
def default_install_dir() -> Path:
    if _platform() == "windows":
        base = os.environ.get("LOCALAPPDATA", str(Path.home()))
        return Path(base) / "renderdoc"
    return Path.home() / ".local" / "renderdoc"
```

The build cache is always `<install_dir_parent>/renderdoc-build`, or overridden with `--build-dir`.

### Backward Compatibility

`scripts/build-renderdoc.sh` and `scripts/setup-renderdoc.sh` are retained verbatim. A deprecation notice comment is prepended at the top of each:

```bash
# DEPRECATED: use scripts/build_renderdoc.py instead.
# Kept for curl-pipe users on systems without Python 3.10+.
```

The `pixi.toml` `setup-renderdoc` task is updated:

```toml
setup-renderdoc = "python scripts/build_renderdoc.py .local/renderdoc --build-dir .local/renderdoc-build"
```

## Non-Goals

- Building renderdoc for non-Python use (GUI, renderdoccmd)
- Supporting renderdoc versions other than v1.41
- Automatic Python version detection for the SWIG binding target
- Package manager integration (apt, brew, winget)
- `ensure-renderdoc.sh` replacement (worktree symlink logic stays bash)
- Modifying `src/rdc/_platform.py` (Windows stubs deferred to W3)

## Risks

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Windows build untested in CI | Medium | Manual verification section in test-plan; CI matrix is Linux-only for now |
| SWIG ZIP layout changes across renderdoc versions | Low | SHA256 pin + explicit `SWIG_SUBDIR` constant |
| `urllib.request` slow vs `curl` for large archives | Low | Progress callback via `reporthook` in `urlretrieve` |
| Visual Studio version drift (2022 to future) | Low | Document assumption; add `--vs-version` flag as future option |
| macOS artifact path differs from Linux | Medium | `copy_artifacts` handles `.dylib` fallback for `librenderdoc` |
