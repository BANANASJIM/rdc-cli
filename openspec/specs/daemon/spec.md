# daemon Specification

## Purpose
TBD - created by archiving change phase0-daemon-protocol. Update Purpose after archive.
## Requirements
### Requirement: JSON-RPC skeleton helpers
The codebase MUST provide JSON-RPC 2.0 helper functions for daemon command payloads.

#### Scenario: Build ping request
- **WHEN** client builds a ping request
- **THEN** payload contains `jsonrpc: 2.0`, method `ping`, and an integer id

#### Scenario: Build shutdown request
- **WHEN** client builds a shutdown request
- **THEN** payload contains `jsonrpc: 2.0`, method `shutdown`, and an integer id

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

