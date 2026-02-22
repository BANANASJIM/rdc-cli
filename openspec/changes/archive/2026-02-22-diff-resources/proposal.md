# Proposal: diff-resources

## Summary

Implement `rdc diff <a.rdc> <b.rdc> --resources` — compare the GPU resource lists
from two captures, reporting which resources were added, deleted, or had their
type changed between the two frames.

## Motivation

When debugging a regression between two captures, knowing which GPU resources
changed (buffers created/destroyed, textures type-swapped) is an essential first
triage step before diving into draw-level diffs. Currently `--resources` is a
stub that exits 2 with "not yet implemented". This feature unlocks that triage.

## Design

### Matching strategy

Resource IDs are not stable across captures (they are assigned at replay time).
Name is the stable key:

1. **Named resources** — match by `name` (case-insensitive). Same name → compare
   `type` field. Difference in `type` → `MODIFIED`. Present only in A → `DELETED`.
   Present only in B → `ADDED`. Same name + same type → `EQUAL`.
2. **Unnamed resources** (empty string name) — group by `type`, match by
   position within the group. Confidence is `"low"`.

### Output

**Default TSV** (no flags):
```
STATUS  NAME            TYPE_A          TYPE_B
=       MyVertexBuffer  Buffer          Buffer
~       SceneDepth      Texture2D       Texture2DMS
-       OldShadowMap    Texture2D
+       NewAlbedo                       Texture2D
```
Header printed unless `--no-header`. Status symbols: `=` equal, `~` modified,
`-` deleted, `+` added.

**`--shortstat`**: `"3 added, 1 deleted, 2 modified, 40 unchanged"`

**`--json`** / **`--format json`**:
```json
[
  {"status": "~", "name": "SceneDepth", "type_a": "Texture2D", "type_b": "Texture2DMS"},
  ...
]
```

**`--format unified`**: unified diff header `--- a/<capture_a>` / `+++ b/<capture_b>`,
then `-name type_a` / `+name type_b` lines for changed resources.

### Exit codes

- `0`: comparison succeeded, no differences (all EQUAL)
- `1`: comparison succeeded, differences found (any ADDED/DELETED/MODIFIED)
- `2`: error (daemon failure, RPC error)

### Files modified

| File | Change |
|------|--------|
| `src/rdc/diff/resources.py` | NEW: `ResourceRecord`, `ResourceDiffRow`, `diff_resources()`, renderers |
| `src/rdc/commands/diff.py` | Remove `"resources"` from `_MODE_STUBS`; wire `diff_resources` handler |
| `tests/unit/test_diff_resources.py` | NEW: unit tests for logic + renderers + CLI dispatch |

### `src/rdc/diff/resources.py` structure

```python
@dataclass
class ResourceRecord:
    id: int
    type: str
    name: str

@dataclass
class ResourceDiffRow:
    status: DiffStatus   # reuse from rdc.diff.draws
    name: str
    type_a: str | None
    type_b: str | None
    confidence: str      # "high" | "low"

def diff_resources(a: list[ResourceRecord], b: list[ResourceRecord]) -> list[ResourceDiffRow]: ...
def render_tsv(rows: list[ResourceDiffRow], *, header: bool = True) -> str: ...
def render_shortstat(rows: list[ResourceDiffRow]) -> str: ...
def render_json(rows: list[ResourceDiffRow]) -> str: ...
def render_unified(rows: list[ResourceDiffRow], capture_a: str, capture_b: str) -> str: ...
```

### `diff.py` wiring

```python
from rdc.diff.resources import ResourceRecord, diff_resources, render_tsv, render_shortstat, render_json, render_unified as render_unified_res

# inside diff_cmd, after mode == "resources":
resp_a, resp_b, err = query_both(ctx, "resources", {})
# parse rows → diff_resources() → pick renderer → print → sys.exit(0 or 1)
```

`query_both` returns `{"result": {"rows": [{"id": int, "type": str, "name": str}, ...]}}`.
If either side fails, exit 2 with error.

## Not in scope

- Filtering by type or name within `--resources` (use `rdc resources` for that)
- Diffing resource *contents* (buffer data, texture pixels) — separate feature
- Unnamed resource matching beyond type-group positional fallback
- GPU integration test (resources handler already has GPU coverage; diff wiring is pure logic)
