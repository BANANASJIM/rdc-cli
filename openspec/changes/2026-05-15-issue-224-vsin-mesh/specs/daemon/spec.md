## ADDED Requirements

### Requirement: VS-In Mesh Stage Support
The daemon SHALL accept `vs-in` as a valid mesh stage identifier in addition to the
existing `vs-out` and `gs-out` stages.

#### Scenario: VS-In Stage Accepted
- **WHEN** client requests `mesh_data` with `stage` equal to `"vs-in"`
- **THEN** daemon calls `GetPostVSData` with stage integer `0` (`MeshDataStage.VSIn`)
- **THEN** daemon decodes the returned `MeshFormat` using the existing geometry decode path
- **THEN** daemon returns vertex positions (and any available attributes) in OBJ format

#### Scenario: VS-In on Non-Draw Event
- **WHEN** client requests `mesh_data` with `stage` equal to `"vs-in"` for a non-draw event
  (or any event where the IA/VSIn stage produced no data)
- **THEN** `GetPostVSData` returns a `MeshFormat` with zero `vertexResourceId` or zero `vertexByteStride`
- **THEN** daemon returns JSON-RPC error `-32001` with message `"no PostVS data at this event"`
- **NOTE** this is the same error contract `vs-out` and `gs-out` already have; no silent-empty
  path exists

#### Scenario: Invalid Stage String
- **WHEN** client requests `mesh_data` with an unrecognized `stage` value
- **THEN** daemon returns an error response
- **AND** the error message SHALL list `vs-in`, `vs-out`, and `gs-out` as valid values
- **NOTE** the error string at ~buffer.py:283 currently omits `vs-in`; this change requires
  updating it to `"invalid stage <name>; use vs-in, vs-out or gs-out"`

## MODIFIED Requirements

### Requirement: Mesh CLI Stage Option
The `rdc mesh` CLI command SHALL accept `vs-in` as a valid `--stage` argument.

#### Scenario: VS-In CLI Invocation
- **WHEN** user runs `rdc mesh <eid> --stage vs-in`
- **THEN** CLI forwards `stage: vs-in` to the daemon `mesh_data` handler
- **THEN** CLI writes the returned OBJ content to stdout

#### Scenario: Unknown Stage Rejected at CLI
- **WHEN** user supplies an unrecognized `--stage` value
- **THEN** Click validation rejects the input with exit code 2 before any daemon call is made
