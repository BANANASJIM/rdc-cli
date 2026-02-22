# Proposal: diff-draws

## Summary

Implement `rdc diff a.rdc b.rdc --draws`: draw call comparison using LCS-based
alignment on debug marker paths. Produces unified diff, `--shortstat` summary,
or `--json` output. Exit code: 0=no change, 1=changed, 2=error.

## Design References

- `设计/Diff 对齐算法.md` §匹配Key — `(marker_path, draw_type, sequential_index)`
- `设计/Diff 对齐算法.md` §对齐算法 — LCS steps
- `设计/Diff 对齐算法.md` §无Marker的Capture — fallback `(draw_type, shader_hash, topology)`
- `设计/Diff 对齐算法.md` §性能 — group by top-level marker
- `设计/命令总览.md` — `rdc diff --draws [--shortstat]`
- `设计/设计原则.md` — exit codes, output philosophy

## Assumptions

Assumes diff-infrastructure exists (dual daemon lifecycle, `query_both`).

## Changes

### New files

| File | Description |
|------|-------------|
| `src/rdc/diff/__init__.py` | Package marker, exports `DrawRecord`, `diff_draws` |
| `src/rdc/diff/alignment.py` | `DrawRecord`, match key builders, `lcs_align`, `align_draws` |
| `src/rdc/diff/draws.py` | `DiffStatus`, `DrawDiffRow`, comparison, 3 renderers |

### Modified files

| File | Change |
|------|--------|
| `src/rdc/commands/diff.py` | Wire `--draws`, `--shortstat` flags |

## Implementation Details

### DrawRecord (`alignment.py`)

```python
@dataclass(frozen=True)
class DrawRecord:
    eid: int
    draw_type: str      # "DrawIndexed" | "Draw" | "Dispatch" | "Clear" | "Copy"
    marker_path: str    # "GBuffer/Floor" or "-"
    triangles: int
    instances: int
    pass_name: str
    shader_hash: str    # hex or "-" (fetched lazily in fallback mode)
    topology: str       # "TriangleList" or "-"
```

### Match Keys

Primary: `(marker_path, draw_type, sequential_index)` — sequential_index
disambiguates repeated marker names.

Fallback (no markers): `(draw_type, shader_hash, topology)` + confidence
column (`high`/`medium`/`low`).

### LCS Alignment

O(n*m) DP. When combined len > 500, groups by top-level marker first,
runs LCS per group, concatenates. Returns `list[tuple[DrawRecord | None, DrawRecord | None]]`.

### Comparison

```python
class DiffStatus(str, Enum):
    EQUAL = "="; MODIFIED = "~"; ADDED = "+"; DELETED = "-"

@dataclass
class DrawDiffRow:
    status: DiffStatus
    eid_a: int | None; eid_b: int | None
    marker: str; draw_type: str
    triangles_a: int | None; triangles_b: int | None
    instances_a: int | None; instances_b: int | None
    confidence: str
```

EQUAL when draw_type + triangles + instances all match. Otherwise MODIFIED.

### Output Formats

- **Unified diff**: `---`/`+++` header, `" "`/`"-"`/`"+"` prefixed rows. Modified = 2 lines.
- **`--shortstat`**: `"3 added, 1 deleted, 5 modified, 42 unchanged"`
- **`--json`**: Array of DrawDiffRow objects

### CLI

`--draws` path: query draws from both daemons → build DrawRecords → `diff_draws()` → render → exit 0 or 1.

## Scope

| Component | Lines |
|-----------|-------|
| `src/rdc/diff/__init__.py` | ~8 |
| `src/rdc/diff/alignment.py` | ~135 |
| `src/rdc/diff/draws.py` | ~185 |
| `src/rdc/commands/diff.py` additions | ~75 |
| Tests (alignment + draws + CLI + GPU) | ~370 |
| **Total** | **~773** |
