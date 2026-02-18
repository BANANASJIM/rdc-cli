# session Specification

## Purpose
TBD - created by archiving change phase0-session-skeleton. Update Purpose after archive.
## Requirements
### Requirement: Session command skeleton
The CLI MUST provide temporary Phase 0 session commands backed by a local session file.

#### Scenario: Open creates local session state
- **WHEN** the user runs `rdc open capture.rdc`
- **THEN** a session file is created under `~/.rdc/sessions/default.json`
- **AND** the session stores capture path and `current_eid=0`

#### Scenario: Goto updates current event
- **WHEN** the user runs `rdc goto 142`
- **THEN** `current_eid` in session state becomes `142`
- **AND** `rdc status` shows updated eid

#### Scenario: Close removes session state
- **WHEN** the user runs `rdc close`
- **THEN** the default session file is removed
- **AND** `rdc status` fails until a new `rdc open`

