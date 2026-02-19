## ADDED Requirements

### Requirement: Daemon count method
The daemon MUST expose a `count` JSON-RPC method that returns a single integer
for the requested target (draws, events, resources, triangles, passes, dispatches,
clears) with optional pass filter.

#### Scenario: Count draws returns total draw call count
- **WHEN** the client sends a `count` request with `what=draws`
- **THEN** the daemon returns `{"value": <integer>}` with the total draw call count

#### Scenario: Count with pass filter
- **WHEN** the client sends a `count` request with `what=draws` and `pass=GBuffer`
- **THEN** the daemon returns the draw count for that pass only

#### Scenario: Count unknown target
- **WHEN** the client sends a `count` request with an invalid `what` value
- **THEN** the daemon returns a JSON-RPC error

### Requirement: Daemon shader_map method
The daemon MUST expose a `shader_map` JSON-RPC method that returns a per-draw
mapping of EID to shader ResourceId for each stage.

#### Scenario: Shader map returns per-draw shader IDs
- **WHEN** the client sends a `shader_map` request
- **THEN** the daemon iterates all draw calls, collecting bound shader IDs per stage
- **AND** returns rows of {eid, vs, hs, ds, gs, ps, cs} with `-` for unbound stages
