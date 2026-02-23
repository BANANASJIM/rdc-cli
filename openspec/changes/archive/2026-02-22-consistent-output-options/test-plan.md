# Test Plan: Consistent Output Options

## Overview

This test plan covers new CLI option tests added to existing unit test files. No new daemon handler tests are required — the changes are purely in CLI output formatting. No GPU is required.

Estimated new test cases: ~50
Target: maintain >= 95% coverage.

---

## Fixtures and Helpers

All CLI tests follow the pattern established in `test_resources_commands.py` and `test_counters_commands.py`:

- Commands using `call()`: monkeypatch `load_session` and `send_request` on `rdc.commands._helpers`.
- Commands importing `_daemon_call` from `rdc.commands.info` (counters, usage, pixel, vfs): monkeypatch `_daemon_call` directly on the command module.
- Use `click.testing.CliRunner` to invoke commands.
- `write_jsonl` / `write_tsv` are not mocked — test through real output.

---

## Unit Tests

### `tests/unit/test_resources_commands.py` — `resources` command

| ID | Test | Assertion |
|----|------|-----------|
| O-01 | `test_resources_no_header` | Invoke `resources` with `--no-header`. Output does NOT contain `ID\tTYPE\tNAME`. Row data present. |
| O-02 | `test_resources_jsonl` | Invoke `resources` with `--jsonl`. Each output line is valid JSON with `"id"` key. |
| O-03 | `test_resources_quiet` | Invoke `resources` with `-q`. Output contains only resource ID integers, one per line. No header, no type, no name. |

### `tests/unit/test_resources_commands.py` — `passes` command

| ID | Test | Assertion |
|----|------|-----------|
| O-04 | `test_passes_no_header` | Invoke `passes` with `--no-header`. Output does NOT contain `NAME\tDRAWS`. Row data present. |
| O-05 | `test_passes_jsonl` | Invoke `passes` with `--jsonl`. Each line is valid JSON with `"name"` key. |
| O-06 | `test_passes_quiet` | Invoke `passes` with `-q`. Output contains only pass names, one per line. No header, no draw count. |

### `tests/unit/test_pipeline_commands.py` (or existing pipeline test file) — `bindings` command

| ID | Test | Assertion |
|----|------|-----------|
| O-07 | `test_bindings_no_header` | Invoke `bindings` with `--no-header`. Output does NOT contain `EID\tSTAGE\tKIND`. Row data present. |
| O-08 | `test_bindings_jsonl` | Invoke `bindings` with `--jsonl`. Each line is valid JSON with `"eid"` key. |
| O-09 | `test_bindings_quiet` | Invoke `bindings` with `-q`. Output contains only EID integers, one per line. |

### `tests/unit/test_pipeline_commands.py` — `shaders` command

| ID | Test | Assertion |
|----|------|-----------|
| O-10 | `test_shaders_no_header` | Invoke `shaders` with `--no-header`. Output does NOT contain `SHADER\tSTAGES\tUSES`. Row data present. |
| O-11 | `test_shaders_jsonl` | Invoke `shaders` with `--jsonl`. Each line is valid JSON with `"shader"` key. |
| O-12 | `test_shaders_quiet` | Invoke `shaders` with `-q`. Output contains only shader hash strings, one per line. |

### `tests/unit/test_counters_commands.py` — `counters --list` path

| ID | Test | Assertion |
|----|------|-----------|
| O-13 | `test_counters_list_no_header` | Invoke `counters --list --no-header`. Output does NOT contain `ID\tNAME\tUNIT`. Counter rows present. |
| O-14 | `test_counters_list_jsonl` | Invoke `counters --list --jsonl`. Each line is valid JSON with `"id"` and `"name"` keys. |
| O-15 | `test_counters_list_quiet` | Invoke `counters --list -q`. Output contains only counter ID integers, one per line. |

### `tests/unit/test_counters_commands.py` — `counters` fetch path

| ID | Test | Assertion |
|----|------|-----------|
| O-16 | `test_counters_fetch_no_header` | Invoke `counters --no-header`. Output does NOT contain `EID\tCOUNTER\tVALUE`. Rows present. |
| O-17 | `test_counters_fetch_jsonl` | Invoke `counters --jsonl`. Each line is valid JSON with `"eid"` and `"counter"` keys. |
| O-18 | `test_counters_fetch_quiet` | Invoke `counters -q`. Output contains only EID integers, one per line. |

### `tests/unit/test_usage_commands.py` — `usage` single-resource path

| ID | Test | Assertion |
|----|------|-----------|
| O-19 | `test_usage_single_no_header` | Invoke `usage 97 --no-header`. Output does NOT contain `EID\tUSAGE`. Entries present. |
| O-20 | `test_usage_single_jsonl` | Invoke `usage 97 --jsonl`. Each line is valid JSON with `"eid"` and `"usage"` keys. |
| O-21 | `test_usage_single_quiet` | Invoke `usage 97 -q`. Output contains only EID integers, one per line. |

### `tests/unit/test_usage_commands.py` — `usage --all` path

| ID | Test | Assertion |
|----|------|-----------|
| O-22 | `test_usage_all_no_header` | Invoke `usage --all --no-header`. Output does NOT contain `ID\tNAME\tEID\tUSAGE`. Rows present. |
| O-23 | `test_usage_all_jsonl` | Invoke `usage --all --jsonl`. Each line is valid JSON with `"id"`, `"name"`, `"eid"`, `"usage"` keys. |
| O-24 | `test_usage_all_quiet` | Invoke `usage --all -q`. Output contains only resource ID integers, one per line. |

### `tests/unit/test_info_commands.py` (or `test_cli.py`) — `log` command

| ID | Test | Assertion |
|----|------|-----------|
| O-25 | `test_log_jsonl` | Invoke `log --jsonl`. Each line is valid JSON with `"level"`, `"eid"`, `"message"` keys. |
| O-26 | `test_log_quiet` | Invoke `log -q`. Output contains only EID integers, one per line. No header. |
| O-27 | `test_log_no_header_regression` | Invoke `log --no-header` (existing option now absorbed by decorator). Header absent, messages present. |

### `tests/unit/test_pixel_history_commands.py` — `pixel` command

| ID | Test | Assertion |
|----|------|-----------|
| O-28 | `test_pixel_jsonl` | Invoke `pixel 100 200 --jsonl`. Each line is valid JSON with `"eid"` key. |
| O-29 | `test_pixel_quiet` | Invoke `pixel 100 200 -q`. Output contains only EID integers, one per line. No header. |
| O-30 | `test_pixel_no_header_regression` | Invoke `pixel 100 200 --no-header` (existing option now absorbed by decorator). Header absent, modification rows present. |

### `tests/unit/test_vfs_commands.py` — `ls -l` command

| ID | Test | Assertion |
|----|------|-----------|
| O-31 | `test_ls_long_no_header` | Invoke `ls -l --no-header /`. Output does NOT contain the TSV column header line. Child rows present. |
| O-32 | `test_ls_long_jsonl` | Invoke `ls -l --jsonl /`. Each line is valid JSON dict with `"name"` key. |
| O-33 | `test_ls_long_quiet` | Invoke `ls -l -q /`. Output contains only entry names, one per line. No TSV header. |
| O-34 | `test_ls_long_options_ignored_without_l` | Invoke `ls --no-header /` (without `-l`). Exit code 0, regular ls output (no error). Options are silently no-ops without `-l`. |

### `tests/unit/test_unix_helpers_commands.py` — `shader-map` command

| ID | Test | Assertion |
|----|------|-----------|
| O-35 | `test_shader_map_json` | Invoke `shader-map --json`. Output is valid JSON array with rows containing `"eid"` key. |
| O-36 | `test_shader_map_jsonl` | Invoke `shader-map --jsonl`. Each line is valid JSON with `"eid"`, `"vs"`, `"ps"` keys. |
| O-37 | `test_shader_map_quiet` | Invoke `shader-map -q`. Output contains only EID integers, one per line. No header. |
| O-38 | `test_shader_map_no_header_regression` | Invoke `shader-map --no-header` (existing option). Header absent, rows present. Regression guard. |

### `tests/unit/test_vfs_formatter.py` — `render_ls_long`

| ID | Test | Assertion |
|----|------|-----------|
| O-39 | `test_render_ls_long_no_header_true` | Call `render_ls_long(children, columns, no_header=True)`. Returned string does NOT start with the column header row. Child data rows present. |
| O-40 | `test_render_ls_long_no_header_false` | Call `render_ls_long(children, columns, no_header=False)` (default). First line is the TSV header. Regression guard. |

---

## Regression Guards

For every command that already has `--no-header`, verify the existing behavior is unchanged:

| ID | Test | Assertion |
|----|------|-----------|
| O-41 | `test_resources_default_has_header` | Invoke `resources` with no flags. Header `ID\tTYPE\tNAME` present. |
| O-42 | `test_passes_default_has_header` | Invoke `passes` with no flags. Header `NAME\tDRAWS` present. |
| O-43 | `test_bindings_default_has_header` | Invoke `bindings` with no flags. Header `EID\tSTAGE\tKIND\tSET\tSLOT\tNAME` present. |
| O-44 | `test_shaders_default_has_header` | Invoke `shaders` with no flags. Header `SHADER\tSTAGES\tUSES` present. |
| O-45 | `test_counters_list_default_has_header` | Invoke `counters --list` with no extra flags. Header `ID\tNAME\tUNIT\tTYPE\tCATEGORY` present. |
| O-46 | `test_counters_fetch_default_has_header` | Invoke `counters` with no extra flags. Header `EID\tCOUNTER\tVALUE\tUNIT` present. |
| O-47 | `test_usage_single_default_has_header` | Invoke `usage 97` with no extra flags. Header `EID\tUSAGE` present. |
| O-48 | `test_usage_all_default_has_header` | Invoke `usage --all` with no extra flags. Header `ID\tNAME\tEID\tUSAGE` present. |
| O-49 | `test_log_default_has_header` | Invoke `log` with no extra flags. Header `LEVEL\tEID\tMESSAGE` present. |
| O-50 | `test_pixel_default_has_header` | Invoke `pixel 100 200` with no extra flags. Header `EID\tFRAG\tDEPTH\tPASSED\tFLAGS` present. |

---

## CLI Test Patterns

### Pattern A — commands using `call()` (resources, passes, bindings, shaders)

```python
def _patch(monkeypatch, response):
    import rdc.commands._helpers as mod
    session = type("S", (), {"host": "127.0.0.1", "port": 1, "token": "tok"})()
    monkeypatch.setattr(mod, "load_session", lambda: session)
    monkeypatch.setattr(mod, "send_request", lambda _h, _p, _payload: {"result": response})
```

### Pattern B — commands importing `_daemon_call` (counters, usage, pixel, vfs)

```python
def _patch(monkeypatch, response):
    monkeypatch.setattr(counters_mod, "_daemon_call", lambda method, params=None: response)
```

### Pattern C — log command (uses `call()` via `info.py`)

```python
def _patch(monkeypatch, response):
    import rdc.commands._helpers as mod
    session = type("S", (), {"host": "127.0.0.1", "port": 1, "token": "tok"})()
    monkeypatch.setattr(mod, "load_session", lambda: session)
    monkeypatch.setattr(mod, "send_request", lambda _h, _p, _payload: {"result": response})
```

### JSONL validation helper

```python
import json

def parse_jsonl(output: str) -> list[dict]:
    return [json.loads(line) for line in output.strip().splitlines()]
```

---

## Coverage Expectations

| Area | New tests | Notes |
|------|-----------|-------|
| `resources` options | 3 + 1 regression | O-01–O-03, O-41 |
| `passes` options | 3 + 1 regression | O-04–O-06, O-42 |
| `bindings` options | 3 + 1 regression | O-07–O-09, O-43 |
| `shaders` options | 3 + 1 regression | O-10–O-12, O-44 |
| `counters --list` options | 3 + 1 regression | O-13–O-15, O-45 |
| `counters` fetch options | 3 + 1 regression | O-16–O-18, O-46 |
| `usage` single options | 3 + 1 regression | O-19–O-21, O-47 |
| `usage --all` options | 3 + 1 regression | O-22–O-24, O-48 |
| `log` options | 3 + 1 regression | O-25–O-27, O-49 |
| `pixel` options | 3 + 1 regression | O-28–O-30, O-50 |
| `ls -l` options | 4 | O-31–O-34 |
| `shader-map` options | 4 | O-35–O-38 |
| `render_ls_long` | 2 | O-39–O-40 |
| **Total** | **~50** | |

- All tests must pass with `pixi run test` (no GPU).
- Overall coverage target: maintain >= 95%.

---

## Test Matrix

| Dimension | Value |
|-----------|-------|
| Python | 3.10, 3.12 (pixi matrix) |
| Platform | Linux (primary) |
| GPU | Not required |
| CI | `pixi run lint && pixi run test` |
