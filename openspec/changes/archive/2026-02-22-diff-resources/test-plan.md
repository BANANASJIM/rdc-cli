# Test Plan: diff-resources

## Scope

### In scope
- `diff_resources()` matching logic: by name (high confidence) and by type-group position (low confidence)
- All four `DiffStatus` outcomes: EQUAL, MODIFIED, ADDED, DELETED
- Renderers: `render_tsv`, `render_shortstat`, `render_json`, `render_unified`
- CLI dispatch: `--resources` flag removed from `_MODE_STUBS`, wired to handler
- `query_both` call, RPC parsing, exit-code mapping (0 / 1 / 2)
- `--shortstat`, `--json`, `--format unified`, `--no-header` flag forwarding

### Out of scope
- Filtering (`type=`, `name=`) inside the diff — tested in `test_query_resources`
- Resource content comparison
- GPU integration test

## Test Matrix

| Layer | Scope | File |
|-------|-------|------|
| Unit | `diff_resources()` logic | `tests/unit/test_diff_resources.py` |
| Unit | All four renderers | `tests/unit/test_diff_resources.py` |
| Unit | CLI dispatch + flag forwarding | `tests/unit/test_diff_resources.py` |

All tests are pure-unit (no daemon, no RPC). CLI tests monkeypatch `query_both`
and `stop_diff_session` / `start_diff_session` as in `test_diff_command.py`.

## Cases

### `diff_resources()` — named matching

1. **Both empty**: `diff_resources([], [])` returns `[]`.

2. **All equal**: same name + same type in both lists → all rows `EQUAL`,
   confidence `"high"`.

3. **Type changed**: resource with same name has different `type` in B →
   `MODIFIED`, `type_a` = A's type, `type_b` = B's type, confidence `"high"`.

4. **ADDED**: resource exists only in B → `ADDED`, `type_a` is `None`,
   `type_b` = B's type, `name` = B's name.

5. **DELETED**: resource exists only in A → `DELETED`, `type_a` = A's type,
   `type_b` is `None`, `name` = A's name.

6. **Mixed batch**: A has [X=Buffer, Y=Tex2D, Z=Buffer], B has [X=Buffer,
   Y=Tex2DMS, W=Buffer]. Expected: X=EQUAL, Y=MODIFIED, Z=DELETED, W=ADDED.

7. **Case-insensitive name match**: name `"MyBuffer"` in A matches `"mybuffer"`
   in B → treated as same resource (EQUAL if types match).

8. **Name collision (same name twice in one side)**: first occurrence matched,
   second treated as ADDED/DELETED. No crash.

### `diff_resources()` — unnamed matching

9. **Unnamed same type, same count**: two unnamed Buffer in A, two unnamed Buffer
   in B → both EQUAL, confidence `"low"`.

10. **Unnamed count mismatch**: three unnamed Texture2D in A, two in B → two
    EQUAL + one DELETED, confidence `"low"`.

11. **Unnamed, type not present in other side**: unnamed Buffer in A, no unnamed
    Buffer in B → DELETED, confidence `"low"`.

12. **Mix of named and unnamed**: named resources matched first, unnamed matched
    separately within their type groups.

### `render_tsv`

13. **Header present by default**: first line is `STATUS\tNAME\tTYPE_A\tTYPE_B`.

14. **`header=False`**: no header line.

15. **EQUAL row**: `=\tMyBuf\tBuffer\tBuffer`.

16. **MODIFIED row**: `~\tSceneDepth\tTexture2D\tTexture2DMS`.

17. **DELETED row**: `-\tOld\tBuffer\t` (TYPE_B column empty).

18. **ADDED row**: `+\tNew\t\tTexture2D` (TYPE_A column empty).

### `render_shortstat`

19. **All statuses present**: `"2 added, 1 deleted, 1 modified, 3 unchanged"`.

20. **All equal**: `"0 added, 0 deleted, 0 modified, N unchanged"`.

### `render_json`

21. **Serializes to JSON array**: each element has keys `status`, `name`,
    `type_a`, `type_b`, `confidence`. `None` values serialize as JSON `null`.

22. **Status uses symbol** (not enum name): `"="`, `"~"`, `"+"`, `"-"`.

### `render_unified`

23. **Header lines**: first two lines are `--- a/<capture_a>` and
    `+++ b/<capture_b>`.

24. **EQUAL**: ` MyBuf Buffer` (space prefix).

25. **MODIFIED**: `-SceneDepth Texture2D` then `+SceneDepth Texture2DMS`.

26. **DELETED**: `-Old Buffer`.

27. **ADDED**: `+New Texture2D`.

### CLI dispatch

28. **`--resources` removed from stubs**: invoking `diff_cmd` with `--resources`
    no longer emits "not yet implemented". (Monkeypatch `query_both` to return
    empty rows on both sides.)

29. **Exit 0 when no differences**: `query_both` returns lists with identical
    resources → exit code 0.

30. **Exit 1 when differences found**: at least one ADDED/DELETED/MODIFIED row →
    exit code 1.

31. **Exit 2 on RPC failure**: `query_both` returns `(None, None, "both daemons failed")`
    → exit code 2, error to stderr.

32. **Default TSV output**: stdout contains tab-separated rows with STATUS column.

33. **`--shortstat`**: stdout is single summary line matching
    `\d+ added, \d+ deleted, \d+ modified, \d+ unchanged`.

34. **`--json` flag**: stdout is valid JSON array, parseable with `json.loads`.

35. **`--format unified`**: stdout starts with `--- a/` header.

36. **`--no-header`**: TSV output has no header row (first line starts with a
    status symbol, not `STATUS`).

37. **Partial failure (one side None)**: `query_both` returns `(resp_a, None, "")`
    → exit 2 with error message.

## Assertions

### Exit codes
- `0`: comparison done, zero ADDED/DELETED/MODIFIED rows
- `1`: comparison done, at least one non-EQUAL row
- `2`: any RPC/daemon error, or either side returned `None`

### TSV contract
- Columns: STATUS, NAME, TYPE_A, TYPE_B (tab-separated)
- TYPE_A empty string for ADDED; TYPE_B empty string for DELETED
- STATUS symbols: `=` `~` `-` `+`

### JSON schema
```json
[
  {
    "status": "~",
    "name": "SceneDepth",
    "type_a": "Texture2D",
    "type_b": "Texture2DMS",
    "confidence": "high"
  }
]
```
- `type_a`/`type_b`: string or `null`
- `confidence`: `"high"` for named matches, `"low"` for unnamed positional

### Confidence
- Named match → `"high"` always
- Unnamed positional → `"low"` always
- Confidence does not affect exit code
