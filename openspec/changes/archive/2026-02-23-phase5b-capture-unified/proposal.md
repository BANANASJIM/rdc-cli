# Proposal: phase5b-capture-unified

**Date:** 2026-02-23
**Phase:** 5B
**Status:** Reviewed

---

## Problem Statement

`rdc capture` is currently a thin subprocess wrapper that shells out to `renderdoccmd capture`. This approach has three concrete deficiencies:

1. **CaptureOptions are inaccessible.** The RenderDoc Python API exposes 12 tunable flags (`ApiValidation`, `CaptureCallstacks`, `HookChildProcesses`, `RefAllResources`, `SoftMemoryLimit`, etc.) through the `CaptureOptions` struct passed to `ExecuteAndInject()`. The `renderdoccmd` wrapper exposes a subset of these through opaque `--opt-*` passthrough flags that are not validated, not documented in `rdc capture --help`, and not reflected in structured output.

2. **No structured output.** The subprocess writes human-readable text to stdout from within `renderdoccmd`; `rdc capture` captures none of it. There is no `--json` path that returns the capture file path, byte size, frame number, or API name as machine-readable data. This blocks AI-agent and CI workflows that need to open the resulting `.rdc` file programmatically.

3. **CaptureFile helpers are missing.** Four methods on the `CaptureFile` object (`GetThumbnail`, `GetAvailableGPUs`, `GetSectionCount/Properties/Contents`, `FindSectionByName`) are not exposed as CLI commands or JSON-RPC handlers. Users who need thumbnail extraction, GPU enumeration, or section inspection must write custom Python scripts.

---

## Proposed Solution

Phase 5B replaces the `renderdoccmd` subprocess wrapper with a Python API implementation using `renderdoc.ExecuteAndInject()` and adds a TargetControl command layer. It is split into three sequential PRs to keep review surfaces small and each PR independently mergeable.

> **Implementation Status (2026-02-23):** PR 1 (mock extensions) is merged (commit b3cc2fc). PR 2 production code is ~90% complete (capture_core.py, commands/capture.py rewrite, handlers/capturefile.py, commands/capturefile.py all implemented; embed-deps removed after real API testing confirmed HasPendingDependencies/EmbedDependenciesIntoCapture do not exist on CaptureFile). Remaining PR 2 work: unit tests. PR 3 (TargetControl commands) is not yet started.

### PR 1: Mock Extensions + Foundation (`feature/5b-mock-foundation`)

Extends `tests/mocks/mock_renderdoc.py` with all types required by PRs 2 and 3. No production code changes; no new CLI commands. This PR unblocks all downstream unit tests.

**New mock types:**

- `CaptureOptions` — dataclass with camelCase fields matching the RenderDoc struct: `allowFullscreen`, `allowVSync`, `apiValidation`, `captureCallstacks`, `captureCallstacksOnlyActions`, `delayForDebugger`, `verifyBufferAccess`, `hookIntoChildren`, `refAllResources`, `captureAllCmdLists`, `debugOutputMute`, `softMemoryLimit`. All fields default to SWIG zero-init values (False/0). Use `GetDefaultCaptureOptions()` to obtain RenderDoc's recommended defaults.
- `ExecuteResult` — dataclass with `result` (int, 0 = success), `ident` (uint32 target control identifier).
- `TargetControlMessageType` — IntEnum with 11 members: `Unknown=0`, `Disconnected=1`, `Busy=2`, `Noop=3`, `NewCapture=4`, `CaptureCopied=5`, `RegisterAPI=6`, `NewChild=7`, `CaptureProgress=8`, `CapturableWindowCount=9`, `RequestShow=10`.
- `TargetControlMessage` — dataclass with `type` (`TargetControlMessageType`), `newCapture` (`NewCaptureData | None`).
- `NewCaptureData` — dataclass with 11 fields: `captureId` (int), `frameNumber` (int), `path` (str), `byteSize` (int), `timestamp` (int), `thumbnail` (bytes), `thumbWidth` (int), `thumbHeight` (int), `title` (str), `api` (str), `local` (bool).
- `MockTargetControl` — class with `Connected()`, `GetTarget()`, `GetPID()`, `GetAPI()`, `ReceiveMessage(progress)`, `TriggerCapture(numFrames)`, `QueueCapture(frameNumber, numFrames)`, `CopyCapture(captureId, localpath)`, `DeleteCapture(captureId)`, `CycleActiveWindow()`, `Shutdown()`. Configurable via constructor kwargs (`messages`, `copy_result`).
- `Thumbnail` — dataclass with `data` (bytes), `width` (int), `height` (int), `type` (int).
- `GPUDevice` — dataclass with `vendor` (int), `deviceID` (int), `name` (str), `driver` (str), `api` (str).
- `SectionProperties` — dataclass with `name` (str), `type` (int), `flags` (int), `version` (int), `uncompressedSize` (int), `compressedSize` (int).
- `SectionType` — IntEnum with members: `Unknown`, `FrameCapture`, `ResolveDatabase`, `Bookmarks`, `Notes`, `ResourceRenames`, `AMDRGPProfile`, `ExtendedThumbnail`.
- `SectionFlags` — IntFlag with members: `NoFlags=0`, `ASCIIStored=1`, `LZ4Compressed=2`, `ZstdCompressed=4`.

**Mock `CaptureFile` enhancements:**

- `GetThumbnail(type, max_size)` → returns `Thumbnail`.
- `GetAvailableGPUs()` → returns list of `GPUDevice`.
- `GetSectionCount()` → returns int.
- `GetSectionProperties(index)` → returns `SectionProperties`.
- `GetSectionContents(index)` → returns bytes.
- `FindSectionByName(name)` → returns int index or -1.
- `HasCallstacks()` → returns bool.
- `RecordedMachineIdent()` → returns str.
- `TimestampBase()` → returns int.

**Module-level additions:**

- `ExecuteAndInject(app, workingDir, cmdLine, env, capturefile, opts, waitForExit)` → returns `ExecuteResult` (7 params matching real API).
- `CreateTargetControl(URL, ident, clientName, forceConnection)` → returns `MockTargetControl`.
- `GetDefaultCaptureOptions()` → returns a `CaptureOptions` instance with RenderDoc recommended defaults (`allowFullscreen=True`, `allowVSync=True`, `debugOutputMute=True`).

**Deliverable:** smoke-test module `tests/test_mock_extensions.py` that imports all new types and verifies default field values, round-trip method calls, and configurable mock responses.

---

### PR 2: Capture Rewrite + CaptureFile Helpers (`feature/5b-capture-helpers`)

Two non-conflicting implementation branches merged into one PR.

#### Branch A: Capture rewrite

**New `src/rdc/capture_core.py`** — testable service module with no Click dependency:

```python
@dataclass
class CaptureResult:
    success: bool
    path: str = ""
    frame: int = 0
    byte_size: int = 0
    api: str = ""
    local: bool = True
    ident: int = 0  # target control ident, 0 if not used
    pid: int = 0     # target process PID
    error: str = ""
```

- `build_capture_options(opts: dict[str, Any]) -> CaptureOptions` — calls `find_renderdoc()` internally, maps CLI flag names to `CaptureOptions` camelCase field assignments.
- `execute_and_capture(rd, app, args, workdir, output, opts, *, frame, trigger, timeout, wait_for_exit) -> CaptureResult` — calls `renderdoc.ExecuteAndInject(app, workingDir, args, [], output, opts, wait_for_exit)` (7 params), runs the TargetControl message loop until `NewCapture` or timeout, returns `CaptureResult`. The message loop uses `TriggerCapture(1)` by default; `--frame N` switches to `QueueCapture(N, 1)`. The `rd` module is passed explicitly as first parameter.
- `_fallback_renderdoccmd(app, args, output, api_name) -> int` — preserved from the current implementation; called when `renderdoc` module is unavailable. Emits a warning on stderr before falling back.
- `_run_target_control_loop(tc, timeout, trigger_only, frame) -> CaptureResult | None` — inner loop; separated for unit testability.

**Rewritten `src/rdc/commands/capture.py`:**

New options added to `capture_cmd`:

| Flag | Type | Description |
|------|------|-------------|
| `--frame N` | int | Use `QueueCapture(N, 1)` instead of `TriggerCapture(1)` |
| `--trigger` | flag | Inject only; do not auto-capture (for use with `rdc capture-trigger`) |
| `--timeout N` | int | Seconds to wait for capture message (default 60) |
| `--wait-for-exit` | flag | Wait for target process to exit before returning |
| `--auto-open` | flag | Call `rdc open <path>` on captured file after capture |
| `--api-validation` | flag | Set `CaptureOptions.apiValidation = True` |
| `--callstacks` | flag | Set `CaptureOptions.captureCallstacks = True` |
| `--hook-children` | flag | Set `CaptureOptions.hookIntoChildren = True` |
| `--ref-all-resources` | flag | Set `CaptureOptions.refAllResources = True` |
| `--soft-memory-limit N` | int | Set `CaptureOptions.softMemoryLimit = N` (MB) |
| `--delay-for-debugger N` | int | Set `CaptureOptions.delayForDebugger = N` (seconds) |
| `--json` | flag | Output `CaptureResult` as JSON to stdout |

Existing flags retained: `-o/--output`, `--api`, `--list-apis`.

The command attempts the Python API path first. If `renderdoc` is not importable, it falls back to `_fallback_renderdoccmd()` with a `warning:` line on stderr. `--api-validation` and other `CaptureOptions` flags are silently ignored in fallback mode (with a warning).

#### Branch B: CaptureFile helper handlers

**New `src/rdc/handlers/capturefile.py`** following the `handlers/texture.py` pattern:

| Handler function | RPC method | RenderDoc call |
|-----------------|------------|----------------|
| `_handle_thumbnail` | `capture_thumbnail` | `CaptureFile.GetThumbnail(type, max_size)` |
| `_handle_gpus` | `capture_gpus` | `CaptureFile.GetAvailableGPUs()` |
| `_handle_sections` | `capture_sections` | `GetSectionCount()` + `GetSectionProperties(i)` for all sections |
| `_handle_section_content` | `capture_section_content` | `FindSectionByName(name)` + `GetSectionContents(idx)` |

Each handler uses `_result_response()`/`_error_response()` from `handlers/_helpers.py`. Thumbnail handler returns base64-encoded image data with dimensions. Handlers require an open `CaptureFile` object on `DaemonState` (same as session-bound handlers).

**New `src/rdc/commands/capturefile.py`** CLI commands:

| Command | Flags | Description |
|---------|-------|-------------|
| `rdc thumbnail` | `-o path`, `--maxsize N` | Export capture thumbnail; prints output path |
| `rdc gpus` | `--json` | List GPUs available at capture time |
| `rdc sections` | `--json` | List all embedded sections with properties |
| `rdc section <name>` | `-o path` | Extract named section contents to file or stdout |

Each command follows the `load_session` + `send_request` pattern from existing commands in `commands/session.py`.

#### Shared merge step (after both branches):

- Register `capturefile` commands in `src/rdc/cli.py`.
- Register `capture_*` handlers in `src/rdc/daemon_server.py` (`**_CAPTUREFILE_HANDLERS` into `_DISPATCH`).
- Enhance `handlers/query.py` `_handle_info` to include `has_callstacks`, `machine_ident`, `timestamp_base` from `CaptureFile` methods.

---

### PR 3: TargetControl Commands (`feature/5b-target-control`)

**New `src/rdc/target_state.py`** — mirrors `session_state.py`:

- State file: `~/.rdc/target/<ident>.json` (per-ident file) with fields `ident`, `target_name`, `pid`, `api`, `connected_at`.
- `save_target_state(host, ident, pid)`, `load_target_state() -> dict`, `delete_target_state()`.
- Raises `TargetStateError` (subclass of `RdcError`) when no state file exists.

**New `src/rdc/commands/capture_control.py`** CLI commands:

| Command | Description |
|---------|-------------|
| `rdc attach <ident>` | `CreateTargetControl("", ident, "rdc-cli", True)`, save state; prints `attached: ident=<N>` |
| `rdc capture-trigger [--frames N]` | Load state, reconnect, call `TriggerCapture(N)` |
| `rdc capture-list [--timeout N]` | Load state, reconnect, poll `ReceiveMessage()` until timeout; print capture list as TSV or `--json` |
| `rdc capture-copy <id> -o <path>` | Load state, reconnect, `CopyCapture(id, path)` |

Each command reconnects on entry (stateless reconnect model — no persistent daemon socket for TargetControl; each CLI invocation calls `find_renderdoc()` then `CreateTargetControl` directly without going through the daemon). This avoids socket lifecycle complexity and matches how RenderDoc UI handles TargetControl. Tests monkeypatch `find_renderdoc` to return the mock module, NOT `load_session`/`send_request`.

Register `attach`, `capture-trigger`, `capture-list`, `capture-copy` in `src/rdc/cli.py`.

---

## Non-Goals

- `InjectIntoProcess` — not supported on Linux; out of scope.
- Section write (`rdc section --write`) — Phase 5C.
- Format conversion (`rdc convert`) — Phase 5C.
- Remote capture (remote host `--target-host`) — Phase 6.
- Daemon-side TargetControl persistence — each CLI command reconnects; no long-lived daemon socket for TargetControl.
- Headless GPU capture in CI — requires Xvfb + real GPU; documented limitation, not in scope for unit tests.

---

## Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| Frame timing: `QueueCapture(N, 1)` misses target frame | Default to `TriggerCapture(1)` (next frame); document `--frame` semantics and note that frame numbers may not align with visual frames in all APIs |
| Target crash during capture leaves no `.rdc` file | Timeout guard in `_run_target_control_loop`; cleanup on exit; clear error message with exit code 1 |
| Headless CI: `ExecuteAndInject` requires a display | Unit tests monkeypatch `renderdoc.ExecuteAndInject`; GPU integration tests marked `@pytest.mark.gpu` and excluded from default CI |
| `renderdoc` module unavailable on developer machine | `_fallback_renderdoccmd()` preserves current behavior; warning on stderr makes the fallback visible |
| Large capture file delays `CopyCapture` | Default timeout 60 s; `--timeout` flag allows override; document that `CopyCapture` is a local file copy, not network transfer |
| Mock drift: new RenderDoc API version changes struct fields | Mock types match v1.41 field names; any mismatch surfaces in GPU integration tests; documented in `tests/mocks/README` |

---

## Acceptance Criteria

1. `rdc capture /usr/bin/vkcube -o /tmp/test.rdc` executes via Python API (`ExecuteAndInject`) without invoking `renderdoccmd`.
2. `rdc capture /usr/bin/vkcube -o /tmp/test.rdc --api-validation --callstacks` sets the corresponding `CaptureOptions` fields; verified in unit test by monkeypatching `execute_and_capture`.
3. When `renderdoc` is not importable, `rdc capture` falls back to `renderdoccmd` and prints `warning: renderdoc module unavailable, falling back to renderdoccmd` on stderr.
4. `rdc capture ... --json` prints a JSON object with keys `success`, `path`, `frame`, `byte_size`, `api`, `local`.
5. `rdc thumbnail -o /tmp/thumb.jpg` extracts the capture thumbnail; file is written and path is printed.
6. `rdc gpus` lists at least one GPU entry as TSV; `--json` produces a JSON array.
7. `rdc sections` lists all embedded sections; `rdc section <name>` extracts named section content.
8. `rdc info` output includes `has_callstacks`, `machine_ident`, `timestamp_base` fields.
9. `rdc attach <ident>` saves state; `rdc capture-trigger` reconnects and triggers a capture; `rdc capture-list` returns the resulting capture entry; `rdc capture-copy <id> -o <path>` copies it.
10. All new commands have unit tests using the extended mock. Coverage does not drop below the current threshold.
11. `pixi run lint && pixi run test` passes with zero failures after each PR.
