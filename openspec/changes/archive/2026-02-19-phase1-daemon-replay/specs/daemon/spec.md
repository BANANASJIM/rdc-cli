## MODIFIED Requirements

### Requirement: Session command skeleton
Session commands MUST use daemon transport once Phase 0 daemon skeleton is available.
The daemon MUST load the renderdoc module and hold a live ReplayController for the
duration of the session. SetFrameEvent MUST use incremental-replay caching.

#### Scenario: Open starts daemon and stores session metadata
- **WHEN** the user runs `rdc open capture.rdc`
- **THEN** a daemon process starts on localhost with a random port and token
- **AND** the daemon loads the renderdoc module and opens the capture file
- **AND** session file stores pid/port/token/capture/current_eid

#### Scenario: Status returns live capture metadata
- **WHEN** the user runs `rdc status`
- **THEN** the daemon returns capture path, API name, event count, and current_eid

#### Scenario: Goto calls SetFrameEvent with caching
- **WHEN** the user runs `rdc goto <eid>`
- **THEN** the daemon calls SetFrameEvent(eid, True) on the ReplayController
- **AND** subsequent goto to the same eid skips the SetFrameEvent call (cache hit)

#### Scenario: Goto rejects out-of-range EID
- **WHEN** the user runs `rdc goto <eid>` with eid exceeding the event count
- **THEN** the daemon returns JSON-RPC error code -32002

#### Scenario: Shutdown releases resources without ShutdownReplay
- **WHEN** the user runs `rdc close`
- **THEN** the daemon calls controller.Shutdown() then cap.Shutdown()
- **AND** the daemon does NOT call rd.ShutdownReplay()
- **AND** the daemon process exits

## ADDED Requirements

### Requirement: Daemon graceful fallback without renderdoc
The daemon MUST support a --no-replay flag for environments where the renderdoc
module is unavailable. In this mode, the daemon operates as a skeleton (no GPU
replay) but all transport and session management functions remain operational.

#### Scenario: Daemon starts in no-replay mode
- **WHEN** the daemon is started with --no-replay
- **THEN** the daemon does not attempt to import renderdoc
- **AND** ping, status, goto, and shutdown methods function normally
- **AND** goto updates current_eid in memory without calling SetFrameEvent
