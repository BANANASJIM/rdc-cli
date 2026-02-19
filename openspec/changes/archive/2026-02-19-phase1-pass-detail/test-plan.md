# Test Plan: `rdc pass`

## Scope

- `get_pass_detail()` in query_service.py
- Daemon handler `pass` in daemon_server.py
- CLI command `pass_cmd` in commands/resources.py

## Unit Tests — Daemon Handler

| Case | Input | Assert |
|------|-------|--------|
| Happy: by index | `{"index": 0}` | result has name, begin_eid, end_eid, draws |
| Happy: by name | `{"name": "Shadow"}` | same fields, case-insensitive match |
| Error: invalid index | `{"index": 999}` | error -32001 |
| Error: unknown name | `{"name": "NoSuch"}` | error -32001 |
| Error: no adapter | no adapter | error -32002 |

## Unit Tests — CLI

| Case | Assert |
|------|--------|
| TSV output | exit 0, key-value lines present |
| JSON output | exit 0, valid JSON with expected keys |
| No session | exit 1 |

## Mock Enhancements

- MockPipeState already has `GetOutputTargets()` and `GetDepthTarget()` — extend
  with non-empty default targets for testing attachment extraction.

## Integration Test

- `test_pass_detail` in test_daemon_handlers_real.py: call `pass` with index 0,
  verify result contains pass metadata fields.
