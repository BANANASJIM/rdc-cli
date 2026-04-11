---
name: rdc-cli
description: >
  Use this skill when working with RenderDoc capture files (.rdc), analyzing GPU frames,
  tracing shaders, inspecting draw calls, or running CI assertions against GPU captures.
  Trigger phrases: "open capture", "rdc file", ".rdc", "renderdoc", "shader debug",
  "pixel trace", "draw calls", "GPU frame", "assert pixel", "export render target".
---

# rdc-cli Skill

## Overview

rdc-cli is a Unix-friendly command-line interface for RenderDoc GPU captures. It provides a daemon-backed architecture using JSON-RPC over TCP, a virtual filesystem (VFS) path namespace for navigating capture internals, and composable commands designed for shell pipelines, scripting, and CI assertions.

Install: `pip install rdc-cli` (requires a local RenderDoc build with Python bindings).
Check setup: `rdc doctor`.

## Core Workflow

Follow this session lifecycle for any capture analysis task:

1. **Open** a capture:
   - Local: `rdc open path/to/capture.rdc`
   - Remote replay (Proxy): `rdc open capture.rdc --proxy host:port`
   - Split thin-client: `rdc open --connect host:port --token TOKEN`
   - Android device: `rdc open capture.rdc --android [--serial SERIAL]`
2. **Inspect** metadata: `rdc info`, `rdc stats`, `rdc events`
3. **Navigate** the VFS: `rdc ls /`, `rdc ls /textures`, `rdc cat /pipelines/0`
4. **Analyze** specifics: `rdc shaders`, `rdc pipeline`, `rdc resources`, `rdc bindings`
5. **Debug** shaders: `rdc debug pixel X Y`, `rdc debug vertex EID VTXID`, `rdc debug thread EID GX GY GZ`
6. **Export** data: `rdc texture EID -o out.png`, `rdc rt EID`, `rdc buffer EID -o buf.bin`, `rdc log`
7. **Close** the session: `rdc close`

### Session Management

- Default session name: `default` (or value of `$RDC_SESSION`).
- Override per-command: `rdc --session myname open capture.rdc`.
- Check active session: `rdc status`.
- Navigate to a specific event: `rdc goto EID`.

## Output Formats

All list/table commands default to TSV (tab-separated values) with a header row, suitable for `cut`, `awk`, and `sort`.

| Flag | Format | Use Case |
|------|--------|----------|
| *(default)* | TSV with header | Human reading, shell pipelines |
| `--no-header` | TSV without header | Piping to `awk`/`cut` without stripping |
| `--json` | JSON array | Structured processing with `jq` |
| `--jsonl` | Newline-delimited JSON | Streaming processing, large datasets |
| `-q` / `--quiet` | Minimal (single column) | Extracting IDs for loops |

Example -- get all draw call EIDs as a plain list:

```bash
rdc draws -q
```

Example -- JSON pipeline with jq:

```bash
rdc events --json | jq '.[] | select(.type == "DrawIndexed")'
```

## Render Pass Analysis

### List passes (Phase 8 columns)

`rdc passes` outputs 6 columns: NAME, DRAWS, DISPATCHES, TRIANGLES, BEGIN_EID, END_EID.

```bash
rdc passes                          # TSV table
rdc passes --json                   # includes load_ops/store_ops per pass
rdc passes --deps --table           # per-pass READS/WRITES/LOAD/STORE
```

### Inspect a single pass

`rdc pass <name>` shows enriched attachments: resource name, format, dimensions, and load/store ops.

```bash
rdc pass GBuffer
rdc pass GBuffer --json
rdc pass 0                          # by 0-based index
```

### Detect dead render targets

`rdc unused-targets` finds render targets written but never consumed by visible output. Columns: ID, NAME, WRITTEN_BY, WAVE.

```bash
rdc unused-targets                  # TSV
rdc unused-targets --json           # structured
rdc unused-targets -q               # one resource ID per line (for scripting)
```

### Frame statistics

`rdc stats` outputs three sections: Per-Pass Breakdown, Top Draws by Triangle Count, and Largest Resources.

```bash
rdc stats                           # all three sections
rdc stats --json                    # includes largest_resources array
```

GL/GLES/D3D11 captures without native BeginPass/EndPass markers get synthetic pass inference automatically — no extra flags needed.

## Common Tasks

### Find all draw calls

```bash
rdc draws
rdc draws --pass "GBuffer" --json
```

### Trace a pixel

```bash
rdc debug pixel 512 384
rdc debug pixel 512 384 --json    # structured output
rdc debug pixel 512 384 --trace   # full step-by-step trace
```

### Search shaders by name or source

```bash
rdc search "main" --type shader
rdc shaders --name "GBuffer*"
```

### Export render targets

```bash
rdc rt EID -o output.png
rdc texture EID --format png -o tex.png
```

### Browse VFS paths

```bash
rdc ls /
rdc ls /textures -l
rdc tree /pipelines --depth 2
rdc cat /events/42
```

### Inspect pipeline state at a draw call

```bash
rdc goto EID
rdc pipeline --json
rdc bindings --json
```

### Compare state before/after a pass

```bash
rdc goto 100 && rdc pipeline --json > before.json
rdc goto 200 && rdc pipeline --json > after.json
diff before.json after.json
```

## CI Assertions

rdc-cli provides assertion commands that exit non-zero on failure, designed for automated testing pipelines:

| Command | Purpose |
|---------|---------|
| `rdc assert-pixel X Y --expect R,G,B,A` | Assert pixel color at coordinates |
| `rdc assert-clean` | Assert no validation errors in capture |
| `rdc assert-count --type DrawIndexed --min N` | Assert minimum draw call count |
| `rdc assert-state FIELD VALUE` | Assert pipeline state field matches value |
| `rdc assert-image EID --ref reference.png` | Assert render target matches reference image |

Example CI script:

```bash
#!/bin/bash
set -e
rdc open test_capture.rdc
rdc assert-clean
rdc assert-count --type DrawIndexed --min 10
rdc assert-pixel 256 256 --expect 1.0,0.0,0.0,1.0
rdc close
```

## Shader Edit-Replay

Modify and replay shaders without recompiling the application:

```bash
rdc shader-encodings EID          # list available encodings
rdc shader EID --source > s.frag  # extract shader source
# ... edit s.frag ...
rdc shader-build s.frag --encoding glsl  # compile edited shader
rdc shader-replace EID s.frag     # hot-swap into capture
rdc shader-restore EID            # revert single shader
rdc shader-restore-all            # revert all modifications
```

## Remote Capture Workflow

rdc-cli wraps `renderdoccmd remoteserver` to support PC-to-PC remote captures.

- `rdc serve [--port PORT] [--allow-ips CIDR] [--no-exec] [--daemon]` — launch remoteserver on the target machine
- `rdc remote connect <host:port>` — save remote connection state
- `rdc remote list` — enumerate capturable apps on the remote
- `rdc remote capture <app> -o frame.rdc [--args ...] [--frame N] [--keep-remote]` — inject, capture, and transfer back. `--keep-remote` skips the transfer and prints the remote path; replay it with `rdc open <path> --proxy host:port`. (The CLI's own `next:` hint currently still references the deprecated `--remote` alias for `--proxy`.)
- `rdc open frame.rdc --proxy host:port` — remote-backed replay (daemon local, GPU remote)

`remote_state.py` persists the last connected host so subsequent `rdc remote list` can omit `--url`.

## Split Mode (thin client)

Split mode decouples CLI and daemon — run the daemon where the GPU is and connect from a machine that doesn't need the renderdoc module. Useful when the analyst's laptop is macOS/Windows and the GPU is on a Linux server.

- Server side: `rdc open capture.rdc --listen [ADDR[:PORT]]`
  - Prints these four labeled lines to stdout (among other status output): `host: ADDR`, `port: PORT`, `token: TOKEN`, `connect with: rdc open --connect ADDR:PORT --token TOKEN`
- Client side: `rdc open --connect HOST:PORT --token TOKEN`

SSH tunnel tip (use the port from `--listen`, or `rdc serve`'s default `39920`): `ssh -L 39920:localhost:39920 user@server`, then connect to `localhost:39920`.

Every normal command (`rdc draws`, `rdc rt`, ...) works transparently in Split mode. Binary exports use `file_read` RPC with raw binary frames — no base64 overhead.

## Android Workflow

- Prerequisite: the RenderDoc APK must already be installed on the host via `rdc setup-renderdoc --android` (upstream) or `--android --arm` (ARM PS fork for Mali). `rdc android setup` does not push the APK itself.
- `rdc android setup [--serial SERIAL]` — starts remoteserver on the device via RenderDoc's Device Protocol API (`StartRemoteServer`), sets adb forward, saves remote state.
- `rdc android capture <activity> [--serial SERIAL] [--timeout N] [--port PORT] [-o out.rdc]` — GPU debug layers based capture (works around EMUI/Mali injection limitations).
- `rdc android stop [--serial SERIAL]` — stops the remoteserver and cleans state.
- For remote replay: `rdc open frame.rdc --android [--serial SERIAL]` — this is the only form that rewrites the saved `adb://SERIAL` to the forwarded `localhost:PORT`. Passing `--proxy adb://SERIAL` directly bypasses the rewrite and is known to crash the daemon (see `session.py:_resolve_android_url`).

Hardware matrix: Adreno is the happy path; Mali may need the ARM Performance Studio fork (see `rdc setup-renderdoc --android --arm`).

## Troubleshooting

Always run `rdc doctor` first. It reports status for renderdoc module, renderdoccmd, adb, Android APK, and platform-specific toolchains. Only the missing-renderdoc-module case emits a dedicated build-hint block; other checks surface inline hints in the detail column, so read each failing line rather than relying on a uniform next-step list.

Common failure categories (conceptual, not literal error strings — map from the text the tool actually emits):

- **network / connect failed** — remote host unreachable, firewall, wrong port. Verify `rdc serve` is running on the target.
- **version mismatch** — host and target RenderDoc versions differ. Re-run `rdc setup-renderdoc` or `rdc setup-renderdoc --android` to align.
- **inject failed / ident=0** — injection blocked (Android EMUI, macOS SIP, Windows privilege). Run `rdc doctor` and check the platform-specific detail.
- **OpenCapture unsupported** — local GPU can't replay the capture's API surface; switch to `--proxy` or `--android` remote replay.
- **not loaded / no session** — forgot `rdc open`; use `rdc status` to inspect.

For long operations (large capture transfers, remote replay init), the CLI has limited progress feedback — this is a known UX gap, not a hang. Wait up to the `--timeout` value before concluding failure.

## Command Reference

For the complete list of all commands with their arguments, options, types, and defaults, see [references/commands-quick-ref.md](references/commands-quick-ref.md).
