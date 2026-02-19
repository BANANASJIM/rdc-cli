# Proposal: `rdc pass <index|name>`

## Summary

Add `rdc pass` command to show detailed metadata for a single render pass,
including begin/end EID range, draw/dispatch counts, triangle totals, and
color/depth attachment info.

## Motivation

`rdc passes` lists all passes but lacks detail. Users need per-pass drill-down
to understand pass scope, cost, and render target setup without opening a GUI.

## Design

### Query Service

`get_pass_detail(actions, sf, identifier)` builds an enriched pass list from
the action tree, then looks up by index (int) or name (str, case-insensitive).

Returns: `{name, begin_eid, end_eid, draws, dispatches, triangles}`

### Daemon Handler

Method `pass` accepts `index` (int) or `name` (str). Calls `get_pass_detail()`,
then fetches attachment info via `SetFrameEvent(begin_eid)` +
`GetPipelineState()` + `GetOutputTargets()` / `GetDepthTarget()`.

### CLI Command

`rdc pass <identifier>` — key-value output (Pass, Begin EID, End EID, etc).
`--json` flag returns full dict. Identifier parsed as int if numeric, else name.

## Output Format

```
Pass:           GBuffer
Begin EID:      90
End EID:        450
Draw Calls:     450
Dispatches:     0
Triangles:      4800000
```
