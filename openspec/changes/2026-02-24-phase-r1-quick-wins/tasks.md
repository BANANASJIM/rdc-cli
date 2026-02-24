# Phase R1: Tasks

## R1.1 Deduplicate `_require_renderdoc()` [0.25h]
- [ ] Add `require_renderdoc()` to `src/rdc/commands/_helpers.py`
- [ ] Replace in `commands/remote.py` — import from `_helpers`
- [ ] Replace in `commands/capture_control.py` — import from `_helpers`

## R1.2 Remove `sys.path.insert` from tests [0.5h]
- [ ] Add `pythonpath = ["src"]` to `pyproject.toml [tool.pytest.ini_options]`
- [ ] Remove `sys.path.insert` + orphaned imports from all 43+ test files

## R1.3 Unify `_req()` test helper [1h]
- [ ] Create `tests/unit/conftest.py` with `rpc_request(method, params=None)`
- [ ] Replace all `_req()` definitions in daemon test files
- [ ] Adapt call-sites from `_req(m, key=val)` to `rpc_request(m, {"key": val})`
