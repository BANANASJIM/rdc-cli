# Proposal: `rdc log`

## Summary

Add `rdc log` command to output debug/validation messages from the capture.

## Motivation

GPU captures may contain validation layer warnings, errors, and performance
hints. Currently there is no CLI way to inspect them — users must open RenderDoc
GUI. `rdc log` exposes these messages for scripted analysis and CI integration.

## Design

### Daemon Handler

Method `log` calls `controller.GetDebugMessages()`, maps severity enum
(0=HIGH, 1=MEDIUM, 2=LOW, 3=INFO), and supports optional `level` and `eid`
filter parameters. Returns `{messages: [{level, eid, message}]}`.

### CLI Command

`rdc log` — TSV output with columns LEVEL, EID, MESSAGE.
`--level` filters by severity. `--eid` filters by event ID.
`--json` outputs full JSON list. Empty messages list is not an error.

## Output Format

```
LEVEL	EID	MESSAGE
ERROR	0	[VUID-123] Descriptor set 2 not bound
WARN	142	[PERF] Suboptimal image layout transition
```
