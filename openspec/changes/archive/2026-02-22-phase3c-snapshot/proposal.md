# Feature: phase3c-snapshot

## Summary

Add an `rdc snapshot <eid> -o dir/` command that captures a complete diagnostic snapshot of a
single draw event into a directory. The command orchestrates multiple existing daemon methods
(pipeline, shader_all, shader_disasm, rt_export, rt_depth) and writes their outputs as
individual files alongside a `manifest.json` index.

This is a CLI-side orchestration command only. No new daemon handlers or JSON-RPC methods are
introduced. All heavy lifting is delegated to existing daemon endpoints via `_daemon_call`.

## Problem

Debugging a draw call requires running 5+ separate `rdc` commands: pipeline state, shader
disassembly per stage, and render target exports. Users frequently need all of this data together
for offline analysis, bug reports, or CI artifact collection. There is no single command that
captures a complete per-draw snapshot.

## Design

### Command signature

```
rdc snapshot <eid> -o <dir> [--json]
```

- `eid` (required, int): Event ID of the draw call to snapshot.
- `-o / --output` (required, directory path): Output directory. Created if it does not exist.
- `--json` (optional, flag): Print the manifest to stdout as JSON instead of human-readable summary.

### Exit codes

- `0`: success (at least pipeline.json written)
- `1`: fatal error (no session, daemon unreachable, pipeline call fails)

### Algorithm

1. `mkdir -p` the output directory via `pathlib.Path.mkdir(parents=True, exist_ok=True)`.
2. Call `pipeline` with `{"eid": eid}` via `_daemon_call` -> write `pipeline.json`.
3. Call `shader_all` with `{"eid": eid}` -> get `{"eid": int, "stages": [{"stage": "vs", ...}, ...]}`.
4. For each stage in the response: call `shader_disasm` with `{"eid": eid, "stage": stage}` ->
   get `{"disasm": "...", "stage": "vs", "eid": int}` -> write `shader_{stage}.txt`.
5. For target index 0..7: call `rt_export` with `{"eid": eid, "target": i}` ->
   get `{"path": "/tmp/...", "size": N}`. Copy the temp file to `color{i}.png` in the output dir.
   Stop on first error (no more targets).
6. Call `rt_depth` with `{"eid": eid}` -> get `{"path": "/tmp/...", "size": N}`.
   Copy to `depth.png`. Skip silently if error (no depth target).
7. Write `manifest.json` with:
   ```json
   {
     "eid": 142,
     "timestamp": "2026-02-22T10:30:00Z",
     "files": ["pipeline.json", "shader_vs.txt", "shader_ps.txt", "color0.png", "depth.png"]
   }
   ```
8. Print human-readable summary or JSON manifest depending on `--json` flag.

### Non-fatal failure handling

Steps 4-6 involve calls that may fail for valid reasons (no shader at a stage, no color target
beyond index 0, no depth target). These failures are caught by intercepting `SystemExit(1)`
raised by `_daemon_call` and skipping the file. The command only fails fatally if step 2
(pipeline) fails, since that indicates the EID is invalid or the session is broken.

### File copy for binary exports

`rt_export` and `rt_depth` return `{"path": str}` pointing to a daemon-managed temp file.
The snapshot command copies this file to the output directory using `shutil.copy2`.

### Uses existing infrastructure

- `_daemon_call` from `rdc.commands.info` for all JSON-RPC communication
- `write_json` from `rdc.formatters.json_fmt` for JSON output
- `shutil.copy2` for binary file transfer
- `json.dumps` for writing `pipeline.json` and `manifest.json`

## Scope

### In scope
- `src/rdc/commands/snapshot.py`: new command module (~80 lines)
- `src/rdc/cli.py`: import + register `snapshot_cmd`
- `tests/unit/test_snapshot_command.py`: ~10 unit tests (monkeypatch `_daemon_call`)
- GPU integration test in `tests/integration/test_daemon_handlers_real.py`

### Out of scope
- New daemon handlers or JSON-RPC methods
- Diff/comparison between snapshots
- Video or animation capture
- Compression or archive format (tar/zip)
- Streaming output (all files written atomically)
