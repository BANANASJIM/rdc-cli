# Test Plan — Phase 5B: Capture Unified + CaptureFile Helpers

## Scope

### In scope

- Mock extensions: `CaptureOptions`, `ExecuteResult`, `TargetControlMessageType`,
  `NewCaptureData`, `MockTargetControl`, enhanced `MockCaptureFile`, module-level
  `ExecuteAndInject` / `CreateTargetControl` / `GetDefaultCaptureOptions`
- `capture_core` service module: `build_capture_options`, `execute_and_capture` (all branches)
- `capture` command rewrite: Python API path, renderdoccmd fallback, all 12 CLI option flags,
  `--list-apis`, `--auto-open`, `--json`, `--trigger` mode
- CaptureFile daemon handlers: `thumbnail`, `gpus`, `sections`, `section`
- CaptureFile CLI commands: `thumbnail`, `gpus`, `sections`, `section`
- `info` handler enhancement: `HasCallstacks`, `RecordedMachineIdent`, `TimestampBase` fields
- TargetControl state persistence: save/load/delete, corrupt-file recovery
- `attach` CLI command: connect, save state, error on failure
- `capture-trigger`, `capture-list`, `capture-copy` CLI commands
- GPU integration tests for capture flow and new CaptureFile commands

### Out of scope

- Windows / macOS platform testing
- Remote capture (cross-host TargetControl)
- Performance benchmarking of capture latency
- Automated GPU tests in CI (manual only)
- D3D11 / D3D12 / Metal capture paths
- Multi-process capture coordination

---

## New Test Files

> **Status (2026-02-23):** PR 1 test file (`test_mock_capture_types.py`) exists in master. PR 2 and PR 3 test files have NOT been created yet — this is the primary remaining work.

### PR 1: Mock Extensions

| File | Description |
|------|-------------|
| `tests/unit/test_mock_capture_types.py` | Smoke tests for all new mock types |

#### `test_mock_capture_types.py` cases

| Test | Description |
|------|-------------|
| `test_capture_options_defaults` | `CaptureOptions()` has 12 fields; verify default values are correct types |
| `test_capture_options_writable` | All 12 fields can be set and read back |
| `test_execute_result_fields` | `ExecuteResult` has `ident` (int) and `result` fields readable |
| `test_target_control_message_type_values` | `TargetControlMessageType` enum has exactly 11 members: `Unknown=0`, `Disconnected=1`, `Busy=2`, `Noop=3`, `NewCapture=4`, `CaptureCopied=5`, `RegisterAPI=6`, `NewChild=7`, `CaptureProgress=8`, `CapturableWindowCount=9`, `RequestShow=10` |
| `test_new_capture_data_fields` | `NewCaptureData` has all 11 fields: `captureId`, `frameNumber`, `path`, `byteSize`, `timestamp`, `thumbnail`, `thumbWidth`, `thumbHeight`, `title`, `api`, `local` |
| `test_mock_target_control_connected` | `MockTargetControl.Connected()` returns True by default |
| `test_mock_target_control_get_target` | `GetTarget()` returns a string |
| `test_mock_target_control_get_pid` | `GetPID()` returns an int |
| `test_mock_target_control_get_api` | `GetAPI()` returns a string |
| `test_mock_target_control_trigger_capture` | `TriggerCapture()` callable; no exception |
| `test_mock_target_control_queue_capture` | `QueueCapture(0)` callable; no exception |
| `test_mock_target_control_copy_capture` | `CopyCapture(0, "/tmp/x.rdc")` callable; returns path string |
| `test_mock_target_control_receive_message` | `ReceiveMessage(progress=None)` returns a `TargetControlMessage` with default type `Noop` |
| `test_mock_target_control_shutdown` | `Shutdown()` callable; no exception |
| `test_capture_file_get_thumbnail` | `MockCaptureFile.GetThumbnail(FileType.PNG, 256)` returns object with `data` bytes and `len` |
| `test_capture_file_get_available_gpus` | `GetAvailableGPUs()` returns a list |
| `test_capture_file_section_count` | `GetSectionCount()` returns an int |
| `test_capture_file_section_properties` | `GetSectionProperties(0)` returns object with `name` and `type` |
| `test_capture_file_section_contents` | `GetSectionContents(0)` returns bytes |
| `test_capture_file_find_section` | `FindSectionByName("name")` returns int index or -1 |
| `test_capture_file_has_callstacks` | `HasCallstacks()` returns bool |
| `test_capture_file_recorded_machine_ident` | `RecordedMachineIdent()` returns a string |
| `test_capture_file_timestamp_base` | `TimestampBase()` returns an int |
| `test_module_execute_and_inject` | `mock_renderdoc.ExecuteAndInject(app, workingDir, cmdLine, env, capturefile, opts, waitForExit)` callable with 7 params; returns `ExecuteResult` |
| `test_module_create_target_control` | `mock_renderdoc.CreateTargetControl(URL, ident, clientName, forceConnection)` callable; returns `MockTargetControl` |
| `test_module_get_default_capture_options` | `mock_renderdoc.GetDefaultCaptureOptions()` returns a `CaptureOptions` instance with recommended defaults (`allowFullscreen=True`) |

---

### PR 2: Capture Rewrite + CaptureFile Helpers

| File | Description |
|------|-------------|
| `tests/unit/test_capture_core.py` | Unit tests for `src/rdc/capture_core.py` service module |
| `tests/unit/test_capturefile_handlers.py` | Unit tests for `src/rdc/handlers/capturefile.py` daemon handlers |
| `tests/unit/test_capturefile_commands.py` | Unit tests for CaptureFile CLI commands via `CliRunner` |

#### `test_capture_core.py` cases

All tests monkeypatch `find_renderdoc` to return a mock renderdoc module. A `_make_mock_rd()`
helper configures `ExecuteAndInject`, `CreateTargetControl`, and default `MockTargetControl`
behaviour.

| Test | Description |
|------|-------------|
| `test_build_capture_options_defaults` | `build_capture_options({})` returns `CaptureOptions` with expected default values |
| `test_build_capture_options_all_flags` | All 12 boolean flags in the options dict map to the correct `CaptureOptions` fields |
| `test_execute_and_capture_success` | `ExecuteAndInject` → `CreateTargetControl` → `TriggerCapture` → `NewCapture` message → `CopyCapture` → returns path string |
| `test_execute_and_capture_queue_frame` | `frame=0` uses `QueueCapture` instead of `TriggerCapture`; result path returned |
| `test_execute_and_capture_timeout` | No `NewCapture` message before timeout → returns error string containing "timeout" |
| `test_execute_and_capture_disconnect` | `ReceiveMessage` returns `Disconnected` type → returns error string containing "disconnect" |
| `test_execute_and_capture_inject_failure` | `ExecuteAndInject` result is not `ResultCode.Succeeded` → returns error string |
| `test_execute_and_capture_trigger_mode` | `trigger=True` → skip auto-capture; returns `CaptureResult` with `success=True` and `ident` set |

#### `test_capturefile_handlers.py` cases

All tests use `_handle_request()` with `DaemonState` + `MockCaptureFile` on `state.capture`.
A `_make_state(tmp_path)` helper builds a `DaemonState` with `temp_dir=str(tmp_path)`.

| Test | Description |
|------|-------------|
| `test_thumbnail_success` | `GetThumbnail` returns data with non-zero `len` → result has base64-encoded `data`, `width`, and `height` fields |
| `test_thumbnail_empty` | `GetThumbnail` returns data with `len == 0` → result has empty `data` (`""`), `width=0`, `height=0` |
| `test_thumbnail_maxsize` | `maxsize` param forwarded to `GetThumbnail` as second argument |
| `test_gpus_success` | `GetAvailableGPUs` returns 2 entries → result `gpus` list has length 2 with expected fields |
| `test_gpus_empty` | `GetAvailableGPUs` returns empty list → result `gpus` is `[]` |
| `test_sections_success` | `GetSectionCount()` returns 2; `GetSectionProperties(i)` called for each → result `sections` list has 2 entries with `name` and `type` |
| `test_section_content_text` | `FindSectionByName("name")` returns 0; section type is text → result has `content` as string |
| `test_section_content_binary` | Section type is binary → result has `path` pointing to a temp file |
| `test_section_not_found` | `FindSectionByName` returns -1 → error -32001 |

#### `test_capturefile_commands.py` cases

All tests monkeypatch `load_session` and `send_request` on `rdc.commands._helpers`, use
`CliRunner`. Pattern mirrors `test_cli_commands.py`.

| Test | Description |
|------|-------------|
| `test_thumbnail_cmd` | `thumbnail -o /tmp/t.jpg` → daemon `thumbnail` method called → file path in output |
| `test_gpus_cmd` | `gpus` → daemon `gpus` method called → structured list output |
| `test_sections_cmd` | `sections` → daemon `sections` method called → list output |
| `test_section_cmd` | `section NAME` → daemon `section` method called → content output |
| `test_thumbnail_cmd_json` | `thumbnail --json` → output is valid JSON with expected keys |
| `test_gpus_cmd_json` | `gpus --json` → output is valid JSON with `gpus` array |

---

### PR 3: TargetControl Commands

| File | Description |
|------|-------------|
| `tests/unit/test_target_state.py` | Unit tests for `src/rdc/target_state.py` persistence module |
| `tests/unit/test_capture_control.py` | Unit tests for `attach` / `capture-trigger` / `capture-list` / `capture-copy` CLI commands |

#### `test_target_state.py` cases

All tests monkeypatch `Path.home()` to `tmp_path` to avoid touching the real home directory.

| Test | Description |
|------|-------------|
| `test_save_load_target_state` | Save state dict → load → fields match exactly |
| `test_load_missing_returns_none` | No state file → `load()` returns `None` |
| `test_delete_target_state` | Save → delete → `load()` returns `None`; state file does not exist |
| `test_corrupt_file_returns_none` | Write invalid JSON to state file → `load()` returns `None`; file cleaned up |

#### `test_capture_control.py` cases

All tests monkeypatch `find_renderdoc` in `rdc.discover` to return a mock module (PR 3 commands
bypass the daemon and call `CreateTargetControl` directly). Also monkeypatch `Path.home()` to
`tmp_path` for state file isolation. Use `CliRunner`.

| Test | Description |
|------|-------------|
| `test_attach_success` | Monkeypatch `CreateTargetControl` → saves state → output shows target and PID |
| `test_attach_connection_failed` | `CreateTargetControl` returns None → exit code non-zero, error in output |
| `test_capture_trigger_success` | Load saved state → `TriggerCapture` called → output confirms trigger sent (does not wait for `NewCapture`) |
| `test_capture_trigger_no_state` | No saved state → error output, non-zero exit code |
| `test_capture_list_success` | Mock `ReceiveMessage` returns `NewCapture` then `Noop` → list output with paths |
| `test_capture_copy_success` | `CopyCapture` called with correct index and dest path → output path shown |
| `test_capture_copy_no_state` | No saved state → error output, non-zero exit code |

---

## Updated Test Files

### PR 2: `tests/unit/test_capture.py`

| Test | Description |
|------|-------------|
| `test_capture_python_api_success` | Monkeypatch `capture_core.execute_and_capture` → success result → exit 0, output path shown |
| `test_capture_fallback_renderdoccmd` | `capture_core` raises `ImportError` (no renderdoc) → falls back to `renderdoccmd` subprocess |
| `test_capture_list_apis` | `--list-apis` calls renderdoccmd, not Python API |
| `test_capture_auto_open` | `--auto-open` invokes `open_cmd` with captured path after success |
| `test_capture_json_output` | `--json` produces structured JSON with `path` and `api` |
| `test_capture_all_options` | All 12 `CaptureOptions` CLI flags translate to correct params in `execute_and_capture` call |

### PR 2: `tests/unit/test_daemon_handlers.py` (or `test_query_handlers.py`)

| Test | Description |
|------|-------------|
| `test_info_includes_callstacks` | `info` response contains `has_callstacks` field (bool) |
| `test_info_includes_machine_ident` | `info` response contains `machine` field (string) |
| `test_info_includes_timestamp_base` | `info` response contains `timestamp_base` field (int) |

---

## Manual Verification

### PR 2: Capture rewrite + CaptureFile helpers

```bash
# Python API path
rdc capture /usr/bin/vkcube -o /tmp/test.rdc --timeout 10

# Frame-queued capture
rdc capture /usr/bin/vkcube -o /tmp/test2.rdc --frame 0 --api-validation

# Trigger mode (inject only, no auto-capture)
rdc capture /usr/bin/vkcube --trigger

# Fallback to renderdoccmd when Python API unavailable
RENDERDOC_PYTHON_PATH=/nonexistent rdc capture /usr/bin/vkcube -o /tmp/fb.rdc

# CaptureFile helpers (open a session first)
rdc open /tmp/test.rdc
rdc thumbnail -o /tmp/thumb.jpg
rdc gpus
rdc sections
rdc info          # verify has_callstacks, machine, timestamp_base fields
rdc close
```

### PR 3: TargetControl commands

```bash
rdc capture /usr/bin/vkcube --trigger   # inject only, returns ident
rdc attach <ident>
rdc capture-trigger --frames 1
rdc capture-list
rdc capture-copy 0 -o /tmp/copied.rdc
```

---

## Coverage Summary

| File | Target Coverage |
|------|----------------|
| `src/rdc/capture_core.py` | 90%+ |
| `src/rdc/handlers/capturefile.py` | 90%+ |
| `src/rdc/commands/capture.py` (rewrite) | 85%+ |
| `src/rdc/commands/capturefile.py` | 85%+ |
| `src/rdc/commands/capture_control.py` | 85%+ |
| `src/rdc/target_state.py` | 95%+ |
| `tests/mocks/mock_renderdoc.py` additions | not measured |
| GPU tests (`@pytest.mark.gpu`) | excluded from CI denominator |

---

## Test Matrix

| Dimension | Value |
|-----------|-------|
| Python | 3.10, 3.12, 3.14 (CI matrix) |
| Platform | Linux (primary) |
| GPU | RTX 3080 Ti (manual only) |
| CI command | `pixi run lint && pixi run test` |

---

## Fixtures

| Fixture | Location | Purpose |
|---------|----------|---------|
| `tmp_path` | pytest built-in | Temp directory for thumbnail and binary section writes |
| `vkcube_replay` | `tests/conftest.py` | GPU test: pre-loaded vkcube replay session |
| `rd_module` | `tests/conftest.py` | GPU test: real renderdoc module |
| `_make_state(tmp_path)` | per-file helper | Builds `DaemonState` with `MockCaptureFile` wired in |
| `_make_mock_rd()` | `test_capture_core.py` | Builds mock renderdoc module with configurable `ExecuteAndInject` and `CreateTargetControl` |

---

## GPU Integration Tests

Append `TestCaptureFileReal` to `tests/integration/test_daemon_handlers_real.py`.
Use the same `vkcube_replay` fixture and `_call()` helper.

| # | Test | Setup | Assertion |
|---|------|-------|-----------|
| G1 | `test_thumbnail_real` | Open vkcube capture via fixture | `result["size"] > 0`; written file starts with PNG magic bytes |
| G2 | `test_gpus_real` | Same fixture | `result["gpus"]` is a list; if non-empty, each entry has a name field |
| G3 | `test_sections_real` | Same fixture | `result["sections"]` is a list; count matches `GetSectionCount()` |
| G4 | `test_info_enhanced_fields` | Same fixture | `result` contains `has_callstacks` (bool), `machine` (str), `timestamp_base` (int) |

---

## Non-Goals

- No automated GPU tests in CI (manual only)
- No Windows / macOS testing
- No remote capture testing (cross-host `CreateTargetControl`)
- No performance benchmarking of capture latency or copy throughput
- No multi-process capture coordination testing
