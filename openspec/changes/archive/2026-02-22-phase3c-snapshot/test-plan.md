# Test Plan: phase3c-snapshot

## Scope

### In scope
- `rdc snapshot` CLI command: argument parsing, output directory creation, file writing
- Orchestration of daemon calls: pipeline, shader_all, shader_disasm, rt_export, rt_depth
- Non-fatal error handling: missing shaders, missing color targets, missing depth
- Manifest generation with correct file list and timestamp
- JSON output mode (`--json`)
- Human-readable summary output (default mode)
- GPU integration test on `hello_triangle.rdc`

### Out of scope
- Daemon handler internals (already tested by existing handler tests)
- VFS routing or tree cache changes
- Binary content correctness of exported PNGs (tested in rt_export/rt_depth handler tests)

## Test Matrix

| Layer | Scope | File |
|-------|-------|------|
| Unit | Happy path: all files written | `tests/unit/test_snapshot_command.py` |
| Unit | Pipeline call failure = exit 1 | `tests/unit/test_snapshot_command.py` |
| Unit | No shaders: only pipeline + RT files | `tests/unit/test_snapshot_command.py` |
| Unit | No color targets: pipeline + shaders only | `tests/unit/test_snapshot_command.py` |
| Unit | No depth target: depth.png skipped | `tests/unit/test_snapshot_command.py` |
| Unit | Multiple color targets exported | `tests/unit/test_snapshot_command.py` |
| Unit | --json flag prints manifest JSON | `tests/unit/test_snapshot_command.py` |
| Unit | Output directory created if missing | `tests/unit/test_snapshot_command.py` |
| Unit | No session = exit 1 | `tests/unit/test_snapshot_command.py` |
| Unit | CLI registration: help shows snapshot | `tests/unit/test_snapshot_command.py` |
| GPU | Full snapshot on hello_triangle.rdc | `tests/integration/test_daemon_handlers_real.py` |

## Cases

### Happy path

1. **All files written**: mock `_daemon_call` to return valid responses for all 5 method types;
   create temp PNG files for rt_export/rt_depth paths to copy from; invoke
   `rdc snapshot 142 -o <tmpdir>`. Assert:
   - exit code 0
   - `pipeline.json` exists and is valid JSON with pipeline data
   - `shader_vs.txt` and `shader_ps.txt` exist with disassembly content
   - `color0.png` exists with correct binary content
   - `depth.png` exists with correct binary content
   - `manifest.json` exists with `"eid": 142`, `"files"` list of 5 entries,
     valid ISO 8601 `"timestamp"`

2. **Output directory created**: pass a non-existent nested directory path as `-o`;
   assert directory is created and files are written inside it.

3. **--json flag**: same mocks as case 1; invoke with `--json`; assert exit code 0;
   parse stdout as JSON; assert it matches the manifest structure with `eid`, `files`,
   `timestamp` keys.

### Partial failures (non-fatal)

4. **No shaders (shader_all returns empty stages)**: mock `shader_all` to return
   `{"eid": 142, "stages": []}`. Assert: no `shader_*.txt` files written;
   `manifest.json` `files` list omits shader files; exit code 0.

5. **No color targets**: mock `rt_export` to raise `SystemExit(1)` for target 0.
   Assert: no `color*.png` files; manifest omits them; exit code 0.

6. **No depth target**: mock `rt_depth` to raise `SystemExit(1)`.
   Assert: no `depth.png`; manifest omits it; exit code 0.

7. **Multiple color targets**: mock `rt_export` to succeed for targets 0, 1, 2 and
   raise `SystemExit(1)` for target 3. Assert: `color0.png`, `color1.png`, `color2.png`
   exist; no `color3.png`; manifest lists all three color files.

### Fatal failures

8. **Pipeline call fails**: mock `_daemon_call("pipeline", ...)` to raise `SystemExit(1)`.
   Assert: exit code 1; no files written in output directory (or directory may exist but
   is empty).

9. **No active session**: monkeypatch `load_session` to return None.
   Assert: exit code 1; stderr contains "no active session".

### CLI registration

10. **Help shows snapshot**: invoke `rdc --help`; assert `"snapshot"` appears in output.

## Assertions

### Exit codes
- `0`: at least `pipeline.json` and `manifest.json` written
- `1`: no session, daemon unreachable, or pipeline call failed
- `2`: CLI argument error (missing required args)

### File system contract
- Output directory is created with `parents=True, exist_ok=True`
- `pipeline.json`: valid JSON, contains the pipeline response data
- `shader_{stage}.txt`: plain text, one file per active shader stage
- `color{i}.png`: binary copy of daemon temp file, sequential from 0
- `depth.png`: binary copy of daemon temp file (may be absent)
- `manifest.json`: valid JSON with keys `"eid"` (int), `"files"` (list of str),
  `"timestamp"` (ISO 8601 string)

### Manifest contract
- `"eid"` matches the input EID argument
- `"files"` lists exactly the files that were successfully written (no extras, no missing)
- `"timestamp"` is a valid ISO 8601 datetime string
- File order in `"files"`: `pipeline.json` first, then shaders alphabetically by stage,
  then color targets by index, then depth.png

### _daemon_call usage
- `pipeline` called with `{"eid": eid}`
- `shader_all` called with `{"eid": eid}`
- `shader_disasm` called with `{"eid": eid, "stage": <stage>}` per active stage
- `rt_export` called with `{"eid": eid, "target": i}` for i in 0..7 until first error
- `rt_depth` called with `{"eid": eid}`

### Error response
- Fatal errors print to stderr via `click.echo(..., err=True)` or `_daemon_call` error path
- Non-fatal errors are silently skipped (no stderr output for missing targets/shaders)

## Risks & Rollback

| Risk | Impact | Mitigation |
|------|--------|------------|
| `rt_export` temp file deleted before copy | `color{i}.png` is empty or missing | Copy immediately after each `rt_export` call; temp files persist for daemon lifetime |
| `SystemExit` from `_daemon_call` not caught in non-fatal paths | Command exits prematurely | Wrap each non-fatal call in `try/except SystemExit`; unit tests verify each skip path |
| Timestamp format varies by platform | Manifest `timestamp` not parseable | Use `datetime.datetime.now(datetime.UTC).isoformat()` for consistent format |
| Large number of color targets causes slow export | UX lag | Cap at 8 targets (practical maximum for any GPU API) |
| Rollback | -- | Revert branch; no master changes until PR squash-merge |
