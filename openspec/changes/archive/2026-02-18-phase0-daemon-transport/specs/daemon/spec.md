## ADDED Requirements

### Requirement: Session command skeleton
Session commands MUST use daemon transport once Phase 0 daemon skeleton is available.

#### Scenario: Open starts daemon and stores session metadata
- **WHEN** the user runs `rdc open capture.rdc`
- **THEN** a daemon process starts on localhost with a random port and token
- **AND** session file stores pid/port/token/capture/current_eid

#### Scenario: Status and goto go through daemon
- **WHEN** the user runs `rdc status` or `rdc goto <eid>`
- **THEN** command sends JSON-RPC request to daemon with session token
- **AND** daemon returns current state or applies eid update
