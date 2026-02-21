# Test Plan: Daemon Crash Fixes

## Scope

**In scope**: Three crash regression tests, mock updates for SWIG-compatible SDChunk iteration.
**Out of scope**: Functional correctness of event detail output (tested elsewhere).

## Test Matrix

| Layer | What | How |
|-------|------|-----|
| Unit | TCP loop survives handler exception | Monkeypatch `_handle_request` to raise, verify error response |
| Unit | SDChunk iteration via NumChildren/GetChild | Mock SDChunk with both old and new API |
| Unit | Counter UUID serialization | Mock CounterDescription with struct uuid |
| GPU | Event detail with real structured data | `test_daemon_handlers_real.py` |

## Cases

### Happy Path
- `event` method returns API call params via NumChildren/GetChild iteration
- `counter_list` serializes uuid field without error

### Error Path
- Handler raises RuntimeError → server returns JSON-RPC error -32603, stays running
- SDChunk with 0 children → empty params dict

### Edge Cases
- Counter UUID is empty string vs SWIG struct
- SDObject value is None

## Assertions

- Server loop continues after exception (running == True)
- JSON-RPC error code -32603 for internal errors
- Event params dict keys/values are strings
- Counter uuid field is always a string in response

## Risks & Rollback

Low risk — these are defensive guards. Rollback: revert commit.
