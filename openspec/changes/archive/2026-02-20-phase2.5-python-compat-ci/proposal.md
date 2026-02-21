# Proposal: Python Compatibility + CI Packaging Validation

## Summary

Lower `requires-python` from `>=3.14` to `>=3.10` and add CI build/packaging
validation with multi-version matrix (3.10/3.12/3.14). This is the foundation
for Phase 2.5 packaging/distribution.

## Motivation

- renderdoc SWIG `.so` is CPython ABI-bound; users must match Python version
  to their renderdoc build. Restricting to 3.14 is unnecessary — rdc code
  only uses 3.10+ features (`X | Y` union type).
- Current CI has zero packaging validation — broken wheels or missing modules
  would only be caught after PyPI publish.
- Multi-version CI catches compatibility regressions early.

## Design

### Python version changes

| File | Current | Target |
|------|---------|--------|
| `pyproject.toml` | `requires-python = ">=3.14"` | `">=3.10"` |
| `pyproject.toml` | `python_version = "3.14"` (mypy) | `"3.10"` |
| `pyproject.toml` | `target-version = "py314"` (ruff) | remove (use ruff.toml) |
| `ruff.toml` | `target-version = "py310"` | keep (already correct) |
| `pixi.toml` | `python = "3.14.*"` | keep (dev env, not distribution) |
| `docker/Dockerfile` | python3.14 | keep (dev/CI image) |

### CI packaging validation (new job in ci.yml)

Three-layer validation on every PR, multi-Python matrix:

**Layer 1 — Build:**
- `uv build` → wheel + sdist
- `twine check dist/*` → metadata validation
- `check-wheel-contents dist/*.whl` → content completeness

**Layer 2 — Install:**
- Clean venv install from wheel
- `rdc --version` entry point check
- `rdc --help` subcommand registration check
- `python -c "from rdc.cli import main"` import check

**Layer 3 — Matrix:**
- Python 3.10, 3.12, 3.14
- All layers run on each version

## Scope

**In:** pyproject.toml, ruff config alignment, CI build job, multi-version matrix.

**Out:** PyPI publish workflow (separate OpenSpec), AUR PKGBUILD, README changes.
