# Test Plan: fix-event-break-and-test-flaky

## Scope

- **In scope:** Multi-event parameter accumulation, session-independent test isolation
- **Out of scope:** Event output format changes, new CLI features

## Test Matrix

| Layer | Tests | Purpose |
|-------|-------|---------|
| Unit (daemon) | 1 new | Multi-chunk event regression |
| Unit (CLI) | 6 modified | Monkeypatch session isolation |
| Unit (service) | 1 modified | Monkeypatch session isolation |
| GPU integration | 0 | Not needed — behavior change is covered by existing GPU event tests |

## Cases

### Happy path

- **test_event_multi_event_all_params_shown**: Action with 2 APIEvents (chunk 0: vkCmdSetViewport with viewportCount, chunk 1: vkCmdDrawIndexed with indexCount+instanceCount). Assert all 3 params present in result, API Call = "vkCmdDrawIndexed" (last chunk wins).

### Error path

- **test_info/events/draws/event/draw** (no session): Monkeypatch `load_session` → `None`, assert exit code 1.
- **test_stats** (no session): Monkeypatch `rdc.commands.info.load_session` → `None`, assert exit code 1.
- **test_close_session_without_state**: Monkeypatch `session_service.load_session` → `None`, assert `ok=False`.

### Edge cases

- Multi-event with overlapping param names: last chunk's value wins (dict update semantics). Covered implicitly by the regression test.

## Assertions

- Exit codes: 1 for no-session commands, 0 for successful event query
- stdout contract: event result contains all chunk parameters
- No changes to TSV/JSON schema

## Risks & Rollback

- **Risk:** Removing `break` could change behavior for single-event actions — mitigated because single-event loop iterates once regardless.
- **Rollback:** Revert single line (re-add `break`); revert monkeypatches (tests become flaky again but functionally unchanged).
