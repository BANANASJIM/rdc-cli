# Tasks: Mock Accuracy Improvements (Track A)

## Branch
`fix/test-mock-accuracy`

## Task List

- [ ] **T1** Rename `value` field to `_id` in `ResourceId` dataclass; update `__int__`, `__eq__`, `__hash__` to use `self._id`
  - File: `tests/mocks/mock_renderdoc.py` (ResourceId class, ~line 402)
  - Constructor `ResourceId(42)` continues to work (positional arg)
  - Note: search all test files for `.value` usage; fix any that use it directly

- [ ] **T2** Add `_save_texture_fails: bool = False` to `MockReplayController.__init__`
  - `SaveTexture`: if `self._save_texture_fails`, return `False` without writing file

- [ ] **T3** Add `_texture_data: dict`, `_buffer_data: dict`, `_raise_on_texture_id: set`, `_raise_on_buffer_id: set` to `MockReplayController.__init__`
  - `GetTextureData`: check raise set → look up dict → fallback default
  - `GetBufferData`: check raise set → look up dict with slice → fallback default

- [ ] **T4** Replace `ContinueDebug` pop logic with index-based access
  - Add `_debug_step_index: dict[int, int]` to `MockReplayController.__init__` (default 0)
  - `ContinueDebug`: get index, if in bounds return `batches[index]` and increment, else return `[]`

- [ ] **T5** Add `_freed_traces: set[int]` to `MockReplayController.__init__`
  - `FreeTrace`: check double-free → add to set

- [ ] Write `tests/unit/test_mock_renderdoc.py` with 8 tests per test-plan

- [ ] Run `pixi run check` — zero failures

## Definition of Done
- `pixi run check` green
- 10 new unit tests pass
- No changes to handler code (mock only)
