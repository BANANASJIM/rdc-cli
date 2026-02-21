# Tasks: Daemon Crash Fixes

- [ ] Update mock: add `NumChildren()`, `GetChild(i)`, `AsString()`, `AsInt()` to SDChunk/SDObject
- [ ] Write crash regression tests (3 test cases)
- [ ] Fix 1: TCP loop try/except guard in `run_server`
- [ ] Fix 2: SDChunk iteration via `NumChildren()`/`GetChild(i)` in event handler
- [ ] Fix 3: Counter UUID `str()` coercion
- [ ] Run `pixi run check`
