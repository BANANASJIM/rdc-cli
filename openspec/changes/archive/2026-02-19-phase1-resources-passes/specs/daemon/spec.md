## ADDED Requirements

### Requirement: Resource Inspection
The daemon SHALL expose methods to list and inspect GPU resources.

#### Scenario: List Resources
- **WHEN** client requests `resources`
- **THEN** daemon returns a list of all resources in the capture (Textures, Buffers).

#### Scenario: Get Resource Details
- **WHEN** client requests `resource` with `id`
- **THEN** daemon returns detailed properties of the specified resource.
- **IF** `id` does not exist, return error.

### Requirement: Pass Inspection
The daemon SHALL expose methods to inspect the frame structure.

#### Scenario: List Passes
- **WHEN** client requests `passes`
- **THEN** daemon returns a hierarchical view of Render Passes and Marker regions.
