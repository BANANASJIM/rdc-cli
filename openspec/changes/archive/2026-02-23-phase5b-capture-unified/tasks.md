# Tasks: phase5b-capture-unified

## Structure

Three sequential PRs, with parallel worktree agents inside PR 2:

- **PR 1** (`feature/5b-mock-foundation`): Mock extensions — new types for TargetControl, CaptureFile, CaptureOptions
- **PR 2** (`feature/5b-capture-helpers`): Capture rewrite + CaptureFile helpers — two parallel worktree agents (non-conflicting files), merge step for shared files
- **PR 3** (`feature/5b-target-control`): TargetControl commands — new commands for live process attach/capture

PR 2 depends on PR 1 merged. PR 3 depends on PR 2 merged.

> **Implementation Status (2026-02-23):**
> - PR 1: **DONE** — merged as commit `b3cc2fc`. All mock types implemented and tested.
> - PR 2: **~90% done** — production code complete (`capture_core.py`, `commands/capture.py`, `handlers/capturefile.py`, `commands/capturefile.py`, `cli.py` registration, `daemon_server.py` registration, `handlers/query.py` info enhancement). `embed-deps` removed (real API confirmed `HasPendingDependencies`/`EmbedDependenciesIntoCapture` do not exist on `CaptureFile`). **Remaining: all unit tests**.
> - PR 3: **Not started**.

---

## PR 1: Mock Extensions + Foundation

### Branch
`feature/5b-mock-foundation`

### Context
Extend `tests/mocks/mock_renderdoc.py` with all types needed for Phase 5B: `CaptureOptions` (12 fields), `ExecuteResult`, `TargetControlMessageType`, `NewCaptureData`, `Thumbnail`, `GPUDevice`, `SectionProperties`, `TargetControlMessage`, `MockTargetControl`, enhanced `MockCaptureFile`, and three module-level functions. All changes are additive — no existing mock code is modified.

---

### Phase A — Tests first

- [ ] **A1** Create `tests/unit/test_mock_capture_types.py`:
  - `test_capture_options_defaults` — instantiate `CaptureOptions()` with no args; verify all 12 fields have SWIG zero-init defaults (e.g. `allowFullscreen=False`, `apiValidation=False`, `captureCallstacks=False`, all bools False, all ints 0)
  - `test_execute_result_fields` — instantiate `ExecuteResult(result=0, ident=1234)`; verify both fields accessible
  - `test_target_control_message_type_values` — verify `TargetControlMessageType` has 11 members; spot-check `Unknown=0`, `Disconnected=1`, `Noop=3`, `NewCapture=4`, `RequestShow=10`
  - `test_new_capture_data_fields` — instantiate with all 11 fields; verify `path`, `frameNumber`, `byteSize` accessible
  - `test_thumbnail_data_fields` — instantiate `Thumbnail(data=b"abc", width=16, height=16)`; verify fields
  - `test_gpu_device_fields` — instantiate `GPUDevice`; verify `name`, `vendor`, `deviceID`, `driver` accessible
  - `test_section_properties_fields` — instantiate `SectionProperties`; verify `name`, `type`, `version`, `compressedSize`, `uncompressedSize`, `flags` accessible
  - `test_mock_target_control_connected` — instantiate `MockTargetControl`; call `Connected()` → `True`
  - `test_mock_target_control_receive_message` — call `ReceiveMessage(progress=None)`; returns `TargetControlMessage` with type `Noop`
  - `test_mock_target_control_trigger_capture` — call `TriggerCapture(1)`; no exception
  - `test_mock_target_control_shutdown` — call `Shutdown()`; `Connected()` returns `False` afterwards
  - `test_mock_capturefile_get_thumbnail` — call `GetThumbnail(fileType=0, maxsize=256)`; returns `Thumbnail`
  - `test_mock_capturefile_get_available_gpus` — call `GetAvailableGPUs()`; returns list with at least one `GPUDevice`
  - `test_mock_capturefile_get_section_count` — call `GetSectionCount()`; returns int >= 0
  - `test_mock_capturefile_get_section_properties` — call `GetSectionProperties(0)`; returns `SectionProperties`
  - `test_mock_capturefile_get_section_contents` — call `GetSectionContents(0)`; returns `bytes`
  - `test_mock_capturefile_find_section_by_name` — call `FindSectionByName("FrameCapture")`; returns int
  - `test_mock_capturefile_has_callstacks` — call `HasCallstacks()`; returns `bool`
  - `test_mock_capturefile_recorded_machine_ident` — call `RecordedMachineIdent()`; returns `str`
  - `test_mock_capturefile_timestamp_base` — call `TimestampBase()`; returns `int`
  - `test_execute_and_inject` — call module-level `ExecuteAndInject(...)`; returns `ExecuteResult`
  - `test_create_target_control` — call `CreateTargetControl(URL="", ident=12345, clientName="rdc-cli", forceConnection=True)`; returns `MockTargetControl`
  - `test_get_default_capture_options` — call `GetDefaultCaptureOptions()`; returns `CaptureOptions` with `allowFullscreen=True`

- [ ] **A2** Run tests — expect all to fail (red phase, implementations missing)

---

### Phase B — Implementation

- [ ] **B1** Add to `tests/mocks/mock_renderdoc.py` — enums and dataclasses:
  - Enum `TargetControlMessageType(IntEnum)` with 11 values: `Unknown=0`, `Disconnected=1`, `Busy=2`, `Noop=3`, `NewCapture=4`, `CaptureCopied=5`, `RegisterAPI=6`, `NewChild=7`, `CaptureProgress=8`, `CapturableWindowCount=9`, `RequestShow=10`
  - Enum `SectionType(IntEnum)`: `Unknown=0`, `FrameCapture=1`, `ResolveDatabase=2`, `Bookmarks=3`, `Notes=4`, `ResourceRenames=5`, `AMDRGPProfile=6`, `ExtendedThumbnail=7`
  - Enum `SectionFlags(IntFlag)`: `NoFlags=0`, `ASCIIStored=1`, `LZ4Compressed=2`, `ZstdCompressed=4`
  - Dataclass `CaptureOptions` with 12 camelCase fields (SWIG zero-init defaults): `allowFullscreen: bool = False`, `allowVSync: bool = False`, `apiValidation: bool = False`, `captureCallstacks: bool = False`, `captureCallstacksOnlyActions: bool = False`, `delayForDebugger: int = 0`, `verifyBufferAccess: bool = False`, `hookIntoChildren: bool = False`, `refAllResources: bool = False`, `captureAllCmdLists: bool = False`, `debugOutputMute: bool = False`, `softMemoryLimit: int = 0`
  - Dataclass `ExecuteResult` with fields: `result: int = 0`, `ident: int = 0`
  - Dataclass `Thumbnail` with fields: `data: bytes = b""`, `width: int = 0`, `height: int = 0`
  - Dataclass `GPUDevice` with fields: `name: str = ""`, `vendor: int = 0`, `deviceID: int = 0`, `driver: str = ""`
  - Dataclass `SectionProperties` with fields: `name: str = ""`, `type: SectionType = SectionType.Unknown`, `version: str = ""`, `compressedSize: int = 0`, `uncompressedSize: int = 0`, `flags: SectionFlags = SectionFlags.NoFlags`
  - Dataclass `NewCaptureData` with fields: `captureId: int = 0`, `frameNumber: int = 0`, `path: str = ""`, `byteSize: int = 0`, `timestamp: int = 0`, `thumbnail: bytes = b""`, `thumbWidth: int = 0`, `thumbHeight: int = 0`, `title: str = ""`, `api: str = ""`, `local: bool = True`
  - Dataclass `TargetControlMessage` with fields: `type: TargetControlMessageType = TargetControlMessageType.Noop`, `newCapture: NewCaptureData | None = None`

- [ ] **B2** Add class `MockTargetControl` to `tests/mocks/mock_renderdoc.py`:
  - `__init__`: `_connected = True`, `_captures: list[NewCaptureData] = []`, `_ident = 0`, `_pid = 0`, `_api = ""`, `_target = ""`
  - `Connected() -> bool`: return `_connected`
  - `GetTarget() -> str`: return `_target`
  - `GetPID() -> int`: return `_pid`
  - `GetAPI() -> str`: return `_api`
  - `TriggerCapture(numFrames: int = 1) -> None`: no-op
  - `QueueCapture(frameNumber: int, numFrames: int = 1) -> None`: no-op
  - `CopyCapture(captureId: int, localpath: str) -> None`: no-op
  - `DeleteCapture(captureId: int) -> None`: removes matching entry from `_captures`
  - `ReceiveMessage(progress: Any = None) -> TargetControlMessage`: returns `TargetControlMessage(type=TargetControlMessageType.Noop)`
  - `CycleActiveWindow() -> None`: no-op
  - `Shutdown() -> None`: sets `_connected = False`

- [ ] **B3** Enhance `MockCaptureFile` in `tests/mocks/mock_renderdoc.py`:
  - `GetThumbnail(fileType: int, maxsize: int) -> Thumbnail`: return `Thumbnail(data=b"\x00" * 16, width=4, height=4)`
  - `GetAvailableGPUs() -> list[GPUDevice]`: return `[GPUDevice(name="Mock GPU", vendor=0, deviceID=0, driver="0.0")]`
  - `GetSectionCount() -> int`: return `1`
  - `GetSectionProperties(idx: int) -> SectionProperties`: return `SectionProperties(name="FrameCapture", type=SectionType.FrameCapture)`
  - `GetSectionContents(idx: int) -> bytes`: return `b"mock-section-data"`
  - `FindSectionByName(name: str) -> int`: return `0` if `name == "FrameCapture"` else `-1`
  - `HasCallstacks() -> bool`: return `False`
  - `RecordedMachineIdent() -> str`: return `"mock-machine-ident"`
  - `TimestampBase() -> int`: return `0`

- [ ] **B4** Add module-level functions to `tests/mocks/mock_renderdoc.py`:
  - `ExecuteAndInject(app: str, workingDir: str, cmdLine: str, envList: list[str], capturefile: str, opts: CaptureOptions, waitForExit: bool = False) -> ExecuteResult`: return `ExecuteResult(result=0, ident=12345)` (7 params matching real API)
  - `CreateTargetControl(URL: str, ident: int, clientName: str, forceConnection: bool) -> MockTargetControl`: return `MockTargetControl()`
  - `GetDefaultCaptureOptions() -> CaptureOptions`: returns `CaptureOptions(allowFullscreen=True, allowVSync=True, debugOutputMute=True)`

---

### Phase C — Verify

- [ ] **C1** `pixi run lint` — zero errors
- [ ] **C2** `pixi run test tests/unit/test_mock_capture_types.py` — all 26 tests pass
- [ ] **C3** `pixi run test` (full suite) — zero failures, no regressions

---

### File Conflict Analysis (PR 1)

| File | Change type | Conflicts with |
|------|-------------|----------------|
| `tests/mocks/mock_renderdoc.py` | Extended (additive only) | None |
| `tests/unit/test_mock_capture_types.py` | New file | None |

Single-worktree sequential execution is sufficient — all changes are additive.

---

## PR 2: Capture Rewrite + CaptureFile Helpers

### Branch
`feature/5b-capture-helpers` (base: PR 1 merged)

### Context
Two parallel worktree agents handle non-conflicting files. Branch A rewrites `capture.py` to use the Python API (`ExecuteAndInject` + `CreateTargetControl` message loop) with fallback to `renderdoccmd`, and extracts service logic into `capture_core.py`. Branch B adds five new CaptureFile helper commands and handlers. A merge step then registers everything in the three shared files (`cli.py`, `daemon_server.py`, `handlers/query.py`).

---

### Agent 1 (Branch A): Capture Rewrite

#### Phase A — Tests first

- [ ] **A1** Create `tests/unit/test_capture_core.py`:
  - `test_build_options_defaults` — call `build_capture_options({})` with no overrides; verify returned `CaptureOptions` has all defaults
  - `test_build_options_all_flags` — pass all 12 flag kwargs; verify each field set correctly on returned `CaptureOptions`
  - `test_capture_success` — mock `renderdoc.ExecuteAndInject` returning `ExecuteResult(ident=12345)` and `MockTargetControl` emitting one `NewCapture` message then `Ping`; assert `CaptureResult.path` is set and `success=True`
  - `test_capture_queue_frame` — pass `frame=5`; verify `QueueCapture(5, 1)` is called before message loop
  - `test_capture_timeout` — mock `ReceiveMessage` to always return `Ping`; verify `CaptureResult.success=False` and error contains "timeout" after timeout expires
  - `test_capture_disconnect` — mock `Connected()` returning `False` immediately; verify `CaptureResult.success=False` with disconnect error
  - `test_capture_inject_failure` — mock `ExecuteAndInject` returning `ExecuteResult(result=1, ident=0)`; verify raises or returns failure result with non-zero result code
  - `test_capture_trigger_mode` — pass `trigger=True`; verify `TriggerCapture(1)` is called instead of `QueueCapture`

- [ ] **A2** Update `tests/unit/test_capture.py` — rewrite for new Python API:
  - `test_python_api_success` — mock `capture_core.execute_and_capture` returning successful `CaptureResult`; invoke `rdc capture app`; assert exit 0, stdout shows path
  - `test_fallback_renderdoccmd` — set `RENDERDOC_PYTHON_PATH` to nonexistent path so `find_renderdoc()` returns None; mock `_find_renderdoccmd` returning a fake path; mock subprocess call; assert fallback invoked
  - `test_list_apis` — mock `renderdoc.GetSupportedDeviceProtocols()` (if applicable) or hardcoded list; verify `rdc capture --list-apis` exits 0 with API names
  - `test_auto_open` — mock successful capture; pass `--auto-open`; verify `rdc open` invoked on captured path
  - `test_json_output` — pass `--json`; verify stdout is valid JSON containing `path`, `frame`, `api`
  - `test_all_options` — invoke with all 12 `--capture-*` flags; verify `build_capture_options` called with correct kwargs

#### Phase B — Implementation

- [ ] **B1** Create `src/rdc/capture_core.py`:
  - Dataclass `CaptureResult` with fields: `success: bool`, `path: str = ""`, `frame: int = 0`, `byte_size: int = 0`, `api: str = ""`, `local: bool = True`, `ident: int = 0`, `pid: int = 0`, `error: str = ""`
  - Function `build_capture_options(opts: dict[str, Any]) -> CaptureOptions`: constructs `CaptureOptions` from a dict of flag overrides; unknown keys ignored
  - Function `execute_and_capture(rd: Any, app: str, args: str, workdir: str, output: str, opts: CaptureOptions, *, frame: int | None = None, trigger: bool = False, timeout: float = 60.0, wait_for_exit: bool = False) -> CaptureResult`:
    - Calls `renderdoc.ExecuteAndInject(app, workdir, args, [], output, opts, False)` → `ExecuteResult` (7 params)
    - Returns failure result if `ExecuteResult.result != 0` or `ident == 0`
    - Calls `renderdoc.CreateTargetControl("", ident, "rdc-cli", True)` → `tc`
    - If `trigger`: calls `tc.TriggerCapture(1)` — else if `frame` is set: calls `tc.QueueCapture(frame, 1)`
    - Message loop: calls `tc.ReceiveMessage(None)` until `NewCapture` message received or `Connected()` is False or timeout expires
    - On `NewCapture`: populates `CaptureResult` from `msg.newCapture` fields; calls `tc.Shutdown()`; returns success result
    - On timeout/disconnect: calls `tc.Shutdown()`; returns failure result

- [ ] **B2** Rewrite `src/rdc/commands/capture.py`:
  - Preserve `_find_renderdoccmd() -> Path | None` function unchanged (fallback path)
  - Add 12 `--capture-*` options mapping to `CaptureOptions` fields (e.g. `--capture-callstacks / --no-capture-callstacks`, `--api-validation / --no-api-validation`, etc.)
  - Add `--trigger` flag: use `TriggerCapture` instead of `QueueCapture`
  - Add `--auto-open` flag: after successful capture, invoke `rdc open <path>` via `subprocess`
  - Add `--json / --no-json` flag: output `CaptureResult` as JSON
  - Primary path: `find_renderdoc()` → import `renderdoc` → `build_capture_options(...)` → `execute_and_capture(...)` → print result
  - Fallback path: if `find_renderdoc()` returns `None` → `_find_renderdoccmd()` → `subprocess.run([renderdoccmd, "capture", ...])` with available flags mapped to renderdoccmd equivalents

---

### Agent 2 (Branch B): CaptureFile Helpers

#### Phase A — Tests first

- [ ] **A3** Create `tests/unit/test_capturefile_handlers.py`:
  - `test_thumbnail_success` — mock `state.cap.GetThumbnail(...)` returning `Thumbnail(data=b"abc", width=4, height=4)`; call `_handle_thumbnail`; assert response has `width=4`, `height=4`, `data` is base64 string
  - `test_thumbnail_empty` — `GetThumbnail` returns `Thumbnail(data=b"", width=0, height=0)`; assert response `data` is `""` or `null`, `width=0`
  - `test_thumbnail_maxsize` — pass `params={"maxsize": 128}`; verify `GetThumbnail` called with `maxsize=128`
  - `test_gpus_success` — `GetAvailableGPUs()` returns 2 `GPUDevice` entries; assert response `gpus` list has 2 items with `name`, `vendor`, `deviceID`, `driver`
  - `test_gpus_empty` — `GetAvailableGPUs()` returns `[]`; assert `gpus=[]`
  - `test_sections_success` — `GetSectionCount()=2`; `GetSectionProperties(0)` and `GetSectionProperties(1)` return different sections; assert response `sections` list has 2 items
  - `test_section_content_text` — `FindSectionByName("Notes")=0`; `GetSectionContents(0)=b"hello"`; assert response `contents` is `"hello"` (decoded UTF-8)
  - `test_section_content_binary` — contents include non-UTF-8 bytes; assert response `contents` is base64 encoded and `encoding="base64"` field present
  - `test_section_not_found` — `FindSectionByName("Missing")=-1`; assert error `-32002`

- [ ] **A4** Create `tests/unit/test_capturefile_commands.py`:
  - `test_thumbnail_cmd` — monkeypatch `call()` in `rdc.commands.capturefile`; mock returns thumbnail data; invoke `rdc thumbnail`; assert exit 0 and stdout contains dimensions
  - `test_gpus_cmd` — mock returns GPU list; invoke `rdc gpus`; assert exit 0 and GPU names in stdout
  - `test_sections_cmd` — mock returns sections list; invoke `rdc sections`; assert exit 0 and section names in stdout
  - `test_section_cmd` — mock returns section content; invoke `rdc section Notes`; assert exit 0 and content in stdout
  - `test_thumbnail_cmd_json` — `--json` flag; assert stdout is valid JSON
  - `test_gpus_cmd_json` — `--json` flag; assert stdout is valid JSON

#### Phase B — Implementation

- [ ] **B3** Create `src/rdc/handlers/capturefile.py`:
  - Follow `src/rdc/handlers/texture.py` pattern for imports and response helpers
  - `_handle_thumbnail(request_id, params, state)`:
    - Validate `state.cap is not None` → error `-32002`
    - Extract `maxsize = params.get("maxsize", 0)` and `file_type = params.get("fileType", 0)`
    - Call `state.cap.GetThumbnail(file_type, maxsize)` → `Thumbnail`
    - Return `{"data": base64.b64encode(td.data).decode() if td.data else "", "width": td.width, "height": td.height}`
  - `_handle_gpus(request_id, params, state)`:
    - Validate `state.cap is not None` → error `-32002`
    - Call `state.cap.GetAvailableGPUs()`
    - Return `{"gpus": [{"name": g.name, "vendor": g.vendor, "deviceID": g.deviceID, "driver": g.driver} for g in gpus]}`
  - `_handle_sections(request_id, params, state)`:
    - Validate `state.cap is not None` → error `-32002`
    - Iterate `range(state.cap.GetSectionCount())`; call `GetSectionProperties(i)` for each
    - Return `{"sections": [{"index": i, "name": p.name, "type": int(p.type), "version": p.version, "compressedSize": p.compressedSize, "uncompressedSize": p.uncompressedSize} for i, p in enumerate(props)]}`
  - `_handle_section_content(request_id, params, state)`:
    - Validate `state.cap is not None` → error `-32002`
    - Extract `name = params.get("name")` → error `-32002` if missing
    - Call `state.cap.FindSectionByName(name)` → `idx`; if `idx < 0` → error `-32002` with `"section not found"`
    - Call `state.cap.GetSectionContents(idx)` → `raw: bytes`
    - Try UTF-8 decode; if success return `{"name": name, "contents": text, "encoding": "utf-8"}`; else return `{"name": name, "contents": base64.b64encode(raw).decode(), "encoding": "base64"}`
  - Export `HANDLERS: dict[str, Any]` mapping method names to handlers: `"capture_thumbnail"`, `"capture_gpus"`, `"capture_sections"`, `"capture_section_content"`

- [ ] **B4** Create `src/rdc/commands/capturefile.py`:
  - Follow `src/rdc/commands/export.py` pattern for imports and `call()` helper usage
  - `thumbnail_cmd` (`rdc thumbnail`): option `--maxsize INT` (default 0), `--file-type INT` (default 0), `--json / --no-json`; calls `"capture_thumbnail"`; default output: `"thumbnail: {width}x{height} ({len} bytes)"`
  - `gpus_cmd` (`rdc gpus`): option `--json / --no-json`; calls `"capture_gpus"`; default output: one line per GPU `"{name}  ({vendor}  driver={driver})"`
  - `sections_cmd` (`rdc sections`): option `--json / --no-json`; calls `"capture_sections"`; default output: one line per section `"[{index}] {name}  (type={type}, {uncompressedSize} bytes)"`
  - `section_cmd` (`rdc section <name>`): argument `name` (str); option `--json / --no-json`; calls `"capture_section_content"`; default output: prints `contents` field directly

---

### Merge Step (after Agent 1 and Agent 2 branches are both complete)

- [x] **B5** Update `src/rdc/cli.py` — import and register 4 CaptureFile commands:
  ```python
  from rdc.commands.capturefile import (
      gpus_cmd,
      section_cmd,
      sections_cmd,
      thumbnail_cmd,
  )
  ```
  Add 4 `main.add_command(...)` lines after existing command registrations. **(DONE)**

- [x] **B6** Update `src/rdc/daemon_server.py` — import and merge CaptureFile handlers: **(DONE)**
  ```python
  from rdc.handlers.capturefile import HANDLERS as _CAPTUREFILE_HANDLERS
  ```
  Merge `**_CAPTUREFILE_HANDLERS` into `_DISPATCH`.

- [x] **B7** Update `src/rdc/handlers/query.py` — enhance `_handle_info` to include 3 new fields from `state.cap`: **(DONE)**
  - Add `has_callstacks: bool` from `state.cap.HasCallstacks()` (if `state.cap is not None`, else omit)
  - Add `machine_ident: str` from `state.cap.RecordedMachineIdent()` (if `state.cap is not None`, else omit)
  - Add `timestamp_base: int` from `state.cap.TimestampBase()` (if `state.cap is not None`, else omit)

---

### Phase C — Verify (after merge step)

- [ ] **C1** `pixi run lint` — zero errors
- [ ] **C2** `pixi run test` — all tests pass, zero failures
- [ ] **C3** Manual GPU tests: `rdc capture <app>`, `rdc thumbnail`, `rdc gpus`, `rdc sections`, `rdc section FrameCapture`, `rdc info` (verify new fields)
- [ ] **C4** Fallback test: `RENDERDOC_PYTHON_PATH=/nonexistent rdc capture <app>` — verify fallback to renderdoccmd path is taken

---

### File Conflict Analysis (PR 2)

| File | Change type | Conflicts with |
|------|-------------|----------------|
| `src/rdc/capture_core.py` | New file | None |
| `src/rdc/commands/capture.py` | Rewrite | None (Branch A only) |
| `tests/unit/test_capture_core.py` | New file | None |
| `tests/unit/test_capture.py` | Modified | None (Branch A only) |
| `src/rdc/handlers/capturefile.py` | New file | None |
| `src/rdc/commands/capturefile.py` | New file | None |
| `tests/unit/test_capturefile_handlers.py` | New file | None |
| `tests/unit/test_capturefile_commands.py` | New file | None |
| `src/rdc/cli.py` | Modified (~5 lines) | Merge step only |
| `src/rdc/daemon_server.py` | Modified (~3 lines) | Merge step only |
| `src/rdc/handlers/query.py` | Modified (~6 lines) | Merge step only |

Branch A and Branch B have **zero file conflicts** — safe for parallel worktree execution.

---

## PR 3: TargetControl Commands

### Branch
`feature/5b-target-control` (base: PR 2 merged)

### Context
Add persistent `TargetControlState` (ident, target name, pid, api, connected_at) following the `session_state.py` pattern. Implement four commands (`attach`, `capture-trigger`, `capture-list`, `capture-copy`) that load state, call `CreateTargetControl`, perform one operation, and call `Shutdown()`.

---

### Phase A — Tests first

- [ ] **A1** Create `tests/unit/test_target_state.py`:
  - `test_save_load` — save `TargetControlState(ident=12345, target_name="myapp", pid=9999, api="Vulkan", connected_at=1700000000.0)`; load by ident; assert all fields equal
  - `test_load_missing` — load nonexistent ident; assert returns `None`
  - `test_delete` — save then delete; load after delete returns `None`
  - `test_corrupt_file` — write garbage JSON to state file path; load returns `None` (no exception)

- [ ] **A2** Create `tests/unit/test_capture_control.py`:
  All tests monkeypatch `find_renderdoc` in `rdc.discover` to return a mock module (NOT `load_session`/`send_request` — PR 3 commands bypass the daemon and call `CreateTargetControl` directly). Also monkeypatch `Path.home()` to `tmp_path` for state file isolation.
  - `test_attach_success` — mock `find_renderdoc()` returning mock_renderdoc module; mock module's `CreateTargetControl` returning `MockTargetControl` with `GetTarget()="myapp"`, `GetPID()=9999`, `GetAPI()="Vulkan"`; invoke `rdc attach 12345`; assert exit 0, state saved, stdout contains target name
  - `test_attach_connection_failed` — `MockTargetControl.Connected()` returns `False` immediately; assert exit 1 with connection error message
  - `test_capture_trigger_success` — save `TargetControlState` for ident `12345`; mock `find_renderdoc()` + `CreateTargetControl` returning `MockTargetControl`; invoke `rdc capture-trigger`; assert `TriggerCapture(1)` called; exit 0
  - `test_capture_trigger_no_state` — no saved state; invoke `rdc capture-trigger`; assert exit 1 with "no active target" message
  - `test_capture_list_success` — save state; mock `ReceiveMessage` returning one `NewCapture` message then `Noop` repeatedly; invoke `rdc capture-list`; assert exit 0 and capture info in stdout
  - `test_capture_copy_success` — save state; mock `CopyCapture`; invoke `rdc capture-copy 0 /tmp/out.rdc`; assert `CopyCapture(0, "/tmp/out.rdc")` called; exit 0
  - `test_capture_copy_no_state` — no saved state; invoke `rdc capture-copy 0 /tmp/out.rdc`; assert exit 1

---

### Phase B — Implementation

- [ ] **B1** Create `src/rdc/target_state.py`:
  - Follow `src/rdc/session_state.py` pattern exactly
  - Dataclass `TargetControlState` with fields: `ident: int`, `target_name: str`, `pid: int`, `api: str`, `connected_at: float`
  - `_state_path(ident: int) -> Path`: returns `Path.home() / ".rdc" / "target" / f"{ident}.json"`
  - `save_target_state(state: TargetControlState) -> None`: serialize to JSON, write to `_state_path(state.ident)`
  - `load_target_state(ident: int) -> TargetControlState | None`: read and deserialize; return `None` on missing or corrupt file
  - `delete_target_state(ident: int) -> None`: remove file if exists; no error if missing

- [ ] **B2** Create `src/rdc/commands/capture_control.py`:
  - `attach_cmd` (`rdc attach <ident>`): argument `ident` (int); option `--host` (str, default `"localhost"`); calls `find_renderdoc()` → import `renderdoc` → `CreateTargetControl(host, ident, "rdc-cli", False)` → verify `tc.Connected()`; save `TargetControlState`; echo target/pid/api; call `tc.Shutdown()`
  - `capture_trigger_cmd` (`rdc capture-trigger`): option `--ident INT` (default: load from saved state); option `--num-frames INT` (default 1); option `--host STR` (default `"localhost"`); loads `TargetControlState` if no `--ident`; calls `CreateTargetControl` → `TriggerCapture(num_frames)` → `Shutdown()`; echo confirmation
  - `capture_list_cmd` (`rdc capture-list`): option `--ident INT`, `--host STR`, `--timeout FLOAT` (default 5.0), `--json / --no-json`; loads state if no `--ident`; calls `CreateTargetControl` → message loop collecting `NewCapture` messages until timeout → `Shutdown()`; prints capture list
  - `capture_copy_cmd` (`rdc capture-copy <capture_id> <dest>`): arguments `capture_id` (int), `dest` (str); option `--ident INT`, `--host STR`; loads state if no `--ident`; calls `CreateTargetControl` → `CopyCapture(capture_id, dest)` → `Shutdown()`; echo confirmation

- [ ] **B3** Update `src/rdc/cli.py` — import and register 4 commands:
  ```python
  from rdc.commands.capture_control import (
      attach_cmd,
      capture_copy_cmd,
      capture_list_cmd,
      capture_trigger_cmd,
  )
  ```
  Add 4 `main.add_command(...)` lines.

---

### Phase C — Verify

- [ ] **C1** `pixi run lint` — zero errors
- [ ] **C2** `pixi run test` — all tests pass, zero failures
- [ ] **C3** Manual TargetControl test: `rdc capture --trigger <app>` to start capture with trigger mode; `rdc attach <ident>`; `rdc capture-trigger`; `rdc capture-list`; `rdc capture-copy 0 /tmp/out.rdc`

---

### File Conflict Analysis (PR 3)

| File | Change type | Conflicts with |
|------|-------------|----------------|
| `src/rdc/target_state.py` | New file | None |
| `src/rdc/commands/capture_control.py` | New file | None |
| `tests/unit/test_target_state.py` | New file | None |
| `tests/unit/test_capture_control.py` | New file | None |
| `src/rdc/cli.py` | Modified (~4 lines) | Low risk (additive) |

---

## Reusable Code Reference

| What | Where | Used by |
|------|-------|---------|
| `find_renderdoc()` | `src/rdc/discover.py` | `capture_core.py`, `capture.py`, `capture_control.py` |
| `SessionState` pattern | `src/rdc/session_state.py:14-21` | `target_state.py` |
| `_result_response()` / `_error_response()` | `src/rdc/handlers/_helpers.py` | `capturefile.py` handlers |
| `call()` RPC helper | `src/rdc/commands/_helpers.py:43-74` | `capturefile.py` CLI commands |
| Temp file / base64 pattern | `src/rdc/handlers/texture.py:33-60` | thumbnail handler |
| `_find_renderdoccmd()` | `src/rdc/commands/capture.py:10-22` | Preserve for fallback |

---

## Post-Merge Wrap-up

- [ ] Archive OpenSpec: `mv openspec/changes/2026-02-23-phase5b-capture-unified openspec/changes/archive/`
- [ ] Update Obsidian `进度跟踪.md` — stats, phase status
- [ ] Update Obsidian `Roadmap.md` — milestones, next steps
- [ ] Record decisions/deviations in `归档/决策记录.md` (next D-NNN)
- [ ] Update `MEMORY.md` — phase status, stats

---

## Definition of Done (all 3 PRs merged)

- `pixi run lint && pixi run test` passes with zero failures
- `rdc capture` uses Python API (`ExecuteAndInject` + message loop) with 12 `CaptureOptions` flags; fallback to `renderdoccmd` when Python module unavailable
- `rdc thumbnail`, `rdc gpus`, `rdc sections`, `rdc section <name>` all work and return correct data
- `rdc info` output includes `has_callstacks`, `machine_ident`, `timestamp_base` fields
- `rdc attach`, `rdc capture-trigger`, `rdc capture-list`, `rdc capture-copy` all work with saved `TargetControlState`
- All new features have unit test coverage; no existing tests regressed
- Manual GPU tests pass on RTX 3080 Ti
