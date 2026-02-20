# Test Plan: phase2-counters

## Scope

### In scope
- Daemon handler `counter_list`: calls `EnumerateCounters` + `DescribeCounter` for each →
  returns list of counter descriptions with all metadata fields
- Daemon handler `counter_fetch`: calls `FetchCounters` → returns per-event counter values;
  supports optional `eid` filter and optional `names` substring filter
- VFS route `/counters/list` → leaf, handler `"counter_list"`
- VFS route `/counters/` → directory listing
- CLI `rdc counters --list` → TSV: `ID\tNAME\tUNIT\tTYPE\tCATEGORY`
- CLI `rdc counters` (default) → TSV: `EID\tCOUNTER\tVALUE\tUNIT` (all draws, all counters)
- CLI `rdc counters --eid EID` → filter fetch to a single event
- CLI `rdc counters --name PAT` → filter counters by name substring
- CLI `rdc counters --json` → JSON output for both list and fetch modes
- Mock additions: `GPUCounter` enum, `CounterUnit` enum, `CompType` members, `CounterDescription`
  dataclass, `CounterResult` dataclass, `CounterValue` union-like object,
  `MockReplayController.EnumerateCounters`, `MockReplayController.DescribeCounter`,
  `MockReplayController.FetchCounters`
- Mock API sync: `test_mock_api_sync.py` covers `GPUCounter`, `CounterUnit` in `ENUM_PAIRS`;
  `CounterDescription`, `CounterResult` in `STRUCT_PAIRS`

### Out of scope
- Custom counter registration or per-vendor extension counters (Nsight/RGP)
- Writing counter results back to a file or binary export
- Aggregation, averaging, or statistical summary of counter values across events
- Counter timeline visualization
- Counter threshold alerting (`rdc watch` integration)

## Test Matrix

| Layer | Scope | Runner |
|-------|-------|--------|
| Unit | Daemon handler `counter_list` with mock adapter | pytest (test_counters_daemon.py) |
| Unit | Daemon handler `counter_fetch` — happy path, eid filter, name filter | pytest (test_counters_daemon.py) |
| Unit | Daemon handler error paths — no adapter, invalid eid | pytest (test_counters_daemon.py) |
| Unit | VFS route resolution for `/counters/list` and `/counters/` | pytest (test_vfs_router.py) |
| Unit | CLI `rdc counters --list` TSV and JSON output | pytest + CliRunner (test_counters_commands.py) |
| Unit | CLI `rdc counters` fetch TSV and JSON output | pytest + CliRunner (test_counters_commands.py) |
| Unit | CLI `rdc counters --eid` and `--name` filter forwarding | pytest + CliRunner (test_counters_commands.py) |
| Integration | Mock API sync (`GPUCounter`, `CounterUnit`, `CounterDescription`, `CounterResult`) | pytest (test_mock_api_sync.py) |
| GPU | `counter_list` returns ≥14 counters with valid schema on real capture | pytest -m gpu |
| GPU | `counter_fetch` returns results with GPU Duration > 0 for draw events | pytest -m gpu |
| GPU | `counter_fetch` with eid filter returns only the requested event | pytest -m gpu |
| GPU | VFS `/counters/list` resolves and returns valid leaf response | pytest -m gpu |

## Cases

### Daemon handler: `counter_list`

1. **Happy path — all counters returned**: `EnumerateCounters` returns 3 `GPUCounter` values;
   handler calls `DescribeCounter` for each → response `{"counters": [...]}` where each entry
   has `id`, `name`, `unit`, `type`, `category`, `description`, `uuid` fields with correct values.
2. **No adapter loaded**: `state.adapter is None` → JSON-RPC error `-32002` with non-empty
   `"message"`.
3. **Empty counter list**: `EnumerateCounters` returns `[]` → response `{"counters": []}`, not
   an error.

### Daemon handler: `counter_fetch`

4. **Happy path — all events, all counters**: `FetchCounters` returns results for two events and
   two counters → response `{"results": [...]}` where each entry has `eid`, `counter`, `value`,
   `unit`; Float counters serialized as floats, UInt counters as integers.
5. **`eid` filter — matching event**: request includes `eid=11`; handler discards all results
   where `result.eventId != 11` → only rows for event 11 in response.
6. **`eid` filter — no matching event**: `eid=999` matches no result → `{"results": []}`, not
   an error.
7. **`eid` filter — invalid type (non-integer string)**: handler returns error `-32001` with
   descriptive message.
8. **`names` filter — substring match**: request includes `names="Duration"`; handler keeps only
   counters whose description name contains `"Duration"` (case-insensitive) → filtered rows.
9. **`names` filter — no match**: `names="Nonexistent"` → `{"results": []}`, not an error.
10. **Combined `eid` and `names` filters**: intersection applied — only rows matching both event
    and name substring.
11. **No adapter loaded**: `state.adapter is None` → error `-32002`.

### VFS routes

12. **`/counters/list` resolves to leaf**: router returns `kind="leaf"`, handler=`"counter_list"`,
    no path params.
13. **`/counters/` resolves to directory**: router returns `kind="dir"` with `"list"` child entry.
14. **Unrecognised path under `/counters/`**: e.g. `/counters/unknown` → `kind="notfound"` or
    router error, not a 500.

### CLI: `rdc counters --list`

15. **TSV output — default list**: header `ID\tNAME\tUNIT\tTYPE\tCATEGORY`, followed by one row
    per counter; tab-separated, no trailing whitespace, exit code 0.
16. **`--list --json` flag**: output is valid JSON; top-level key `"counters"` is a list where
    each element has `id`, `name`, `unit`, `type`, `category` string fields; exit code 0.
17. **Missing session — list**: no active daemon → error message to stderr, exit code 1.

### CLI: `rdc counters` (fetch)

18. **TSV output — all events all counters**: header `EID\tCOUNTER\tVALUE\tUNIT`; Float values
    printed as decimal notation (not scientific); UInt values printed as plain integers; exit code 0.
19. **`--eid EID` filter forwarded**: daemon `counter_fetch` receives `eid` param equal to the
    integer passed; output contains only rows for that event.
20. **`--name PAT` filter forwarded**: daemon `counter_fetch` receives `names` param equal to the
    pattern string; output contains only matching counter rows.
21. **`--json` flag on fetch**: output is valid JSON; top-level key `"results"` is a list where
    each element has `eid` (int), `counter` (str), `value` (number), `unit` (str); exit code 0.
22. **Zero results returned**: only header row printed, exit code 0.
23. **Missing session — fetch**: error to stderr, exit code 1.
24. **`--eid` with non-integer value**: click validation error, exit code 2.

### Mock additions

25. **`GPUCounter` enum**: at minimum `EventGPUDuration=1`, `InputVerticesRead=2`, and enough
    members up to `Count=16`; importable from `mock_renderdoc`.
26. **`CounterUnit` enum**: at minimum `Absolute=0`, `Seconds=1`, `Percentage=2`; importable
    from `mock_renderdoc`.
27. **`CompType` enum**: members `Float=1`, `UInt=4` present in `mock_renderdoc`.
28. **`CounterDescription` dataclass**: fields `counter`, `name`, `category`, `description`,
    `resultByteWidth`, `resultType` (`CompType`), `unit` (`CounterUnit`), `uuid`; importable.
29. **`CounterResult` dataclass**: fields `eventId: int`, `counter: GPUCounter`,
    `value: CounterValue`; importable.
30. **`CounterValue` object**: exposes `.d` (float), `.u64` (int), `.u32` (int), `.f` (float)
    attributes without raising `AttributeError`.
31. **`MockReplayController.EnumerateCounters()`**: returns `list[GPUCounter]`; default stub
    returns at least two entries; configurable in fixture.
32. **`MockReplayController.DescribeCounter(counterId)`**: returns a `CounterDescription`;
    default stub returns a description matching the given `counterId`.
33. **`MockReplayController.FetchCounters(counterIds)`**: accepts `list[GPUCounter]`; returns
    `list[CounterResult]`; default stub returns one result per counter per known event.

### GPU integration

34. **`counter_list` on hello_triangle.rdc**: response contains ≥14 counters; every entry has
    non-empty `name`, `unit`, `type`, `category` strings; no entry raises an exception.
35. **`counter_fetch` GPU Duration > 0**: fetch all counters on real capture; at least one result
    for the `EventGPUDuration` counter has `value > 0`.
36. **`counter_fetch` eid filter on real capture**: request with a known draw eid; response
    contains only rows with `eid` matching the requested value.
37. **VFS `/counters/list` GPU**: VFS resolve + handler round-trip returns valid `{"counters": [...]}`
    with ≥14 entries.

## Assertions

### Exit codes
- 0: success (including zero-result responses)
- 1: runtime error (no session, no adapter, invalid eid)
- 2: argument/usage error (non-integer `--eid`, unrecognised flag)

### TSV contract (`rdc counters --list`)
- First line is exactly `ID\tNAME\tUNIT\tTYPE\tCATEGORY` (no leading/trailing whitespace)
- Each subsequent line: five tab-separated fields; `ID` is a decimal integer string; `NAME`,
  `UNIT`, `TYPE`, `CATEGORY` are non-empty strings
- No blank lines between data rows

### TSV contract (`rdc counters` fetch)
- First line is exactly `EID\tCOUNTER\tVALUE\tUNIT`
- Each subsequent line: four tab-separated fields; `EID` is a decimal integer; `COUNTER` is a
  non-empty string; `VALUE` is a numeric string (decimal float or integer, no scientific notation);
  `UNIT` is a non-empty string
- No blank lines between data rows

### JSON schema (`counter_list` handler response)
```json
{
  "counters": [
    {
      "id": <int>,
      "name": <str>,
      "unit": <str>,
      "type": <str>,
      "category": <str>,
      "description": <str>,
      "uuid": <str>
    },
    ...
  ]
}
```
- `counters` is always a list (empty is valid)
- All `id` values are positive integers
- All string fields are non-empty

### JSON schema (`counter_fetch` handler response)
```json
{
  "results": [
    {"eid": <int>, "counter": <str>, "value": <number>, "unit": <str>},
    ...
  ]
}
```
- `results` is always a list (empty is valid)
- `eid` is a positive integer
- `value` is a JSON number (float or integer), never a string
- `counter` and `unit` are non-empty strings

### Error response (JSON-RPC)
- `-32001`: invalid parameter (e.g. non-integer eid)
- `-32002`: no replay loaded / no adapter
- `"message"` field is a non-empty string
- Error output goes to stderr, nothing to stdout

### Value formatting
- `CompType.Float` counters: `value` serialized as Python `float`; TSV column uses `f"{v:.6g}"` or
  equivalent (no trailing zeros, no scientific notation for normal ranges)
- `CompType.UInt` counters: `value` serialized as Python `int`; TSV column is a plain integer string

## Risks & Rollback

| Risk | Impact | Mitigation |
|------|--------|------------|
| `FetchCounters` is GPU-bound and slow on large captures | GPU tests time out | Increase pytest timeout for `gpu` mark to 60 s; document in conftest |
| Vendor/extension counters (Nsight counter 3000000) cause `DescribeCounter` to return error description | `counter_list` crashes or returns garbage | Wrap `DescribeCounter` call in try/except; skip entries with empty or error name |
| AMD/Intel/Nvidia vendor counters add unexpected entries beyond built-in 14 | GPU count assertion fails | Assert `>= 14` not `== 14`; do not assert exact set |
| `CounterValue` is a SWIG union — accessing wrong field returns 0.0 silently | Incorrect values with no error | Check `resultType` (`CompType`) before reading `.d` vs `.u32`/`.u64`; unit test covers both branches |
| `GPUCounter` enum values differ between RenderDoc versions | Mock out-of-sync with real API | GPU sync test in `test_mock_api_sync.py` compares enum members against live import |
| Counter name substring filter is case-sensitive vs. case-insensitive discrepancy | Unexpected empty results for users | Normalise to lowercase on both sides; assert in unit test with mixed-case pattern |
| Rollback | — | Revert branch; no master changes until PR squash-merge |
