## ADDED Requirements

### Requirement: Pipeline Query Methods
The daemon SHALL expose read-only JSON-RPC methods for pipeline and shader inspection.

#### Scenario: Query pipeline
- **WHEN** client requests `pipeline` with optional `eid` and `section`
- **THEN** daemon returns pipeline state summary for that event

#### Scenario: Query bindings
- **WHEN** client requests `bindings` with optional `eid`
- **THEN** daemon returns bound resources grouped by stage and slot

#### Scenario: Query shader
- **WHEN** client requests `shader` with optional `eid` and required/implicit stage
- **THEN** daemon returns shader metadata for the selected stage

#### Scenario: Query shaders inventory
- **WHEN** client requests `shaders`
- **THEN** daemon returns unique shader list for the loaded capture
