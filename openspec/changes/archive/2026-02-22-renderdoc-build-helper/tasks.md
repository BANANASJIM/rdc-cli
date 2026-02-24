# Tasks: renderdoc-build-helper

## Branch
`feat/renderdoc-build-helper`

## Context

`scripts/setup-renderdoc.sh` serves the dev workflow (installs to `.local/renderdoc/`, invoked via
`pixi run setup-renderdoc`). The new `scripts/build-renderdoc.sh` is a standalone user-facing script
that requires no pixi: installs to `~/.local/renderdoc/`, verifies SWIG sha256, and prints a
ready-to-use `export` line. The doctor hint and README "Setup renderdoc" section are updated to
reference the new script and docs site.

---

## Phase A — Tests first

- [ ] **A1** Update `tests/unit/test_doctor.py` — `test_doctor_shows_build_hint_when_renderdoc_missing`
  - Change assertion from `"cmake -B build -DENABLE_PYRENDERDOC=ON"` to check for raw GitHub
    script URL (`https://raw.githubusercontent.com/BANANASJIM/rdc-cli/master/scripts/build-renderdoc.sh`) in `result.output`
    (Note: hint is emitted via `click.echo(..., err=True)` but CliRunner mixes stderr into
    `result.output` by default — do NOT use `result.stderr`)
  - Keep `result.exit_code == 1` and `"not found" in result.output` assertions

- [ ] **A2** Add `test_doctor_hint_contains_docs_url` in `tests/unit/test_doctor.py`
  - `from rdc.commands.doctor import _RENDERDOC_BUILD_HINT`
  - Assert `"https://bananasjim.github.io/rdc-cli/"` in `_RENDERDOC_BUILD_HINT`

- [ ] **A3** Run `pixi run test tests/unit/test_doctor.py` — expect A1 and A2 to fail (red phase)

---

## Phase B — Implementation

### B1 — `scripts/build-renderdoc.sh` (new file)

- [ ] **B1-1** Create `scripts/build-renderdoc.sh`:
  - `set -euo pipefail`
  - Constants:
    ```bash
    RDOC_TAG="v1.41"
    SWIG_URL="https://github.com/baldurk/swig/archive/renderdoc-modified-7.zip"
    SWIG_SHA256="9d7e5013ada6c42ec95ab167a34db52c1cc8c09b89c8e9373631b1f10596c648"
    OUT_DIR="${1:-${HOME}/.local/renderdoc}"
    BUILD_DIR="${HOME}/.local/renderdoc-build"
    ```
  - Early-exit guard: if `$OUT_DIR/renderdoc.so` exists, print location and exit 0
  - Clone (idempotent): `git clone --depth 1 --branch "$RDOC_TAG" ... "$BUILD_DIR/renderdoc"`
  - SWIG download + sha256 verify + unzip (idempotent: skip if `$BUILD_DIR/renderdoc-swig` exists)
  - LTO strip (same pattern as `setup-renderdoc.sh`)
  - cmake configure with canonical flags from `aur/PKGBUILD` lines 56-64:
    ```bash
    cmake -B "$BUILD_DIR/renderdoc/build" -S "$BUILD_DIR/renderdoc" -G Ninja \
      -DCMAKE_BUILD_TYPE=Release \
      -DENABLE_PYRENDERDOC=ON \
      -DENABLE_QRENDERDOC=OFF \
      -DENABLE_RENDERDOCCMD=OFF \
      -DENABLE_GL=OFF \
      -DENABLE_GLES=OFF \
      -DENABLE_VULKAN=ON \
      -DRENDERDOC_SWIG_PACKAGE="$BUILD_DIR/renderdoc-swig"
    ```
  - `cmake --build ... -j "$(nproc 2>/dev/null || echo 4)"`
  - Copy `renderdoc.so` + `librenderdoc.so` to `$OUT_DIR/`
  - Print: `export RENDERDOC_PYTHON_PATH="$OUT_DIR"` and `rdc doctor` verification step
  - `chmod +x scripts/build-renderdoc.sh`

### B2 — `src/rdc/commands/doctor.py`

- [ ] **B2-1** Replace `_RENDERDOC_BUILD_HINT` (lines 34-40) with:
  ```python
  _RENDERDOC_BUILD_HINT = """\
    renderdoc is not available on PyPI and must be built from source.
    Quick build script (no pixi required):
      bash <(curl -fsSL https://raw.githubusercontent.com/BANANASJIM/rdc-cli/master/scripts/build-renderdoc.sh)
    Full instructions: https://bananasjim.github.io/rdc-cli/
    Then re-run: rdc doctor"""
  ```

### B3 — `README.md`

- [ ] **B3-1** Insert Prerequisites callout before `## Install` section:
  ```markdown
  > **Prerequisite — renderdoc Python module**
  > `rdc` requires `renderdoc.cpython-*.so`, which is **not available on PyPI**.
  > Build it once with the provided script (requires cmake, ninja, Vulkan headers):
  > ```bash
  > bash <(curl -fsSL https://raw.githubusercontent.com/BANANASJIM/rdc-cli/master/scripts/build-renderdoc.sh)
  > ```
  > Full instructions: <https://bananasjim.github.io/rdc-cli/>
  > AUR users: `yay -S rdc-cli-git` handles this automatically.
  ```

- [ ] **B3-2** Update `## Setup renderdoc` section: replace bare cmake snippet with script one-liner;
  keep "Module discovery order" list and `rdc doctor` verification line unchanged

---

## Phase C — Integration and Verify

- [ ] **C1** `pixi run lint` — zero errors
- [ ] **C2** `pixi run test tests/unit/test_doctor.py` — all tests pass (updated A1, new A2, existing tests)
- [ ] **C3** `pixi run test` (full suite) — zero failures, coverage unchanged
- [ ] **C4** Static script checks:
  ```bash
  bash -n scripts/build-renderdoc.sh
  grep -q 'set -euo pipefail' scripts/build-renderdoc.sh
  grep -q 'v1\.41' scripts/build-renderdoc.sh
  grep -q '9d7e5013' scripts/build-renderdoc.sh
  grep -q 'RENDERDOC_PYTHON_PATH' scripts/build-renderdoc.sh
  ```
- [ ] **C5** Verify README: Prerequisites callout above `## Install`, old cmake snippet gone from `## Setup renderdoc`

---

## File Conflict Analysis

| File | Change type | Conflicts with |
|------|------------|----------------|
| `scripts/build-renderdoc.sh` | New file | None |
| `src/rdc/commands/doctor.py` | String constant update (lines 34-40) | None |
| `tests/unit/test_doctor.py` | 1 updated + 1 new test | None |
| `README.md` | Two-section prose update | None |

Single-worktree sequential execution is sufficient.

---

## Definition of Done

- `pixi run lint && pixi run test` passes with zero failures
- `tests/unit/test_doctor.py` green (2 new tests + updated assertion)
- `scripts/build-renderdoc.sh` executable, passes `bash -n`, contains correct sha256 constant
- `README.md` contains Prerequisites callout referencing PyPI gap
- `_RENDERDOC_BUILD_HINT` references raw GitHub script URL and docs URL
