# Test Plan: renderdoc-build-helper

## Scope

Changes covered:
1. `scripts/build-renderdoc.sh` — new standalone bash script
2. `src/rdc/commands/doctor.py` — `_RENDERDOC_BUILD_HINT` updated
3. `README.md` — note clarifying renderdoc is not in the PyPI package

Out of scope: running the full cmake/ninja build in CI, GPU integration tests.

---

## 1. Unit Tests — `tests/unit/test_doctor.py`

### 1.1 New: hint contains script URL

```python
def test_build_hint_contains_script_url() -> None:
    from rdc.commands.doctor import _RENDERDOC_BUILD_HINT
    assert "build-renderdoc.sh" in _RENDERDOC_BUILD_HINT
```

### 1.2 New: hint contains docs URL

```python
def test_build_hint_contains_docs_url() -> None:
    from rdc.commands.doctor import _RENDERDOC_BUILD_HINT
    assert "https://" in _RENDERDOC_BUILD_HINT
```

### 1.3 Update existing regression test

`test_doctor_shows_build_hint_when_renderdoc_missing` currently asserts `"cmake -B build -DENABLE_PYRENDERDOC=ON"` in output. Update assertion to match new content:

```python
assert "build-renderdoc.sh" in result.output
```

Note: `_RENDERDOC_BUILD_HINT` is emitted via `click.echo(..., err=True)` but Click's `CliRunner` mixes stderr into `result.output` by default (`mix_stderr=True`). Do NOT use `result.stderr` — it will be `None` with default settings.

---

## 2. Script Static Checks — `scripts/build-renderdoc.sh`

Run in CI without cmake or GPU:

| Check | Command |
|-------|---------|
| Executable bit | `test -x scripts/build-renderdoc.sh` |
| Valid shebang | `head -1 scripts/build-renderdoc.sh \| grep -q '^#!/'` |
| Syntax check | `bash -n scripts/build-renderdoc.sh` |
| `set -euo pipefail` present | `grep -q 'set -euo pipefail' scripts/build-renderdoc.sh` |
| Correct renderdoc tag | `grep -q 'v1\.41' scripts/build-renderdoc.sh` |
| Installs to `~/.local` | `grep -q '\$HOME/.local/renderdoc' scripts/build-renderdoc.sh` |
| Prints `RENDERDOC_PYTHON_PATH` | `grep -q 'RENDERDOC_PYTHON_PATH' scripts/build-renderdoc.sh` |
| shellcheck | `shellcheck scripts/build-renderdoc.sh` |

---

## 3. README Static Checks

```bash
grep -q 'not.*PyPI\|PyPI.*not\|not included in the PyPI' README.md
grep -q 'build-renderdoc.sh' README.md
```

---

## 4. Manual Verification

- `bash scripts/build-renderdoc.sh` on a system where `~/.local/renderdoc/renderdoc.so` already exists → exits 0 with skip message (idempotent)
- `rdc doctor` without `RENDERDOC_PYTHON_PATH` → stderr shows updated hint with script URL and docs URL
- Full build smoke test (local only): `bash scripts/build-renderdoc.sh` → `renderdoc.so` + `librenderdoc.so` in `~/.local/renderdoc/`

---

## 5. Non-Goals

- No mocking of cmake/ninja
- No GPU integration test changes (no behaviour change to handlers)
- No exact-prose assertions on hint beyond URL strings

---

## Coverage Summary

| Area | Type | Count |
|------|------|-------|
| Hint contains script URL | Unit | 1 new |
| Hint contains docs URL | Unit | 1 new |
| Hint emitted on missing module | Unit | 1 updated |
| Script static checks | Shell | 8 |
| README checks | Grep | 2 |
| Full build + import | Manual | 1 |
