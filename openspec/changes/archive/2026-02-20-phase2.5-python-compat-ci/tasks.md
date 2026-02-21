# Tasks: Python Compatibility + CI Packaging Validation

## Phase A: Python version downgrade

- [ ] A1: Update `pyproject.toml` — `requires-python = ">=3.10"`
- [ ] A2: Update `pyproject.toml` — mypy `python_version = "3.10"`
- [ ] A3: Remove duplicate ruff config from `pyproject.toml` (already in `ruff.toml`)
- [ ] A4: Verify `ruff.toml` already has `target-version = "py310"` (no change needed)
- [ ] A5: Run `pixi run check` — verify all tests pass locally

## Phase B: CI multi-version test matrix

- [ ] B1: Update `ci.yml` test job — matrix `python-version: ["3.10", "3.12", "3.14"]`
- [ ] B2: Update `ci.yml` lint job — use Python 3.12 (stable, fast)
- [ ] B3: Update `ci.yml` typecheck job — use Python 3.12

## Phase C: CI build + packaging validation job

- [ ] C1: Add `build-and-verify` job to `ci.yml`
- [ ] C2: Layer 1 steps: `uv build`, `twine check dist/*`, `check-wheel-contents`
- [ ] C3: Layer 2 steps: clean venv install, `rdc --version`, `rdc --help`, import check
- [ ] C4: Multi-Python matrix for build job (3.10/3.12/3.14)

## Phase D: Verification

- [ ] D1: Push branch, verify all CI jobs pass
- [ ] D2: Manually verify wheel install locally: `uv build && uv pip install dist/*.whl`
- [ ] D3: Verify `rdc --version` + `rdc --help` + `rdc doctor` from installed wheel
