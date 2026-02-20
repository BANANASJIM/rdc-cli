# Test Plan: phase2-usage

## Scope

### In scope
- Daemon handler `usage`: single resource → `EventUsage` list as dicts
- Daemon handler `usage_all`: full cross-resource usage matrix with optional filters
- VFS route `/resources/<id>/usage` → leaf, handler `"usage"`
- Tree cache: adds `"usage"` child to each resource node
- CLI `rdc usage <id>` → TSV output (EID, USAGE columns)
- CLI `rdc usage --all` → TSV output (ID, NAME, EID, USAGE columns)
- CLI `rdc usage <id> --json` → JSON output
- CLI `rdc usage --all --type Texture` and `--usage ColorTarget` filters
- Mock additions: `EventUsage` dataclass, `ResourceUsage` enum, `GetUsage` on
  `MockReplayController`
- Mock API sync: `test_mock_api_sync.py` covers `EventUsage` + `GetUsage`

### Out of scope
- Pass dependency graph derived from usage data (`rdc passes --deps`)
- Anomaly detection (unused resources)
- Resource timeline visualization
- Binary or non-text output from VFS

## Test Matrix

| Layer | Scope | Runner |
|-------|-------|--------|
| Unit | Daemon handlers `usage` + `usage_all` with mock adapter | pytest |
| Unit | VFS route resolution for `/resources/<id>/usage` | pytest (test_vfs_router.py) |
| Unit | Tree cache adds `"usage"` child to resource nodes | pytest (test_vfs_tree_cache.py) |
| Unit | CLI `rdc usage` output format (TSV + JSON) | pytest + CliRunner |
| Integration | Mock API sync (`EventUsage`, `GetUsage` signature) | pytest (test_mock_api_sync.py) |
| GPU | `GetUsage` on real vkcube capture — non-empty results | pytest -m gpu |
| GPU | `usage_all` returns complete matrix from real capture | pytest -m gpu |

## Cases

### Daemon handler: `usage`

1. **Happy path — single resource with entries**: resource ID 97 has 3 usage events →
   response `{"id": 97, "name": "...", "entries": [{"eid": int, "usage": str}, ...]}` with
   correct eid and human-readable usage strings.
2. **Zero usage entries**: resource exists but `GetUsage` returns `[]` → response with
   `"entries": []`, not an error.
3. **Resource not found**: `id` not in resource list → error `-32001`.
4. **No adapter loaded**: `state.adapter is None` → error `-32002`.
5. **`resolve_names=false`**: response omits `"name"` field (or sets it to `null`).

### Daemon handler: `usage_all`

6. **No filters**: returns all `{id, name, eid, usage}` rows for all resources.
7. **`--type Texture` filter**: only rows where the resource type is `Texture`; Buffer
   resources are excluded.
8. **`--usage ColorTarget` filter**: only rows where `usage == "ColorTarget"`.
9. **Both filters combined**: `--type Texture --usage ColorTarget` — intersection, not union.
10. **Filter yields zero rows**: valid filters but no matches → `{"rows": [], "total": 0}`,
    not an error.
11. **No adapter loaded**: error `-32002`.

### VFS routes

12. **`/resources/<id>/usage` resolves to leaf**: router returns `kind="leaf"`,
    handler=`"usage"`, param `id` extracted from path.
13. **`/resources/<bad-id>/usage` with non-integer segment**: router returns error or
    `kind="notfound"`.
14. **Tree cache adds `"usage"` child**: after `build_vfs_skeleton`, each resource node
    contains `"usage"` in its children list.

### CLI: `rdc usage <id>`

15. **TSV output — single resource**: header `EID\tUSAGE`, followed by one row per entry;
    tab-separated, no trailing whitespace.
16. **Zero entries**: only header row printed, exit code 0.
17. **`--json` flag**: output is valid JSON matching the `usage` handler response schema.
18. **Missing session**: no active daemon → error message to stderr, exit code 1.
19. **Invalid resource ID (non-integer argument)**: click validation error, exit code 2.

### CLI: `rdc usage --all`

20. **TSV output — all resources**: header `ID\tNAME\tEID\tUSAGE`, one row per usage entry,
    sorted by ID then EID.
21. **`--type Texture` filter forwarded**: daemon receives `type="Texture"` param.
22. **`--usage ColorTarget` filter forwarded**: daemon receives `usage="ColorTarget"` param.
23. **No rows returned**: only header row, exit code 0.
24. **Missing session**: error to stderr, exit code 1.

### Mock additions

25. **`EventUsage` dataclass**: fields `eventId: int`, `usage: ResourceUsage`; importable
    from `mock_renderdoc`.
26. **`ResourceUsage` enum**: at minimum the values exercised in tests are present
    (`Clear`, `ColorTarget`, `CopySrc`, `VS_Constants`, `DepthStencilTarget`,
    `VertexBuffer`, `IndexBuffer`).
27. **`MockReplayController.GetUsage(resourceId)`**: returns a `list[EventUsage]`; default
    stub returns `[]`; configurable per resource ID in fixture.

### GPU integration

28. **`GetUsage` on hello_triangle.rdc**: known texture/render-target resource returns at
    least one entry with usage `ColorTarget` or `Clear`.
29. **`usage_all` full matrix**: result has `total > 0`, all rows have valid integer `eid`
    and non-empty string `usage`.
30. **`--type Texture` GPU filter**: subset of `usage_all` with no non-texture resources.

## Assertions

### Exit codes
- 0: success (including zero-entry results)
- 1: runtime error (no session, resource not found, no adapter)
- 2: argument/usage error (invalid CLI arguments)

### TSV contract (`rdc usage <id>`)
- First line is exactly `EID\tUSAGE` (no leading/trailing whitespace)
- Each subsequent line: two tab-separated fields, `eid` is a decimal integer string,
  `usage` is a non-empty string with no spaces (enum name)
- No blank lines between data rows

### TSV contract (`rdc usage --all`)
- First line is exactly `ID\tNAME\tEID\tUSAGE`
- Each subsequent line: four tab-separated fields; `id` and `eid` are decimal integers,
  `name` is non-empty, `usage` is a non-empty enum name string

### JSON schema (`usage` handler response)
```json
{
  "id": <int>,
  "name": <str>,
  "entries": [
    {"eid": <int>, "usage": <str>},
    ...
  ]
}
```
- `entries` is always a list (empty is valid)
- All `eid` values are positive integers
- All `usage` values are non-empty strings (no raw integers)

### JSON schema (`usage_all` handler response)
```json
{
  "rows": [
    {"id": <int>, "name": <str>, "eid": <int>, "usage": <str>},
    ...
  ],
  "total": <int>
}
```
- `total` equals `len(rows)`

### Error response (JSON-RPC)
- `-32001`: resource not found
- `-32002`: no replay loaded / no adapter
- `"message"` field is a non-empty string
- Error output goes to stderr, nothing to stdout

## Risks & Rollback

| Risk | Impact | Mitigation |
|------|--------|------------|
| `GetUsage` returns raw `ResourceUsage` int, not string | Enum label missing in output | Always call `.name` on the enum value; guard with `str(v)` fallback |
| 46 enum values — mock may be incomplete | Tests miss real enum names | Define a representative subset (≥10 values); GPU tests catch gaps |
| Large captures with many resources make `usage_all` slow | Daemon timeout | Measure on vkcube; add note to proposal if > 500 ms |
| `int(resourceId)` vs `.value` SWIG compat | `GetUsage` receives wrong type | Wrap resource lookup with `int()` cast, consistent with existing handlers |
| VFS router regex for `/resources/<id>/usage` conflicts with future sub-paths | Route shadowing | Use `$` anchor in router pattern; add router conflict test |
| Rollback | — | Revert branch; no master changes until PR squash-merge |
