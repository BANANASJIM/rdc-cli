# Proposal: renderdoc-build-helper

**Date:** 2026-02-22
**Phase:** Post-5 / release-prep maintenance
**Status:** Draft

---

## Problem Statement

Users who install `rdc-cli` from PyPI via `pipx install rdc-cli` have no renderdoc Python module and no clear path to obtaining one.

Three specific pain points exist today:

1. `rdc doctor` prints a raw 5-line cmake snippet (`_RENDERDOC_BUILD_HINT`) to stderr when renderdoc is missing. It has no progress output, no error recovery, and no link to further docs. A first-time user does not know about the custom SWIG fork, LTO incompatibility on Arch, or the `RENDERDOC_PYTHON_PATH` convention.

2. `scripts/setup-renderdoc.sh` already encodes the full correct build logic (custom SWIG URL, LTO stripping, Ninja, artifact copy to `.local/renderdoc`) but is tightly coupled to the pixi dev environment (`pixi run setup-renderdoc`). An end-user who installed via PyPI has no pixi and cannot use it.

3. `README.md` "Setup renderdoc" section repeats the same raw cmake commands without mentioning the SWIG fork, LTO issue, or the existence of `rdc doctor`. A user who hits a build failure has no guidance.

---

## Proposed Solution

### Component 1: `scripts/build-renderdoc.sh` — standalone user-facing build script

A new script at `scripts/build-renderdoc.sh` that:

- Targets end-users who installed `rdc-cli` from PyPI (no pixi, no dev env).
- Single supported invocation: `bash <(curl -fsSL <url>) [INSTALL_DIR]` (process substitution preserves positional args; `curl | bash` pipe form does not and is avoided).
- Security note: piping remote scripts is an accepted pattern (same as rustup, nvm); users who prefer can `curl -fsSL <url> -o build-renderdoc.sh && bash build-renderdoc.sh`.
- `INSTALL_DIR` defaults to `$HOME/.local/renderdoc`; prints the export line to add to shell profile.
- Build steps (derived from `setup-renderdoc.sh` but self-contained):
  1. Check required tools: `cmake`, `ninja`, `git`, `curl`, `unzip`, `python3` — exit with clear message listing what is missing.
  2. Clone `renderdoc v1.41` with `--depth 1` into a temp dir (`mktemp -d`).
  3. Download the baldurk SWIG fork zip into the same temp dir.
  4. Strip `-flto=auto` from `CFLAGS`/`CXXFLAGS`/`LDFLAGS` (required for SWIG bindings).
  5. Run cmake + build with flags matching `setup-renderdoc.sh` and `PKGBUILD`.
  6. Copy `renderdoc.so` + `librenderdoc.so` to `INSTALL_DIR`.
  7. Clean up temp dir on exit (trap).
  8. Print `export RENDERDOC_PYTHON_PATH=<INSTALL_DIR>` and instruct user to re-run `rdc doctor`.
- Idempotent: if `$INSTALL_DIR/renderdoc.so` already exists, print skip message and exit 0.
- Works on plain Debian/Ubuntu/Arch user install (no pixi required).

This is distinct from `setup-renderdoc.sh` which remains the pixi dev-environment script.

### Component 2: `rdc doctor` hint enhancement

Replace `_RENDERDOC_BUILD_HINT` in `src/rdc/commands/doctor.py` with a three-line hint:

```
  renderdoc Python module not found. To build it:
    bash <(curl -fsSL https://raw.githubusercontent.com/BANANASJIM/rdc-cli/master/scripts/build-renderdoc.sh)
    export RENDERDOC_PYTHON_PATH=$HOME/.local/renderdoc
  Full instructions: https://bananasjim.github.io/rdc-cli/
```

No logic change to `run_doctor()` or any `CheckResult`.

### Component 3: `README.md` "Setup renderdoc" section update

Replace the current raw cmake block with:

1. A note that renderdoc is a native C++ library (~150 MB), not included in the PyPI package.
2. The one-liner script invocation.
3. A reference to `rdc doctor` to verify after setup.

---

## Non-Goals

- Distributing a pre-built renderdoc binary.
- macOS support in `build-renderdoc.sh` (dev-host only; covered by `setup-renderdoc.sh`).
- Adding a new `rdc install-renderdoc` CLI command.
- Modifying the docs Astro site structure.

---

## Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| Script URL dead before docs CI publishes | Use raw GitHub URL initially |
| renderdoc v1.42+ breaks cmake flags | Pin `RDOC_TAG="v1.41"` explicitly; bump as separate PR |
| LTO stripping no-ops on distros without `CFLAGS` | `${CFLAGS:-}` default handles this |
| User Python version mismatch | Print warning: "ensure RENDERDOC_PYTHON_PATH points to .so built with $(python3 --version)" |

---

## Acceptance Criteria

1. `scripts/build-renderdoc.sh` is executable and passes `shellcheck` with no errors.
2. Running the script on a clean Ubuntu 22.04 environment produces `renderdoc.so` and `librenderdoc.so` in `INSTALL_DIR`.
3. Running the script a second time exits 0 with a skip message (idempotent).
4. `rdc doctor` with missing renderdoc prints the new hint referencing script URL and docs URL.
5. `README.md` contains: missing-from-PyPI note, one-liner, and `rdc doctor` verification step.
6. `pixi run check` passes with no regressions.
