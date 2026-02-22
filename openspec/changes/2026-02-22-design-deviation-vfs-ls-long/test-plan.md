# Test Plan: VFS ls Long Format (-l flag)

## Overview

Tests for adding `-l`/`--long` to `rdc ls` and extending `vfs_ls` RPC with `long: bool`.

Estimated new test cases: ~28
Target: maintain >= 95% coverage.

---

## Unit Tests

### `tests/unit/test_vfs_handlers.py` — daemon handler

New tests for `_handle_vfs_ls` with `long=True`:

| Test name | Description |
|-----------|-------------|
| `test_vfs_ls_long_false_unchanged` | `long=False` (default) returns existing format — no `columns`, no extra fields in children |
| `test_vfs_ls_long_passes` | `long=True` on `/passes` returns `columns=["NAME","DRAWS","DISPATCHES","TRIANGLES"]` and children with those fields |
| `test_vfs_ls_long_draws` | `long=True` on `/draws` returns `columns=["EID","NAME","TYPE","TRIANGLES","INSTANCES"]` |
| `test_vfs_ls_long_events` | `long=True` on `/events` returns `columns=["EID","NAME","TYPE"]` |
| `test_vfs_ls_long_resources` | `long=True` on `/resources` returns `columns=["ID","NAME","TYPE","SIZE"]` |
| `test_vfs_ls_long_textures` | `long=True` on `/textures` returns `columns=["ID","NAME","WIDTH","HEIGHT","FORMAT"]` |
| `test_vfs_ls_long_buffers` | `long=True` on `/buffers` returns `columns=["ID","NAME","LENGTH"]` |
| `test_vfs_ls_long_shaders` | `long=True` on `/shaders` returns `columns=["ID","STAGES","ENTRY","INPUTS","OUTPUTS"]` |
| `test_vfs_ls_long_other_dir` | `long=True` on `/counters` (no specific schema) returns `columns=["NAME","TYPE"]` |
| `test_vfs_ls_long_missing_fields_use_dash` | Child missing a metadata field → value is `"-"` not `None` or KeyError |
| `test_vfs_ls_long_no_adapter_returns_error` | `long=True` when `state.adapter is None` → `-32002` error |
| `test_vfs_ls_long_not_found_returns_error` | `long=True` on non-existent path → `-32001` error |
| `test_vfs_ls_long_draws_triangles_computed` | Triangle count = `(num_indices // 3) * num_instances` |
| `test_vfs_ls_long_draws_type_str` | Draw type string matches `_action_type_str()` result (Draw/DrawIndexed/Dispatch/Clear) |

---

### `tests/unit/test_vfs_commands.py` — CLI command

Add to existing test file:

| Test name | Description |
|-----------|-------------|
| `test_ls_long_calls_rpc_with_long_true` | `-l` flag causes `_daemon_call("vfs_ls", {"path": ..., "long": True})` |
| `test_ls_long_renders_tsv_header` | Response with `columns` → first output line is tab-separated header |
| `test_ls_long_renders_tsv_rows` | Each child row is tab-separated with correct field order |
| `test_ls_long_missing_value_renders_dash` | Child entry missing a metadata key → `-` in that column |
| `test_ls_long_json_emits_full_response` | `-l --json` → JSON output includes `columns` and enriched children |
| `test_ls_long_classify_mutex` | `-l -F` together → exit code 1, error message mentioning mutual exclusion |
| `test_ls_long_empty_directory` | `long=True` response with zero children → only header line, no rows |
| `test_ls_no_long_default_unchanged` | Without `-l`, existing short format still works (regression) |

---

### `tests/unit/test_vfs_formatter.py` (new file)

| Test name | Description |
|-----------|-------------|
| `test_render_ls_long_header_row` | First line matches `"\t".join(columns)` |
| `test_render_ls_long_data_rows` | Each child produces a row with fields in column order |
| `test_render_ls_long_none_field_becomes_dash` | A `None` value in a child dict → `-` in output |
| `test_render_ls_long_empty_children` | No children → only the header line returned |
| `test_render_ls_short_unchanged` | Existing `render_ls` still works (regression) |

---

## CLI Tests

All CLI tests use `click.testing.CliRunner` with `monkeypatch` on `rdc.commands.vfs._daemon_call`.

Mock response shape for `-l` tests:

```python
{
    "path": "/passes",
    "kind": "dir",
    "long": True,
    "columns": ["NAME", "DRAWS", "DISPATCHES", "TRIANGLES"],
    "children": [
        {"name": "Pass#1", "kind": "dir", "draws": 10, "dispatches": 0, "triangles": 5000},
    ],
}
```

---

## GPU Integration Tests

### `tests/integration/test_daemon_handlers_real.py`

Add a new `TestVfsLsLong` class using the existing real-capture session fixture:

| Test name | Description |
|-----------|-------------|
| `test_vfs_ls_long_passes_real` | `vfs_ls(path="/passes", long=True)` on real capture → `columns` matches expected header, each child has numeric `draws`/`dispatches`/`triangles` |
| `test_vfs_ls_long_draws_real` | `vfs_ls(path="/draws", long=True)` → EID values match known draw EIDs, TYPE is a known string |
| `test_vfs_ls_long_resources_real` | `vfs_ls(path="/resources", long=True)` → ID values are non-zero integers, SIZE is int or `-` |
| `test_vfs_ls_long_textures_real` | `vfs_ls(path="/textures", long=True)` → WIDTH and HEIGHT are positive integers |
| `test_vfs_ls_long_buffers_real` | `vfs_ls(path="/buffers", long=True)` → LENGTH is non-negative integer |
| `test_vfs_ls_long_shaders_real` | `vfs_ls(path="/shaders", long=True)` → STAGES is a comma-joined string like `"ps"` or `"vs,ps"` |
| `test_vfs_ls_long_backward_compat_real` | `vfs_ls(path="/passes")` without `long` → no `columns` key, children have only `name`+`kind` |

---

## Coverage Expectations

| Area | New cases | Notes |
|------|-----------|-------|
| Daemon handler (unit) | 14 | All path contexts + edge cases |
| CLI command (unit) | 8 | Flag behavior, rendering, mutex |
| Formatter (unit) | 5 | New `render_ls_long` function |
| GPU integration | 7 | Real capture validation |
| **Total** | **~34** | |

- All unit tests run without GPU (`pixi run test`)
- GPU tests run with `pixi run test-gpu`
- Overall coverage must remain >= 95%

---

## Test Matrix

| Dimension | Value |
|-----------|-------|
| Python | 3.10, 3.12 (pixi matrix) |
| Platform | Linux (primary) |
| GPU | Unit tests: none; Integration: real capture required |
| CI | `pixi run lint && pixi run test` |

### Fixtures and helpers

- Handler tests: `DaemonState` + `MockReplayController` from `tests/mocks/mock_renderdoc.py`; populate `vfs_tree`, `tex_map`, `buf_map`, `res_names`, `shader_meta` with synthetic data
- CLI tests: `CliRunner` + `monkeypatch` on `rdc.commands.vfs._daemon_call`
- Formatter tests: direct function calls, no fixtures needed
- GPU tests: session-scoped real-capture fixture already defined in `tests/integration/test_daemon_handlers_real.py`
