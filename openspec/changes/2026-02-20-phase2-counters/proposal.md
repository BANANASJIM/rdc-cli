# Proposal: phase2-counters

## Summary

Add `rdc counters` command, `counter_list` and `counter_fetch` daemon handlers,
and `/counters/list` VFS leaf to expose GPU performance counter data via
`EnumerateCounters`, `DescribeCounter`, and `FetchCounters`.

## Motivation

GPU performance counters provide hardware-level metrics (GPU duration,
primitive counts, shader invocations) that are essential for identifying
bottlenecks. RenderDoc exposes 14+ built-in counters per backend; currently
rdc-cli has no way to surface them.

`rdc counters --list` answers "what metrics are available?"; `rdc counters`
(or `--eid EID`) answers "what are the measured values for this capture?".
Both outputs are pipeable TSV, making them trivially composable with `awk`,
`sort`, and other tools for quick per-draw profiling.

## Design

### Daemon handler: `counter_list`

**Params:** none

**Response:**
```json
{
  "counters": [
    {
      "id": 1,
      "name": "GPU Duration",
      "unit": "Seconds",
      "type": "Float",
      "category": "Vulkan Built-in",
      "description": "Time taken for this event on the GPU, as measured by its own timer."
    },
    {
      "id": 2,
      "name": "Input Vertices Read",
      "unit": "Absolute",
      "type": "UInt",
      "category": "Vulkan Built-in",
      "description": "..."
    }
  ],
  "total": 14
}
```

Implementation: call `controller.EnumerateCounters()` → for each `GPUCounter`
value call `controller.DescribeCounter(id)` → map `CounterDescription` fields:
- `resultType`: `CompType.Float` → `"Float"`, `CompType.UInt` → `"UInt"`
- `unit`: `CounterUnit` enum → `.name` string

### Daemon handler: `counter_fetch`

**Params:**
- `eid` (int, optional) — if provided, filter results to that event ID only
- `names` (list[str], optional) — filter counters by name substring (case-insensitive)

**Response:**
```json
{
  "rows": [
    {"eid": 11, "counter": "GPU Duration",        "value": 1.6384e-05, "unit": "Seconds"},
    {"eid": 11, "counter": "Input Vertices Read",  "value": 36,         "unit": "Absolute"}
  ],
  "total": 2
}
```

Implementation:
1. Enumerate all counters (same as `counter_list`).
2. Apply `names` filter to get the counter ID list to fetch.
3. Call `controller.FetchCounters(counter_ids)` → list of `CounterResult`.
4. For each result, resolve counter name + unit from the description cache.
5. Read value: `Float`/8-byte → `.d` (double), `UInt`/8-byte → `.u64`.
6. If `eid` param provided, filter rows to matching `eventId` only.

### VFS

```
/counters/          → directory listing counter IDs
/counters/list      → leaf, handler "counter_list" (TSV of available counters)
```

No per-counter sub-nodes needed; the list is small (14 built-in) and returned
as a single response. `counter_fetch` is not exposed as a VFS leaf because it
requires mutable params (`eid`, `names`) better handled by the CLI command.

### CLI: `rdc counters`

```
rdc counters --list                    # enumerate available counters
rdc counters                           # fetch values for all draw events
rdc counters --eid 11                  # fetch values for event 11 only
rdc counters --name "Duration"         # filter counters by name substring
rdc counters --eid 11 --name "GPU"     # combined filter
rdc counters --list --json             # JSON output
rdc counters --json                    # JSON output
```

**`--list` output (TSV):**
```
ID	NAME	UNIT	TYPE	CATEGORY
1	GPU Duration	Seconds	Float	Vulkan Built-in
2	Input Vertices Read	Absolute	UInt	Vulkan Built-in
3	IAPrimitives	Absolute	UInt	Vulkan Built-in
```

**Default / `--eid` output (TSV):**
```
EID	COUNTER	VALUE	UNIT
11	GPU Duration	1.6384e-05	Seconds
11	Input Vertices Read	36	Absolute
11	IAPrimitives	12	Absolute
```

### VFS extractor

`rdc cat /counters/list` outputs the same TSV as `rdc counters --list`.

### Error handling

- No replay loaded → `-32002`
- `eid` provided but not found in results → `-32001`
- `FetchCounters` returns empty or raises → `-32003` with message
- `--name` matches no counters → empty TSV body (header only), not error

## Scope

**In scope:**
- `counter_list` daemon handler (enumerate + describe)
- `counter_fetch` daemon handler (fetch values, optional eid/names filter)
- VFS route `/counters/` directory + `/counters/list` leaf
- `rdc counters` CLI command with `--list`, `--eid`, `--name`, `--json`
- TSV formatter for list and fetch output
- Mock `EnumerateCounters`, `DescribeCounter`, `FetchCounters` in mock_renderdoc

**Out of scope:**
- Vendor-specific counter extensions (AMD/Intel/Nvidia plugins)
- Counter comparison across multiple frames or captures
- Counter-based anomaly detection or threshold alerting
