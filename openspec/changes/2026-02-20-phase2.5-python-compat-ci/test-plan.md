# Test Plan: Python Compatibility + CI Packaging Validation

## Scope

**In:**
- Python 3.10/3.12/3.14 compatibility of all source code
- Wheel/sdist build correctness
- Package metadata validity
- Entry point smoke test after clean install

**Out:**
- GPU integration tests (unchanged, local-only)
- PyPI publish (separate OpenSpec)
- AUR PKGBUILD validation

## Test Matrix

| Layer | What | Tool | Runs on |
|-------|------|------|---------|
| Unit | Existing 647 tests | pytest | CI matrix 3.10/3.12/3.14 |
| Build | wheel + sdist build | `uv build` | CI matrix |
| Metadata | Package metadata | `twine check` | CI (single) |
| Content | Wheel completeness | `check-wheel-contents` | CI (single) |
| Install | Clean venv + smoke | `uv venv` + `uv pip install` | CI matrix |

## Cases

### Happy path

1. **Multi-version unit tests** — all 647 tests pass on Python 3.10, 3.12, 3.14
2. **Build succeeds** — `uv build` produces both `.whl` and `.tar.gz` in `dist/`
3. **Metadata valid** — `twine check` exits 0
4. **Wheel contents correct** — `check-wheel-contents` exits 0, all `rdc/` modules included
5. **Clean install works** — `uv pip install dist/*.whl` in fresh venv succeeds
6. **Entry point works** — `rdc --version` outputs version string
7. **Help works** — `rdc --help` lists all subcommands
8. **Import works** — `python -c "from rdc.cli import main"` exits 0

### Error path

1. **Missing module** — if `__init__.py` excluded from wheel, import check catches it
2. **Broken metadata** — `twine check` fails with clear error
3. **Version mismatch** — ruff/mypy config targets different Python than pyproject.toml

### Edge cases

1. **Python 3.10 union syntax** — `X | Y` requires `from __future__ import annotations`
   (already present in all files)
2. **Type hints** — `dict[str, Any]` works on 3.10 with `__future__` annotations

## Assertions

- CI `build-and-verify` job: all steps exit 0 on all 3 Python versions
- Existing `lint`, `typecheck`, `test` jobs: still pass (no regression)
- `rdc --version` output matches `pyproject.toml` version

## Risks & Rollback

- **Risk:** Some 3.14 syntax slipped in without `__future__` import
  - Mitigation: CI matrix catches on 3.10 immediately
- **Risk:** Third-party dep incompatible with 3.10
  - Mitigation: click 8.1+ and pytest 8.0+ support 3.10
- **Rollback:** Revert PR, restore `>=3.14`
