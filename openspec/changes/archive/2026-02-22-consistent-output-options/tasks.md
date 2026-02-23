# Tasks: Consistent Output Options

## Agent Assignment

| Commit | Agent | Files | Parallel? |
|--------|-------|-------|-----------|
| 1 — feat(formatters): add `@list_output_options` decorator | Worktree 1 | `formatters/options.py` | Independent |
| 2 — feat(vfs): add `no_header` param to `render_ls_long` | Worktree 1 | `vfs/formatter.py`, `test_vfs_formatter.py` | Sequential after commit 1 |
| 3 — feat(cli): add output options to resources and passes | Worktree 2 | `commands/resources.py`, `test_resources_commands.py` | Independent |
| 4 — feat(cli): add output options to bindings and shaders | Worktree 2 | `commands/pipeline.py`, pipeline test file | Sequential after commit 3 |
| 5 — feat(cli): add output options to counters | Worktree 3 | `commands/counters.py`, `test_counters_commands.py` | Independent |
| 6 — feat(cli): add output options to usage | Worktree 3 | `commands/usage.py`, `test_usage_commands.py` | Sequential after commit 5 |
| 7 — feat(cli): add output options to log and pixel | Worktree 4 | `commands/info.py`, `commands/pixel.py`, log/pixel test files | Independent |
| 8 — feat(cli): add output options to ls -l | Worktree 5 | `commands/vfs.py`, `test_vfs_commands.py` | Independent |
| 9 — feat(cli): add output options to shader-map | Worktree 5 | `commands/unix_helpers.py`, `test_unix_helpers_commands.py` | Sequential after commit 8 |

Worktrees 2–5 can run in parallel after commit 1 lands. Worktree 1 (commits 1–2) must complete first so the decorator is available.

---

## Commit 1: `feat(formatters): add @list_output_options decorator`

**Agent:** Worktree 1

### Files Created

| File | Change |
|------|--------|
| `src/rdc/formatters/options.py` | New module. Define `list_output_options(fn)` that stacks `--no-header`, `--jsonl` (`use_jsonl`), and `-q/--quiet` Click options onto the decorated function using `functools.wraps`. |

### Implementation notes

- Decorator stacking order: innermost first, so `-q` is closest to the function signature. Use `functools.wraps` to preserve the function name for Click's command name inference.
- Do NOT include `--json` — every affected command already declares it.
- Parameter names match events/draws: `no_header: bool`, `use_jsonl: bool`, `quiet: bool`.

---

## Commit 2: `feat(vfs): add no_header param to render_ls_long`

**Agent:** Worktree 1

### Files Modified

| File | Change |
|------|--------|
| `src/rdc/vfs/formatter.py` | Add `no_header: bool = False` keyword-only parameter to `render_ls_long`. When `True`, omit the first (header) line from the returned string. |
| `tests/unit/test_vfs_formatter.py` | Add tests O-39 and O-40: `no_header=True` omits header; `no_header=False` (default) includes it. |

---

## Commit 3: `feat(cli): add output options to resources and passes`

**Agent:** Worktree 2

### Files Modified

| File | Change |
|------|--------|
| `src/rdc/commands/resources.py` | Apply `@list_output_options` to `resources_cmd`. Add `no_header`, `use_jsonl`, `quiet` params. Replace header+loop echo with waterfall: json→write_json, jsonl→write_jsonl(rows dicts), quiet→id per line, else→write_tsv. |
| `src/rdc/commands/resources.py` | Apply `@list_output_options` to `passes_cmd`. Replace header+loop echo with waterfall: json→write_json(tree), jsonl→write_jsonl(passes list), quiet→name per line, else→write_tsv. |
| `tests/unit/test_resources_commands.py` | Add tests O-01–O-06 and O-41–O-42. |

### Import additions for `resources.py`

```python
import sys
from rdc.formatters.options import list_output_options
from rdc.formatters.tsv import write_tsv
from rdc.formatters.json_fmt import write_jsonl
```

---

## Commit 4: `feat(cli): add output options to bindings and shaders`

**Agent:** Worktree 2

### Files Modified

| File | Change |
|------|--------|
| `src/rdc/commands/pipeline.py` | Apply `@list_output_options` to `bindings_cmd`. Replace header+loop echo with waterfall: jsonl→write_jsonl(rows dicts), quiet→eid per line, else→write_tsv. |
| `src/rdc/commands/pipeline.py` | Apply `@list_output_options` to `shaders_cmd`. Replace header+loop echo with waterfall (quiet column: `shader`). |
| `tests/unit/test_pipeline_state.py` or new `test_pipeline_commands.py` | Add tests O-07–O-12 and O-43–O-44. |

### Import additions for `pipeline.py`

```python
import sys
from rdc.formatters.options import list_output_options
from rdc.formatters.tsv import write_tsv
from rdc.formatters.json_fmt import write_jsonl
```

---

## Commit 5: `feat(cli): add output options to counters`

**Agent:** Worktree 3

### Files Modified

| File | Change |
|------|--------|
| `src/rdc/commands/counters.py` | Apply `@list_output_options` to `counters_cmd`. Add `no_header`, `use_jsonl`, `quiet` params. For `--list` path: replace f-string echo with waterfall (quiet col: `id`). For fetch path: replace f-string echo with waterfall (quiet col: `eid`). |
| `tests/unit/test_counters_commands.py` | Add tests O-13–O-18 and O-45–O-46. |

### Import additions for `counters.py`

```python
import sys
from rdc.formatters.options import list_output_options
from rdc.formatters.tsv import write_tsv
from rdc.formatters.json_fmt import write_jsonl
```

---

## Commit 6: `feat(cli): add output options to usage`

**Agent:** Worktree 3

### Files Modified

| File | Change |
|------|--------|
| `src/rdc/commands/usage.py` | Apply `@list_output_options` to `usage_cmd`. Add `no_header`, `use_jsonl`, `quiet` params. For `--all` path: replace f-string echo with waterfall (quiet col: `id`). For single-resource path: replace f-string echo with waterfall (quiet col: `eid`). |
| `tests/unit/test_usage_commands.py` | Add tests O-19–O-24 and O-47–O-48. |

### Import additions for `usage.py`

```python
import sys
from rdc.formatters.options import list_output_options
from rdc.formatters.tsv import write_tsv
from rdc.formatters.json_fmt import write_jsonl
```

---

## Commit 7: `feat(cli): add output options to log and pixel`

**Agent:** Worktree 4

### Files Modified

| File | Change |
|------|--------|
| `src/rdc/commands/info.py` | Apply `@list_output_options` to `log_cmd`. Remove individual `--no-header` option declaration (absorbed by decorator). Add `use_jsonl` and `quiet` to function signature. Add jsonl→write_jsonl(messages) and quiet→eid per line paths before the existing `write_tsv` call. |
| `src/rdc/commands/pixel.py` | Apply `@list_output_options` to `pixel_cmd`. Remove individual `--no-header` option declaration. Add `use_jsonl` and `quiet` to function signature. Add jsonl and quiet output paths. |
| `tests/unit/test_info_commands.py` (or existing log test location) | Add tests O-25–O-27 and O-49. |
| `tests/unit/test_pixel_history_commands.py` | Add tests O-28–O-30 and O-50. |

### Import additions for `info.py`

```python
from rdc.formatters.options import list_output_options
from rdc.formatters.json_fmt import write_jsonl
```

### Import additions for `pixel.py`

```python
import sys
from rdc.formatters.options import list_output_options
from rdc.formatters.json_fmt import write_jsonl
```

### Special note for `pixel.py`

`_fmt_pixel_mod` produces a TSV row string for the existing echo loop. For `write_jsonl`, pass `result.get("modifications", [])` (list of dicts) directly. For `-q`, print `m["eid"]` per modification entry.

---

## Commit 8: `feat(cli): add output options to ls -l`

**Agent:** Worktree 5

### Files Modified

| File | Change |
|------|--------|
| `src/rdc/commands/vfs.py` | Add individual Click options `--no-header`, `--jsonl` (`use_jsonl`), `-q/--quiet` to `ls_cmd`. These are NOT from the decorator (special semantics). In the `use_long` branch: pass `no_header` to `render_ls_long`; add `use_jsonl` path (write_jsonl on children); add `quiet` path (print child["name"] per entry). |
| `tests/unit/test_vfs_commands.py` | Add tests O-31–O-34. |

### Import additions for `vfs.py`

```python
import sys
from rdc.formatters.json_fmt import write_jsonl
```

### Option semantics for `ls`

`--no-header`, `--jsonl`, and `-q` only take effect when `-l` is also passed. Without `-l`, these options are accepted but have no visible effect (regular ls output is unchanged). This avoids a confusing error and matches the precedent that `-F` and `-l` are independently validated.

---

## Commit 9: `feat(cli): add output options to shader-map`

**Agent:** Worktree 5

### Files Modified

| File | Change |
|------|--------|
| `src/rdc/commands/unix_helpers.py` | Add `--json` (`as_json`), `--jsonl` (`use_jsonl`), `-q/--quiet` options to `shader_map_cmd`. Keep existing `--no-header`. Add waterfall: json→write_json(rows), jsonl→write_jsonl(rows), quiet→eid per line, else→existing no_header TSV logic. |
| `tests/unit/test_unix_helpers_commands.py` | Add tests O-35–O-38. |

### Import additions for `unix_helpers.py`

```python
import sys
from rdc.formatters.json_fmt import write_json, write_jsonl
```

---

## File Conflict Analysis

| Worktree | Files Owned |
|----------|-------------|
| Worktree 1 | `src/rdc/formatters/options.py` (new), `src/rdc/vfs/formatter.py`, `tests/unit/test_vfs_formatter.py` |
| Worktree 2 | `src/rdc/commands/resources.py`, `src/rdc/commands/pipeline.py`, `tests/unit/test_resources_commands.py`, pipeline test file |
| Worktree 3 | `src/rdc/commands/counters.py`, `src/rdc/commands/usage.py`, `tests/unit/test_counters_commands.py`, `tests/unit/test_usage_commands.py` |
| Worktree 4 | `src/rdc/commands/info.py`, `src/rdc/commands/pixel.py`, log/pixel test files |
| Worktree 5 | `src/rdc/commands/vfs.py`, `src/rdc/commands/unix_helpers.py`, `tests/unit/test_vfs_commands.py`, `tests/unit/test_unix_helpers_commands.py` |

No file overlaps across worktrees. Parallel execution is safe after commit 1.

---

## Acceptance Criteria

- [ ] `pixi run lint && pixi run test` passes with zero failures after all commits merged
- [ ] All ~50 new tests pass (O-01 through O-50)
- [ ] No regression in existing test suite (existing json/tsv tests unchanged)
- [ ] `--no-header` suppresses header on all affected list commands
- [ ] `--jsonl` produces valid JSONL (one JSON object per line) on all affected commands
- [ ] `-q` prints only the primary key column, one value per line, on all affected commands
- [ ] `shader-map --json` produces valid JSON array
- [ ] `ls -l --no-header` / `--jsonl` / `-q` work correctly; options no-op without `-l`
- [ ] No `--json` option added to any command that already has it
- [ ] `render_ls_long` `no_header=True` omits header row
- [ ] `log --no-header` and `pixel --no-header` still work (option now from decorator, behavior unchanged)
