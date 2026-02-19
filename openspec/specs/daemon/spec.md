# daemon Specification

## Purpose
The daemon is a long-lived process that hosts a RenderDoc ReplayController for
an open capture file. It accepts JSON-RPC 2.0 requests over a localhost TCP
socket and exposes query methods for capture inspection. All session-aware CLI
commands communicate with the daemon via this protocol.

## Requirements

### Requirement: JSON-RPC transport
The codebase MUST provide JSON-RPC 2.0 helper functions for daemon command payloads.
Every request MUST include a `_token` parameter for authentication.

#### Scenario: Build ping request
- **WHEN** client builds a ping request
- **THEN** payload contains `jsonrpc: 2.0`, method `ping`, and an integer id

#### Scenario: Build shutdown request
- **WHEN** client builds a shutdown request
- **THEN** payload contains `jsonrpc: 2.0`, method `shutdown`, and an integer id

### Requirement: Replay lifecycle
The daemon MUST load the renderdoc module, open a capture file, and hold a live
ReplayController for the duration of the session.

#### Scenario: Open starts daemon and stores session metadata
- **WHEN** the user runs `rdc open capture.rdc`
- **THEN** a daemon process starts on localhost with a random port and token
- **AND** session file stores pid/port/token/capture/current_eid
- **AND** daemon calls InitialiseReplay, OpenCaptureFile, OpenCapture

#### Scenario: Shutdown releases resources
- **WHEN** the daemon receives a `shutdown` request
- **THEN** it calls controller.Shutdown() and cap.Shutdown()
- **AND** the process exits

### Requirement: Navigation methods
The daemon MUST support event navigation with SetFrameEvent caching.

#### Scenario: Status and goto go through daemon
- **WHEN** the user runs `rdc status` or `rdc goto <eid>`
- **THEN** command sends JSON-RPC request to daemon with session token
- **AND** daemon returns current state or applies eid update

#### Scenario: SetFrameEvent caching
- **WHEN** `goto` is called with the same EID as current
- **THEN** the daemon skips the redundant SetFrameEvent call

### Requirement: Capture overview methods
The daemon MUST expose methods for capture-level queries.

#### Method: `info`
- **Returns** capture metadata: file path, API name, event count, draw/dispatch/clear/copy breakdown

#### Method: `stats`
- **Returns** per-pass breakdown (draws, dispatches, triangles, RT dimensions, attachments) and top draws by triangle count

#### Method: `events`
- **Params** optional `type`, `filter`, `range`, `limit`
- **Returns** list of events with eid, type, name

#### Method: `draws`
- **Params** optional `pass`, `sort`, `limit`
- **Returns** list of draw calls with eid, type, triangles, instances, pass, marker; plus summary string

#### Method: `event`
- **Params** `eid` (required)
- **Returns** single event detail with API call name and structured parameters

#### Method: `draw`
- **Params** `eid` (optional, defaults to current)
- **Returns** draw call detail with event, type, marker, triangles, instances

### Requirement: Count and shader-map methods

#### Method: `count`
- **Params** `what` (draws|events|resources|triangles|passes|dispatches|clears), optional `pass`
- **Returns** `{"value": int}`

#### Method: `shader_map`
- **Returns** list of rows mapping EID to shader ResourceId per stage (vs/hs/ds/gs/ps/cs)

### Requirement: Pipeline and shader inspection methods

#### Method: `pipeline`
- **Params** optional `eid`, optional `section` (vs/hs/ds/gs/ps/cs)
- **Returns** pipeline state row (eid, api, topology, graphics/compute pipeline objects), with optional section detail

#### Method: `bindings`
- **Params** optional `eid`, optional `binding` (filter by slot index)
- **Returns** list of descriptor binding rows (eid, stage, kind, slot, name)

#### Method: `shader`
- **Params** optional `eid`, `stage` (default ps)
- **Returns** shader metadata row (eid, stage, shader id, entry point, ro/rw/cbuffer counts)

#### Method: `shaders`
- **Returns** inventory of unique shaders with shader id, stages used, use count

#### Method: `shader_targets`
- **Returns** list of available disassembly target format strings

#### Method: `shader_reflect`
- **Params** optional `eid`, `stage`
- **Returns** input/output signatures and constant block metadata

#### Method: `shader_constants`
- **Params** optional `eid`, `stage`
- **Returns** constant buffer data (name, bind point, size, hex data)

#### Method: `shader_source`
- **Params** optional `eid`, `stage`
- **Returns** debug source code (falls back to disassembly if unavailable)

#### Method: `shader_disasm`
- **Params** optional `eid`, `stage`, `target`
- **Returns** disassembly text for the specified format

#### Method: `shader_all`
- **Params** optional `eid`
- **Returns** all bound shader stages with metadata (stage, shader id, entry, ro/rw/cbuffer counts)

### Requirement: Resource and pass inspection methods

#### Method: `resources`
- **Returns** list of all resources (id, type, name, width, height, depth, format)

#### Method: `resource`
- **Params** `id` (required)
- **Returns** detailed properties for a single resource

#### Method: `passes`
- **Returns** render pass hierarchy tree with pass names, child structure, and draw counts

