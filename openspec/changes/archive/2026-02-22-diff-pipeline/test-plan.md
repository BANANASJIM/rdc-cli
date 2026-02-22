# Test Plan: diff-pipeline

## Scope

### In scope
- `build_draw_records`: converts `draws` RPC response rows to `list[DrawRecord]`
- `find_aligned_pair`: locates aligned `(DrawRecord_a, DrawRecord_b)` by marker_path
- `diff_pipeline_sections`: compares 13 pipe_* section dicts, returns `list[PipeFieldDiff]`
- Rendering: TSV (default, changed-only), TSV verbose (all fields), JSON
- CLI wiring: `--pipeline MARKER` dispatches to pipeline logic, `--json` flag respected
- Error paths: marker not found (exit 2), draws fetch failure (exit 2), section RPC
  failure (warn + skip)
- Repeated marker disambiguation: `marker[0]` / `marker[1]` index syntax

### Out of scope
- Compute pipeline sections
- GPU integration test (deferred)
- VFS routes

## Test Matrix

| Layer | Scope | Runner |
|-------|-------|--------|
| Unit  | `build_draw_records`, `find_aligned_pair`, `diff_pipeline_sections`, renderers | pytest (`test_diff_pipeline.py`) |
| Unit  | CLI `--pipeline` dispatch, `--json`, error exits | pytest + CliRunner (`test_diff_command.py`) |

## Cases

### `build_draw_records`

1. **Basic conversion**: draws list with `eid`, `type`, `marker`, `triangles`,
   `instances`, `pass`. Returns `DrawRecord` with `marker_path=marker`,
   `shader_hash=""`, `topology=""`, other fields mapped directly.

2. **Missing marker field**: draw row without `"marker"` key → `marker_path="-"`.

3. **Empty list**: `build_draw_records([])` → `[]`.

### `find_aligned_pair`

4. **Exact marker found in both**: aligned pairs contain `(a, b)` where
   `a.marker_path == "GBuffer/Floor"`. Returns `(a, b)`.

5. **Marker only in A** (deleted draw): aligned pair is `(a, None)`.
   Returns error: marker not found in B. Exits 2.

6. **Marker only in B** (added draw): aligned pair is `(None, b)`.
   Returns error: marker not found in A.

7. **Marker not found in either**: returns error for A capture.

8. **Repeated marker, no index suffix**: two draws with same marker_path.
   Returns pair at index 0, emits warning that duplicates exist.

9. **Repeated marker, `marker[1]` suffix**: returns pair at sequential_index 1.

10. **`marker[99]` out of range**: index exceeds occurrence count → error exit 2.

### `diff_pipeline_sections`

11. **Identical flat sections**: topology same both sides → `PipeFieldDiff` with
    `changed=False`, `value_a == value_b`.

12. **Changed scalar field**: `topology` differs (`TriangleList` vs
    `TriangleStrip`) → `PipeFieldDiff(section="topology", field="topology",
    value_a="TriangleList", value_b="TriangleStrip", changed=True)`.

13. **`eid` key stripped**: `eid` never appears as a diff field.

14. **Nested dict (stencil front/back)**: `front.failOperation` differs →
    `PipeFieldDiff(section="stencil", field="front.failOperation", ...)`.

15. **List sections same length, one element differs**: `blends[0].enabled`
    differs → `PipeFieldDiff(section="blend", field="blends[0].enabled", ...)`.

16. **List sections different lengths**: A has 2 blend entries, B has 1 →
    `PipeFieldDiff(section="blend", field="count", value_a=2, value_b=1,
    changed=True)`.

17. **Section RPC returned `None`** (failed): section skipped, no crash. Warning
    emitted (testable via captured stderr or return value flag).

18. **All sections identical**: `diff_pipeline_sections` returns a list where
    all entries have `changed=False`.

### Renderers

19. **`render_pipeline_tsv` changed-only**: only rows with `changed=True`
    appear; each line ends with `<- changed`.

20. **`render_pipeline_tsv` verbose**: all rows rendered; unchanged rows do not
    have `<- changed` marker. Header row present.

21. **`--no-header` TSV**: header line absent.

22. **`render_pipeline_json`**: returns valid JSON array; each element has
    `section`, `field`, `value_a`, `value_b`, `changed` keys.

23. **No changes**: TSV output is header only (or empty with `--no-header`).

### CLI wiring

24. **`--pipeline MARKER` dispatches**: `diff_cmd` with `--pipeline GBuffer/Floor`
    calls pipeline handler, not stub error path. Exit 0 on successful diff.
    (Monkeypatch `query_both` and `query_both_sync` to return fixture data.)

25. **`--pipeline` + `--json`**: JSON rendered to stdout, exit 0.

26. **`--pipeline` marker not found → exit 2**: monkeypatch `query_both` to
    return draws without the requested marker. Exit code 2, error on stderr.

27. **`--pipeline` draws fetch failure → exit 2**: monkeypatch `query_both` to
    return `(None, None, "both daemons failed")`. Exit 2.

28. **`--pipeline` section RPC failure (partial)**: some `query_both_sync`
    results are `None`. Affected sections skipped; exit 0 with warning on stderr.

29. **`--pipeline` + `--verbose`**: all fields rendered (including unchanged).

## Assertions

### Exit codes
- `0`: diff completed (even if all sections identical)
- `2`: startup failure, draws fetch failure, or marker not found

### TSV schema (default, changed-only)
```
SECTION\tFIELD\tA\tB
<section>\t<field>\t<value_a>\t<value_b>\t<- changed
```

### JSON schema
```json
[
    {
        "section": "topology",
        "field": "topology",
        "value_a": "TriangleList",
        "value_b": "TriangleStrip",
        "changed": true
    }
]
```

### `PipeFieldDiff` invariants
- `section` is one of the 13 section key names
- `field` is a dot-path for nested values (`"front.failOperation"`) or
  index-path for lists (`"blends[0].enabled"`)
- `value_a` / `value_b` are JSON-serializable (str, int, float, bool, None)
- `eid` is never a field name

## Risks

| Risk | Mitigation |
|------|------------|
| `draws` RPC `marker` field absent in older daemon builds | Default to `"-"` in `build_draw_records` |
| Stencil front/back order differs between APIs | Compare by field name, not position |
| List section ordering not stable (samplers) | Compare by index; document limitation |
| Marker index syntax conflicts with path characters | Restrict to trailing `[N]` regex only |
