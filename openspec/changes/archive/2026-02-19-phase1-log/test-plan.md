# Test Plan: `rdc log`

## Scope

- Mock DebugMessage + GetDebugMessages in mock_renderdoc.py
- Daemon handler `log` in daemon_server.py
- CLI command `log_cmd` in commands/info.py

## Unit Tests — Daemon Handler

| Case | Input | Assert |
|------|-------|--------|
| Happy: messages returned | no filters | result has messages list |
| Filter by level | `{"level": "HIGH"}` | only HIGH messages |
| Filter by eid | `{"eid": 42}` | only messages at eid 42 |
| No messages | empty list | result messages = [] |
| No adapter | adapter=None | error -32002 |

## Unit Tests — CLI

| Case | Assert |
|------|--------|
| TSV output | exit 0, LEVEL/EID/MESSAGE header |
| --level filter | correct option passed |
| --eid filter | correct option passed |
| JSON output | exit 0, valid JSON |
| No session | exit 1 |

## Mock Enhancements

- Add `DebugMessage` dataclass with `severity`, `eventId`, `description`
- Add `GetDebugMessages()` to `MockReplayController`

## Integration Test

- `test_log` in test_daemon_handlers_real.py: call `log`, assert no error
  (may return empty list — that is valid).
