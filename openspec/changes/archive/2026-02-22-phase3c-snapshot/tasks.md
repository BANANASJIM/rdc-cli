# Tasks: phase3c-snapshot

## Phase A: Tests first

### CLI argument parsing
- [ ] In `tests/unit/test_snapshot_command.py`, add `test_help_shows_snapshot`: invoke `rdc --help`; assert `"snapshot"` in output
- [ ] Add `test_missing_eid_exits_2`: invoke `rdc snapshot -o /tmp/out`; assert exit code 2 (Click missing argument)
- [ ] Add `test_missing_output_exits_2`: invoke `rdc snapshot 142`; assert exit code 2 (Click missing option)

### Happy path
- [ ] Add `test_snapshot_happy_path`: mock `_daemon_call` to return valid responses for all 5 method types; create temp PNG files for rt_export/rt_depth paths to copy from; invoke `rdc snapshot 142 -o <tmpdir>`; assert:
  - exit code 0
  - `pipeline.json` exists and is valid JSON with pipeline data
  - `shader_vs.txt` and `shader_ps.txt` exist with disassembly content
  - `color0.png` exists with correct binary content
  - `depth.png` exists with correct binary content
  - `manifest.json` exists with `"eid": 142`, `"files"` list of 5 entries, valid ISO 8601 `"timestamp"`
- [ ] Add `test_snapshot_creates_output_dir`: pass non-existent nested dir as `-o`; assert dir created and files written
- [ ] Add `test_snapshot_json_output`: same mocks; invoke with `--json`; parse stdout as JSON; assert manifest structure with `eid`, `files`, `timestamp`

### Non-fatal failures
- [ ] Add `test_snapshot_no_shaders`: mock `shader_all` returns `{"eid": 142, "stages": []}`; assert no `shader_*.txt` files; manifest omits them; exit code 0
- [ ] Add `test_snapshot_no_color_targets`: mock `rt_export` raises `SystemExit(1)` for target 0; assert no `color*.png`; manifest omits them; exit code 0
- [ ] Add `test_snapshot_no_depth`: mock `rt_depth` raises `SystemExit(1)`; assert no `depth.png`; manifest omits it; exit code 0
- [ ] Add `test_snapshot_multiple_color_targets`: mock `rt_export` succeeds for targets 0, 1, 2 then raises `SystemExit(1)` for target 3; assert `color0.png`, `color1.png`, `color2.png` exist; manifest lists 3 color files

### Fatal failures
- [ ] Add `test_snapshot_pipeline_fails`: mock `_daemon_call("pipeline", ...)` raises `SystemExit(1)`; assert exit code 1
- [ ] Add `test_snapshot_no_session`: monkeypatch `load_session` to return None; assert exit code 1

## Phase B: Implementation

### New file: `src/rdc/commands/snapshot.py`
- [ ] Create `src/rdc/commands/snapshot.py` with imports:
  ```python
  from __future__ import annotations
  import datetime
  import json
  import shutil
  from pathlib import Path
  from typing import Any
  import click
  from rdc.commands.info import _daemon_call
  from rdc.formatters.json_fmt import write_json
  ```
- [ ] Implement `_try_call(method: str, params: dict[str, Any]) -> dict[str, Any] | None` helper that wraps `_daemon_call` in `try/except SystemExit` and returns `None` on failure
- [ ] Implement `snapshot_cmd` Click command:
  - `@click.command("snapshot")`
  - `@click.argument("eid", type=int)`
  - `@click.option("-o", "--output", required=True, type=click.Path(), help="Output directory")`
  - `@click.option("--json", "use_json", is_flag=True, help="JSON output")`
- [ ] Step 1: Create output dir with `Path(output).mkdir(parents=True, exist_ok=True)`
- [ ] Step 2: Call `_daemon_call("pipeline", {"eid": eid})` (fatal on failure); write result to `pipeline.json` via `json.dumps` with indent=2
- [ ] Step 3: Call `_try_call("shader_all", {"eid": eid})`; iterate returned stages
- [ ] Step 4: For each stage, call `_try_call("shader_disasm", {"eid": eid, "stage": s["stage"]})`; write `shader_{stage}.txt` with the `"disasm"` field content
- [ ] Step 5: Loop target 0..7, call `_try_call("rt_export", {"eid": eid, "target": i})`; on success `shutil.copy2(result["path"], out_dir / f"color{i}.png")`; on failure break loop
- [ ] Step 6: Call `_try_call("rt_depth", {"eid": eid})`; on success copy to `depth.png`
- [ ] Step 7: Build manifest dict with `"eid"`, `"timestamp"` (UTC ISO 8601), `"files"` (list of written filenames); write `manifest.json`
- [ ] Step 8: If `--json`, call `write_json(manifest)`; else print human-readable summary with `click.echo`
- [ ] Track written files in a `files: list[str]` accumulator; append each filename on successful write

### Register command
- [ ] In `src/rdc/cli.py`, add import: `from rdc.commands.snapshot import snapshot_cmd`
- [ ] Add `main.add_command(snapshot_cmd, name="snapshot")` after `assert-image`

### Verify unit tests
- [ ] Run `pixi run test -k test_snapshot` -- all tests green

## Phase C: Integration

- [ ] Run full unit test suite: `pixi run test` -- all tests green, coverage >= 80%
- [ ] Run lint and type check: `pixi run lint` -- zero ruff errors, zero mypy strict errors
- [ ] GPU test: in `tests/integration/test_daemon_handlers_real.py`, add `test_snapshot_gpu`:
  - Use session-scoped daemon state fixture
  - Pick a valid draw EID from the hello_triangle capture
  - Create a temp directory
  - Simulate the snapshot orchestration: call `pipeline`, `shader_all`, `shader_disasm`, `rt_export`, `rt_depth` handlers directly
  - Assert `pipeline` response has `"row"` key
  - Assert `shader_all` returns at least one stage (vs or ps)
  - Assert `rt_export` target 0 returns `"path"` pointing to an existing file
  - Assert the temp file has non-zero size
- [ ] Run GPU tests: `RENDERDOC_PYTHON_PATH=/home/jim_z/Dev/renderdoc-src/build-py314/lib pixi run test-gpu -k test_snapshot`

## Phase D: Verify

- [ ] `pixi run check` passes (= lint + typecheck + test, all green)
- [ ] Manual: `rdc snapshot <eid> -o /tmp/snap` on hello_triangle capture; verify all expected files present
- [ ] Manual: `rdc snapshot <eid> -o /tmp/snap --json` prints valid JSON manifest
- [ ] Manual: verify manifest.json `files` list matches actual directory contents
- [ ] Archive: move `openspec/changes/2026-02-22-phase3c-snapshot/` -> `openspec/changes/archive/`
- [ ] Update `进度跟踪.md` in Obsidian vault
