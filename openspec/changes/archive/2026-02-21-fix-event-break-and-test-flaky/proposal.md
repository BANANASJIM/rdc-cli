# Proposal: fix-event-break-and-test-flaky

## Summary

Two independent bug fixes in a single branch:

1. **`rdc event` shows only first sub-event** — `query.py:423` has a `break` that exits after the first `APIEvent` chunk, discarding parameters from subsequent chunks.
2. **Unit tests polluted by live daemon session** — `TestNoSession` and `test_close_session_without_state` fail when a daemon session happens to be running (e.g. from E2E pre-push hook).

## Motivation

### Fix 1: event break

RenderDoc actions can have multiple `APIEvent` entries (e.g. `vkCmdSetViewport` + `vkCmdDrawIndexed`). The `break` at line 423 of `_handle_event` causes only the first chunk's parameters to appear. Users see incomplete API call information.

**Impact:** Data loss in `rdc event <eid>` output — parameters from secondary chunks are silently dropped.

### Fix 2: test session pollution

Five tests assume no daemon session exists. When a session is active (from concurrent E2E tests or manual `rdc open`), `load_session()` returns a live session state, causing these tests to get exit code 0 instead of expected 1.

**Impact:** Flaky CI — tests pass in isolation but fail when daemon is running.

## Design

### Fix 1

Delete the `break` statement in `_handle_event` (query.py). This lets the loop iterate all `action.events`, accumulating parameters from every chunk. The last chunk's name becomes `api_call` (correct: the final API call is the draw/dispatch itself).

### Fix 2

Add `monkeypatch` fixtures to patch `load_session` to return `None`:

| Test file | Patch target | Reason |
|-----------|-------------|--------|
| `test_draws_events_cli.py` TestNoSession (5 tests) | `rdc.commands._helpers.load_session` | Shared helper import |
| `test_draws_events_cli.py` test_stats | `rdc.commands.info.load_session` | stats has its own import |
| `test_session_service.py` test_close_session_without_state | `session_service.load_session` | Direct module attribute |

## Scope

- **In scope:** Delete break, add monkeypatches, add regression test
- **Out of scope:** Changing event output format, daemon session isolation (Phase 3A)
