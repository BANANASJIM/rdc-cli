# Test Plan: 2026-06-09-rt-depth-flag

## Scope

### In scope
- `--depth` routes to `/draws/{eid}/targets/depth.png`
- `--depth` + explicit `--target` raises `UsageError`
- `--depth` + `-o` writes output file
- `--depth` without `--overlay` reaches `_export_vfs_path`
- Remote daemon path (pid==0) with `--depth`

### Out of scope
- `rt_depth` daemon handler correctness (shipped in PR #237, covered by prior tests)
- `--overlay` behaviour (no change)

## Test Matrix

| Layer | Test Type | File |
|-------|-----------|------|
| Unit | `--depth` flag routing | `tests/unit/test_export_commands.py` (extend `TestRtCmd`) |
| Unit | `--depth` + `--target` mutual exclusion | `tests/unit/test_export_commands.py` |
| Unit | `--depth` + `-o` output file written | `tests/unit/test_export_commands.py` |
| Unit | remote pid==0 path with `--depth` | `tests/unit/test_export_commands.py` |
| Unit | `--depth` + `--overlay` ignores depth (no error) | `tests/unit/test_export_commands.py` |
| Manual | real GPU: local + remote | see below |

## Unit Cases (extend `TestRtCmd` in `test_export_commands.py`)

### `test_rt_depth_routes_to_depth_png`

Monkeypatch `call` and `_deliver_binary`. Invoke `rt_cmd` with `["100", "--depth", "-o",
str(out_file)]`. Assert exit code 0. Assert `vfs_ls` was called with path
`/draws/100/targets/depth.png`.

### `test_rt_depth_with_explicit_target_raises_usage_error`

Invoke `rt_cmd` with `["100", "--depth", "--target", "1", "-o", str(out_file)]`. Assert
exit code non-zero. Assert output/error contains `"mutually exclusive"`.

### `test_rt_depth_target_none_defaults_to_color0`

Invoke `rt_cmd` with `["100", "-o", str(out_file)]` (no `--depth`, no `--target`). Assert
`vfs_ls` was called with path `/draws/100/targets/color0.png`. Confirms sentinel default
behaviour is preserved.

### `test_rt_depth_remote_pid0_writes_output`

Monkeypatch `rdc.commands.vfs._load_session` to return a session with `pid=0`,
`rdc.commands.vfs.fetch_remote_file` to return PNG bytes, and
`rdc.commands.vfs._stdout_is_tty` to `lambda: False`. Invoke `rt_cmd` with
`["100", "--depth", "-o", str(out_file)]`.

NOTE (corrected against actual code): `_export_vfs_path` → `_deliver_binary` does NOT
emit any "--output required" error for the VFS path. For `pid==0` it calls
`fetch_remote_file(temp_path)` and, when `output` is set, writes the bytes to the output
file (vfs.py lines 234-244). There is no remote "--output is required" guard on this
path; that guard exists only in the `--overlay` branch of `rt_cmd`. So:

- Assert exit code 0.
- Assert `vfs_ls` was called with `/draws/100/targets/depth.png`.
- Assert `out_file` was written with the mocked PNG bytes.

(If the remote no-`-o` behaviour is also worth covering: under `CliRunner`,
`_stdout_is_tty()` is False, so `--depth` with no `-o` and `pid==0` writes bytes to
stdout and exits 0 — it does NOT error. Per the settled main-agent ruling, `--depth`
without `-o` behaves exactly like color export, i.e. no special TTY/remote guard.)

### `test_rt_depth_with_overlay_ignores_depth`

Per the design, `--overlay` takes priority and `--depth` is silently ignored (the
`--overlay` branch early-returns before the depth/target logic, so no mutual-exclusion
error is raised for `--depth + --overlay`). Monkeypatch `call` so `rt_overlay` returns a
`path` and `fetch_remote_file` returns bytes. Invoke `rt_cmd` with
`["100", "--overlay", "depth", "--depth", "-o", str(out_file)]`. Assert exit code 0,
assert `rt_overlay` was called (not `vfs_ls` for `depth.png`), and `vfs_ls` was NOT
called with `/draws/100/targets/depth.png`. Confirms `--depth` is inert under `--overlay`
and does not trip the mutual-exclusion guard.

## Manual Real-GPU Verify

Prerequisite: vkcube capture with a known draw EID that has a depth attachment (any 3D
draw should qualify).

1. **Local mode**:
   ```
   rdc open capture.rdc
   rdc rt <EID> --depth -o /tmp/depth_local.png
   ```
   Assert exit code 0, `/tmp/depth_local.png` is a valid PNG, non-empty.

2. **Remote proxy mode**:
   ```
   rdc open capture.rdc --proxy host:port
   rdc rt <EID> --depth -o /tmp/depth_remote.png
   ```
   Assert exit code 0, file written, pixel values plausible (non-constant, depth values
   visible as greyscale gradient).

3. **Mutual exclusion error**:
   ```
   rdc rt <EID> --depth --target 0 -o /tmp/d.png
   ```
   Assert non-zero exit with `"mutually exclusive"` in output.

4. **`--overlay depth` still works** (regression):
   ```
   rdc rt <EID> --overlay depth -o /tmp/depth_overlay.png
   ```
   Assert exit code 0. File is a colour-mapped overlay PNG (distinct from raw depth).
