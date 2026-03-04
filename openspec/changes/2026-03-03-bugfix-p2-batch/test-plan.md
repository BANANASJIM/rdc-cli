# Test Plan: P2 Bugfix Batch

## B75 — `_extract_sd_value()` SDObject type dispatch

Test class: `TestExtractSDValue` in `tests/unit/test_draws_events_daemon.py`.

All cases call `_handle_request(rpc_request("event", {"eid": 42}), state)` with a
structured file whose chunk child has the SDObject under test. Assert that the
`Parameters` field in `resp["result"]` contains the expected string for each basetype.
The state is built with `make_daemon_state(structured_file=..., actions=...)` where
the action at EID 42 has `events=[APIEvent(eventId=42, chunkIndex=0)]`.

### B75-01 — UnsignedInteger (basetype=7)
- Build `SDObject` with `type.basetype=7`, `data.basic.u=255`
- Assert `Parameters` contains `"255"`

### B75-02 — SignedInteger (basetype=8)
- Build `SDObject` with `type.basetype=8`, `data.basic.i=-42`
- Assert `Parameters` contains `"-42"`

### B75-03 — Float (basetype=9)
- Build `SDObject` with `type.basetype=9`, `data.basic.d=3.14`
- Assert `Parameters` contains `"3.14"` (or a float-formatted representation of 3.14)

### B75-04 — Boolean (basetype=10)
- Build `SDObject` with `type.basetype=10`, `data.basic.b=True`
- Assert `Parameters` contains `"True"`

### B75-05 — Resource (basetype=12)
- Build `SDObject` with `type.basetype=12`, `data.basic.id=42`
- Assert `Parameters` contains `"42"`

### B75-06 — String (basetype=5)
- Build `SDObject` with `type.basetype=5`, `data.str="hello"`
- Assert `Parameters` contains `"hello"`

### B75-07 — Enum (basetype=6)
- Build `SDObject` with `type.basetype=6`, `data.str="VK_FORMAT_R8G8B8A8_UNORM"`
- Assert `Parameters` contains `"VK_FORMAT_R8G8B8A8_UNORM"`

### B75-08 — No `type` attribute (legacy fallback)
- Build `SDObject` that has no `type` attribute (standard mock default)
- Assert `Parameters` contains the result of `AsString()` on the object (falls back gracefully, no exception)

### B75-09 — Unknown basetype (99)
- Build `SDObject` with `type.basetype=99`, `data.basic.value=0`
- Assert no exception is raised and `Parameters` contains the `AsString()` fallback value

---

## Remote Export (RE) — `is_remote` guard for export handlers

Add one test per handler in the relevant test file. Each test calls
`_handle_request(rpc_request("<method>", params), state)` where `state` is built
with `make_daemon_state(is_remote=True, rd=mock_renderdoc)`. The `rd` param must be
set so the test doesn't hit the `rd is None` error before reaching the remote guard.
Assert `resp["error"]["code"] == -32002` and the message contains `"not supported in remote mode"`.

### RE-01 — `pick_pixel` remote guard
- File: `tests/unit/test_pick_pixel_daemon.py`
- State: `make_daemon_state(is_remote=True)`
- Call: `rpc_request("pick_pixel", {"x": 0, "y": 0})`
- Assert: `resp["error"]["code"] == -32002`, message contains `"not supported in remote mode"`

### RE-02 — `tex_export` remote guard
- File: `tests/unit/test_tex_stats_handler.py` or a new class in the texture handler test file
- State: `make_daemon_state(is_remote=True)`
- Call: `rpc_request("tex_export", {"id": 1})`
- Assert: `resp["error"]["code"] == -32002`, message contains `"not supported in remote mode"`

### RE-03 — `rt_export` remote guard
- Same file as RE-02
- State: `make_daemon_state(is_remote=True)`
- Call: `rpc_request("rt_export", {"eid": 10, "target": 0})`
- Assert: `resp["error"]["code"] == -32002`, message contains `"not supported in remote mode"`

### RE-04 — `rt_depth` remote guard
- Same file as RE-02
- State: `make_daemon_state(is_remote=True)`
- Call: `rpc_request("rt_depth", {"eid": 10})`
- Assert: `resp["error"]["code"] == -32002`, message contains `"not supported in remote mode"`

---

## Daemon Survival (DS) — `popen_flags()` platform dispatch

Test class: `TestPopenFlagsPlatform` in `tests/unit/test_platform.py`.
Use `monkeypatch.setattr("rdc._platform._WIN", ...)` to control the platform branch
without running on a real Windows system.

### DS-01 — Windows flags
- Monkeypatch `_WIN=True`
- Call `popen_flags()`
- Assert result is a dict with key `"creationflags"`
- Assert `CREATE_NEW_PROCESS_GROUP` (0x200) bit is set
- Assert `DETACHED_PROCESS` (0x8) bit is set
- Assert `CREATE_NO_WINDOW` (0x08000000) is NOT set (mutually exclusive with DETACHED_PROCESS)

### DS-02 — Unix returns empty dict
- Monkeypatch `_WIN=False`
- Call `popen_flags()`
- Assert result `== {}`

---

## Regression

- All existing tests must continue to pass after the changes.
- `pixi run lint` produces zero warnings or errors.
