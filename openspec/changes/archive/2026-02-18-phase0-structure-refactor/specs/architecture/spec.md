## ADDED Requirements

### Requirement: Layered command architecture
Command modules MUST delegate business logic to service modules.

#### Scenario: Session command delegates to service
- **WHEN** `rdc open/status/goto/close` is executed
- **THEN** command handlers call service functions
- **AND** commands remain thin adapters for I/O and argument parsing
