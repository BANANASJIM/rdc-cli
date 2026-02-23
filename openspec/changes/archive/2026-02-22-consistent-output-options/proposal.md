# Proposal: Consistent Output Options

**Date:** 2026-02-22
**Phase:** Post-4C maintenance
**Status:** Draft

---

## Problem

The `events` and `draws` commands support `--no-header`, `--jsonl`, and `-q/--quiet` output options. Approximately 12 other list-producing commands are missing some or all of these options:

- `resources`, `passes`, `bindings`, `shaders` — missing all three
- `counters` (both `--list` and fetch paths) — missing all three
- `usage` (both single and `--all` paths) — missing all three
- `log` — missing `--jsonl` and `-q`
- `pixel` — missing `--jsonl` and `-q`
- `ls -l` — missing `--no-header`, `--jsonl`, and `-q`
- `shader-map` — missing `--json`, `--jsonl`, and `-q`

This inconsistency forces pipeline authors and agent scripts to use `awk`/`tail`/`grep` workarounds for output that should be accessible via a flag. It also makes `-q` piping patterns (e.g. `rdc resources -q | xargs …`) unavailable for these commands.

---

## Solution

1. Create `src/rdc/formatters/options.py` with a `@list_output_options` Click decorator that attaches `--no-header`, `--jsonl`, and `-q/--quiet` to any command. The `--json` option is excluded because every affected command already declares it.

2. Apply `@list_output_options` to the 10 affected commands that use `call()` or `_daemon_call()`. Replace raw `click.echo` / f-string output with `write_tsv` / `write_jsonl` calls and the standard output waterfall.

3. For `ls -l`: add `--no-header`, `--jsonl`, and `-q` as individual Click options (not the decorator) because `-q` semantics differ (`name` column only, and `--no-header` is only meaningful with `-l`). Extend `render_ls_long()` in `vfs/formatter.py` with a `no_header` parameter.

4. For `shader-map`: add `--json`, `--jsonl`, and `-q` as individual options alongside the existing `--no-header`.

5. `stats` is excluded — it emits multiple distinct tables; quiet/jsonl semantics are undefined.

---

## Design

### Output waterfall (universal pattern)

```python
if use_json:
    write_json(data)
elif use_jsonl:
    write_jsonl(rows)
elif quiet:
    for row in rows:
        sys.stdout.write(str(row[quiet_col]) + "\n")
else:
    write_tsv(rows, header=HEADER, no_header=no_header)
```

`rows` is always a `list[list[Any]]` for `write_tsv` / `write_jsonl`. For `write_jsonl`, pass the original list of dicts from the daemon response. For `-q`, `quiet_col` is the primary key column for each command (see table below).

### `@list_output_options` decorator

```python
# src/rdc/formatters/options.py
import click, functools
from collections.abc import Callable
from typing import Any

def list_output_options(fn: Callable) -> Callable:
    """Attach --no-header, --jsonl, -q to a Click command function."""
    @click.option("--no-header", is_flag=True, help="Omit TSV header")
    @click.option("--jsonl", "use_jsonl", is_flag=True, help="JSONL output")
    @click.option("-q", "--quiet", is_flag=True, help="Print primary key column only")
    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return fn(*args, **kwargs)
    return wrapper
```

The decorator is applied *below* `@click.command(...)` (closer to the function def), so Click sees the options when it processes the command. Usage:

```python
@click.command("resources")
@click.option("--json", "as_json", ...)
@list_output_options
def resources_cmd(as_json, no_header, use_jsonl, quiet, ...):
```

### `render_ls_long` signature change

```python
def render_ls_long(
    children: list[dict[str, Any]],
    columns: list[str],
    *,
    no_header: bool = False,
) -> str:
```

When `no_header=True`, the header line is omitted from the returned string.

### Affected commands — migration table

| Command | File | Quiet column | TSV rows data key |
|---------|------|-------------|-------------------|
| `resources` | `resources.py` | `id` | `result["rows"]` |
| `passes` | `resources.py` | `name` | `tree["passes"]` |
| `bindings` | `pipeline.py` | `eid` | `result["rows"]` |
| `shaders` | `pipeline.py` | `shader` | `result["rows"]` |
| `counters --list` | `counters.py` | `id` | `result["counters"]` |
| `counters` (fetch) | `counters.py` | `eid` | `result["rows"]` |
| `usage` (single) | `usage.py` | `eid` | `result["entries"]` |
| `usage --all` | `usage.py` | `id` | `result["rows"]` |
| `log` | `info.py` | `eid` | `result["messages"]` |
| `pixel` | `pixel.py` | `eid` | `result["modifications"]` |
| `ls -l` | `vfs.py` | `name` | `result["children"]` |
| `shader-map` | `unix_helpers.py` | `eid` | `result["rows"]` |

### `ls` special handling

`-q` on `ls -l` prints only the `name` field of each child entry (one per line). `--no-header` only suppresses the column header when `-l` is active; for regular `ls` output there is no header to suppress. `--jsonl` on `ls -l` emits each child dict as one JSON line. These options have no effect without `-l`.

### `shader-map` additions

`shader-map` gains `--json` (full JSON array), `--jsonl` (one row per line), and `-q` (EID column only). The existing `--no-header` is preserved as-is.

---

## Files Changed

| File | Change |
|------|--------|
| `src/rdc/formatters/options.py` | New — `@list_output_options` decorator |
| `src/rdc/commands/resources.py` | Apply decorator; replace `format_row` echo with `write_tsv`/`write_jsonl`/quiet for `resources` and `passes` |
| `src/rdc/commands/pipeline.py` | Apply decorator; replace `format_row` echo with waterfall for `bindings` and `shaders` |
| `src/rdc/commands/counters.py` | Apply decorator; replace f-string echo with waterfall for both paths |
| `src/rdc/commands/usage.py` | Apply decorator; replace f-string echo with waterfall for both paths |
| `src/rdc/commands/info.py` | Apply decorator; add `use_jsonl` and `quiet` to `log_cmd`; remove individual `--no-header` (absorbed by decorator) |
| `src/rdc/commands/pixel.py` | Apply decorator; add `use_jsonl` and `quiet` to `pixel_cmd`; remove individual `--no-header` (absorbed by decorator) |
| `src/rdc/commands/vfs.py` | Add individual `--no-header`, `--jsonl`, `-q` to `ls_cmd`; pass `no_header` to `render_ls_long`; add jsonl/quiet output paths for `-l` |
| `src/rdc/commands/unix_helpers.py` | Add `--json`, `--jsonl`, `-q` to `shader_map_cmd`; add waterfall output |
| `src/rdc/vfs/formatter.py` | Add `no_header: bool = False` parameter to `render_ls_long` |
| `tests/unit/test_resources_commands.py` | Add `--no-header`, `--jsonl`, `-q` tests for `resources` and `passes` |
| `tests/unit/test_pipeline_commands.py` (or existing) | Add `--no-header`, `--jsonl`, `-q` tests for `bindings` and `shaders` |
| `tests/unit/test_counters_commands.py` | Add `--no-header`, `--jsonl`, `-q` tests for both paths |
| `tests/unit/test_usage_commands.py` | Add `--no-header`, `--jsonl`, `-q` tests for both paths |
| `tests/unit/test_info_commands.py` (or `test_cli.py`) | Add `--jsonl`, `-q` tests for `log` |
| `tests/unit/test_pixel_history_commands.py` | Add `--jsonl`, `-q` tests for `pixel` |
| `tests/unit/test_vfs_commands.py` | Add `--no-header`, `--jsonl`, `-q` tests for `ls -l` |
| `tests/unit/test_unix_helpers_commands.py` | Add `--json`, `--jsonl`, `-q` tests for `shader-map` |
| `tests/unit/test_vfs_formatter.py` | Add `no_header=True` test for `render_ls_long` |

---

## Non-Goals

- Changing `--json` behavior on any command (already consistent)
- Adding output options to single-record commands (`resource`, `pass`, `event`, `draw`, `info`, `pipeline`)
- Adding output options to `stats` (multi-table; semantics undefined)
- Changing the daemon protocol or JSON-RPC wire format
- Modifying `write_tsv` or `write_jsonl` signatures
