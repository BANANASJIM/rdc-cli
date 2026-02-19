## ADDED Requirements

### Requirement: Daemon query methods for events and draws
The daemon MUST expose JSON-RPC methods for querying capture data: info, stats,
events, draws, event, and draw.

#### Scenario: Info method returns capture metadata
- **WHEN** the client sends a `info` JSON-RPC request
- **THEN** the daemon returns API name, GPU, driver, resolution, event count,
  draw call breakdown, resource summary, and render pass count

#### Scenario: Stats method returns per-pass breakdown
- **WHEN** the client sends a `stats` JSON-RPC request
- **THEN** the daemon returns per-pass statistics (draws, dispatches, triangles,
  RT dimensions, attachments), top draws by triangle count, and largest resources

#### Scenario: Events method returns filtered event list
- **WHEN** the client sends an `events` JSON-RPC request with optional type and filter params
- **THEN** the daemon returns a list of events matching the filter criteria

#### Scenario: Draws method returns filtered draw list
- **WHEN** the client sends a `draws` JSON-RPC request with optional pass, sort, limit params
- **THEN** the daemon returns a list of draw calls matching the criteria

#### Scenario: Event method returns single API call detail
- **WHEN** the client sends an `event` JSON-RPC request with eid
- **THEN** the daemon returns the API call name, parameters, and duration from structured data

#### Scenario: Draw method returns draw call detail
- **WHEN** the client sends a `draw` JSON-RPC request with eid
- **THEN** the daemon calls SetFrameEvent and returns pipeline state, bindings,
  shaders, render targets, and rasterizer state
