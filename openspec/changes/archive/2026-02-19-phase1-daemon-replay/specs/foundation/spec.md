## ADDED Requirements

### Requirement: TSV output formatter
The CLI MUST provide a TSV formatter that produces tab-separated output compliant
with the design principles: raw numbers, dash for empty fields, escaped tabs and
newlines, optional header row, footer to stderr.

#### Scenario: TSV list output with header
- **WHEN** a list command produces output
- **THEN** the first line is a tab-separated header row
- **AND** subsequent lines are tab-separated data rows
- **AND** empty fields are represented as `-`
- **AND** numeric fields are raw integers (e.g. `1200000` not `1.2M`)

#### Scenario: TSV with --no-header
- **WHEN** the user passes --no-header
- **THEN** the header row is omitted

#### Scenario: Footer to stderr
- **WHEN** a command produces a summary footer
- **THEN** the footer is written to stderr, not stdout

### Requirement: JSON output formatter
The CLI MUST provide JSON and JSONL formatters for structured output.

#### Scenario: JSON output
- **WHEN** the user passes --json
- **THEN** output is a single formatted JSON document

#### Scenario: JSONL output
- **WHEN** the user passes --jsonl
- **THEN** output is one JSON object per line

### Requirement: RenderDoc adapter extensions
The adapter layer MUST expose convenience methods for common ReplayController
operations used by Phase 1 commands.

#### Scenario: Adapter wraps pipeline state access
- **WHEN** a command needs pipeline state
- **THEN** it calls adapter.get_pipeline_state() which delegates to controller.GetPipelineState()

#### Scenario: Adapter wraps SetFrameEvent
- **WHEN** a command needs to move to a specific event
- **THEN** it calls adapter.set_frame_event(eid) which delegates to controller.SetFrameEvent(eid, True)
