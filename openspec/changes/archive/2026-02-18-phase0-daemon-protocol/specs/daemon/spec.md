## ADDED Requirements

### Requirement: JSON-RPC skeleton helpers
The codebase MUST provide JSON-RPC 2.0 helper functions for daemon command payloads.

#### Scenario: Build ping request
- **WHEN** client builds a ping request
- **THEN** payload contains `jsonrpc: 2.0`, method `ping`, and an integer id

#### Scenario: Build shutdown request
- **WHEN** client builds a shutdown request
- **THEN** payload contains `jsonrpc: 2.0`, method `shutdown`, and an integer id
