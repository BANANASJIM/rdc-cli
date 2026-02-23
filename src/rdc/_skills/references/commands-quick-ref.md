# rdc-cli Command Quick Reference

## `rdc assert-clean`

Assert capture log has no messages at or above given severity.

**Options:**

| Flag | Help | Type | Default |
|------|------|------|---------|
| `--min-severity` | Minimum severity threshold. | choice | HIGH |
| `--json` | JSON output. | flag |  |

## `rdc assert-count`

Assert a capture metric satisfies a numeric comparison.

**Arguments:**

| Name | Type | Required |
|------|------|----------|
| `what` | choice | yes |

**Options:**

| Flag | Help | Type | Default |
|------|------|------|---------|
| `--expect` | Expected count value. | integer |  |
| `--op` | Comparison operator. | choice | eq |
| `--pass` | Filter by render pass name. | text |  |
| `--json` | JSON output. | flag |  |

## `rdc assert-image`

Compare two images pixel-by-pixel.

**Arguments:**

| Name | Type | Required |
|------|------|----------|
| `expected` | file | yes |
| `actual` | file | yes |

**Options:**

| Flag | Help | Type | Default |
|------|------|------|---------|
| `--threshold` | Diff ratio threshold (%). | float | 0.0 |
| `--diff-output` | Write diff visualization PNG. | file |  |
| `--json` | JSON output. | flag |  |

## `rdc assert-pixel`

Assert pixel RGBA at (x, y) matches expected value within tolerance.

**Arguments:**

| Name | Type | Required |
|------|------|----------|
| `eid` | integer | yes |
| `x` | integer | yes |
| `y` | integer | yes |

**Options:**

| Flag | Help | Type | Default |
|------|------|------|---------|
| `--expect` | Expected RGBA as 4 space-separated floats. | text |  |
| `--tolerance` | Per-channel tolerance. | float | 0.01 |
| `--target` | Render target index. | integer | 0 |
| `--json` | JSON output. | flag |  |

## `rdc assert-state`

Assert pipeline state value at EID matches expected.

**Arguments:**

| Name | Type | Required |
|------|------|----------|
| `eid` | integer | yes |
| `key_path` | text | yes |

**Options:**

| Flag | Help | Type | Default |
|------|------|------|---------|
| `--expect` | Expected value. | text |  |
| `--json` | JSON output. | flag |  |

## `rdc bindings`

Show bound resources per shader stage.

**Arguments:**

| Name | Type | Required |
|------|------|----------|
| `eid` | integer | no |

**Options:**

| Flag | Help | Type | Default |
|------|------|------|---------|
| `--binding` | Filter by binding index. | integer |  |
| `--set` | Filter by descriptor set index. | integer |  |
| `--json` | Output JSON. | flag |  |
| `--no-header` | Omit TSV header | flag |  |
| `--jsonl` | JSONL output | flag |  |
| `-q, --quiet` | Print primary key column only | flag |  |

## `rdc buffer`

Export buffer raw data.

**Arguments:**

| Name | Type | Required |
|------|------|----------|
| `id` | integer | yes |

**Options:**

| Flag | Help | Type | Default |
|------|------|------|---------|
| `-o, --output` | Write to file | path |  |
| `--raw` | Force raw output even on TTY | flag |  |

## `rdc capture`

Execute application and capture a frame.

**Arguments:**

| Name | Type | Required |
|------|------|----------|
| `executable` | text | no |

**Options:**

| Flag | Help | Type | Default |
|------|------|------|---------|
| `-o, --output` | Output .rdc file path. | path |  |
| `--api` | Capture API name. | text |  |
| `--list-apis` | List capture APIs and exit. | flag |  |
| `--frame` | Queue capture at frame N. | integer |  |
| `--trigger` | Inject only; do not auto-capture. | flag |  |
| `--timeout` | Capture timeout in seconds. | float | 60.0 |
| `--wait-for-exit` | Wait for process to exit. | flag |  |
| `--keep-alive` | Keep target process running after capture. | flag |  |
| `--auto-open` | Open capture after success. | flag |  |
| `--api-validation` | Enable API validation. | flag |  |
| `--callstacks` | Capture callstacks. | flag |  |
| `--hook-children` | Hook child processes. | flag |  |
| `--ref-all-resources` | Reference all resources. | flag |  |
| `--soft-memory-limit` | Soft memory limit (MB). | integer |  |
| `--delay-for-debugger` | Debugger attach delay (s). | integer |  |
| `--json` | Output as JSON. | flag |  |

## `rdc cat`

Output VFS leaf node content.

**Arguments:**

| Name | Type | Required |
|------|------|----------|
| `path` | text | yes |

**Options:**

| Flag | Help | Type | Default |
|------|------|------|---------|
| `--json` | JSON output | flag |  |
| `--raw` | Force raw output even on TTY | flag |  |
| `-o, --output` | Write binary output to file | path |  |

## `rdc close`

Close daemon-backed session.

## `rdc completion`

Generate shell completion script.

**Arguments:**

| Name | Type | Required |
|------|------|----------|
| `shell` | choice | no |

## `rdc count`

Output a single integer count to stdout.

**Arguments:**

| Name | Type | Required |
|------|------|----------|
| `what` | choice | yes |

**Options:**

| Flag | Help | Type | Default |
|------|------|------|---------|
| `--pass` | Filter by render pass name. | text |  |

## `rdc counters`

Query GPU performance counters.

**Options:**

| Flag | Help | Type | Default |
|------|------|------|---------|
| `--list` | List available counters. | flag |  |
| `--eid` | Filter to specific event ID. | integer |  |
| `--name` | Filter counters by name substring. | text |  |
| `--json` | JSON output. | flag |  |
| `--no-header` | Omit TSV header | flag |  |
| `--jsonl` | JSONL output | flag |  |
| `-q, --quiet` | Print primary key column only | flag |  |

## `rdc debug pixel`

Debug pixel shader at (X, Y) for event EID.

**Arguments:**

| Name | Type | Required |
|------|------|----------|
| `eid` | integer | yes |
| `x` | integer | yes |
| `y` | integer | yes |

**Options:**

| Flag | Help | Type | Default |
|------|------|------|---------|
| `--trace` | Full execution trace (TSV) | flag |  |
| `--dump-at` | Var snapshot at LINE | integer |  |
| `--sample` | MSAA sample index | integer |  |
| `--primitive` | Primitive ID override | integer |  |
| `--json` | JSON output | flag |  |
| `--no-header` | Suppress TSV header row | flag |  |

## `rdc debug thread`

Debug compute shader thread at workgroup (GX,GY,GZ) thread (TX,TY,TZ).

**Arguments:**

| Name | Type | Required |
|------|------|----------|
| `eid` | integer | yes |
| `gx` | integer | yes |
| `gy` | integer | yes |
| `gz` | integer | yes |
| `tx` | integer | yes |
| `ty` | integer | yes |
| `tz` | integer | yes |

**Options:**

| Flag | Help | Type | Default |
|------|------|------|---------|
| `--trace` | Full execution trace (TSV) | flag |  |
| `--dump-at` | Var snapshot at LINE | integer |  |
| `--json` | JSON output | flag |  |
| `--no-header` | Suppress TSV header row | flag |  |

## `rdc debug vertex`

Debug vertex shader for vertex VTX_ID at event EID.

**Arguments:**

| Name | Type | Required |
|------|------|----------|
| `eid` | integer | yes |
| `vtx_id` | integer | yes |

**Options:**

| Flag | Help | Type | Default |
|------|------|------|---------|
| `--trace` | Full execution trace (TSV) | flag |  |
| `--dump-at` | Var snapshot at LINE | integer |  |
| `--instance` | Instance index (default 0) | integer | 0 |
| `--json` | JSON output | flag |  |
| `--no-header` | Suppress TSV header row | flag |  |

## `rdc diff`

Compare two RenderDoc captures side-by-side.

**Arguments:**

| Name | Type | Required |
|------|------|----------|
| `capture_a` | file | yes |
| `capture_b` | file | yes |

**Options:**

| Flag | Help | Type | Default |
|------|------|------|---------|
| `--draws` |  | flag |  |
| `--resources` |  | flag |  |
| `--passes` |  | flag |  |
| `--stats` |  | flag |  |
| `--framebuffer` |  | flag |  |
| `--pipeline` |  | text |  |
| `--json` |  | flag |  |
| `--format` |  | choice | tsv |
| `--shortstat` |  | flag |  |
| `--no-header` |  | flag |  |
| `--verbose` |  | flag |  |
| `--timeout` |  | float | 60.0 |
| `--target` | Color target index (default 0) | integer | 0 |
| `--threshold` | Max diff ratio %% to count as identical | float | 0.0 |
| `--eid` | Compare at specific EID (default: last draw) | integer |  |
| `--diff-output` | Write diff PNG here | path |  |

## `rdc doctor`

Run environment checks for rdc-cli.

## `rdc draw`

Show draw call detail.

**Arguments:**

| Name | Type | Required |
|------|------|----------|
| `eid` | integer | no |

**Options:**

| Flag | Help | Type | Default |
|------|------|------|---------|
| `--json` | JSON output | flag |  |

## `rdc draws`

List draw calls.

**Options:**

| Flag | Help | Type | Default |
|------|------|------|---------|
| `--pass` | Filter by pass name | text |  |
| `--sort` | Sort field | text |  |
| `--limit` | Max rows | integer |  |
| `--no-header` | Omit TSV header | flag |  |
| `--json` | JSON output | flag |  |
| `--jsonl` | JSONL output | flag |  |
| `-q, --quiet` | Only EID column | flag |  |

## `rdc event`

Show single API call detail.

**Arguments:**

| Name | Type | Required |
|------|------|----------|
| `eid` | integer | yes |

**Options:**

| Flag | Help | Type | Default |
|------|------|------|---------|
| `--json` | JSON output | flag |  |

## `rdc events`

List all events.

**Options:**

| Flag | Help | Type | Default |
|------|------|------|---------|
| `--type` | Filter by type | text |  |
| `--filter` | Filter by name glob | text |  |
| `--limit` | Max rows | integer |  |
| `--range` | EID range N:M | text |  |
| `--no-header` | Omit TSV header | flag |  |
| `--json` | JSON output | flag |  |
| `--jsonl` | JSONL output | flag |  |
| `-q, --quiet` | Only EID column | flag |  |

## `rdc goto`

Update current event id via daemon.

**Arguments:**

| Name | Type | Required |
|------|------|----------|
| `eid` | integer | yes |

## `rdc gpus`

List GPUs available at capture time.

**Options:**

| Flag | Help | Type | Default |
|------|------|------|---------|
| `--json` | Output as JSON. | flag |  |

## `rdc info`

Show capture metadata.

**Options:**

| Flag | Help | Type | Default |
|------|------|------|---------|
| `--json` | JSON output | flag |  |

## `rdc install-skill`

Install rdc-cli skill files to ~/.claude/skills/rdc-cli/.

**Options:**

| Flag | Help | Type | Default |
|------|------|------|---------|
| `--check` | Verify installed files are current. | flag |  |
| `--remove` | Remove installed skill files. | flag |  |

## `rdc log`

Show debug/validation messages from the capture.

**Options:**

| Flag | Help | Type | Default |
|------|------|------|---------|
| `--level` | Filter by severity. | choice |  |
| `--eid` | Filter by event ID. | integer |  |
| `--json` | JSON output | flag |  |
| `--no-header` | Omit TSV header | flag |  |
| `--jsonl` | JSONL output | flag |  |
| `-q, --quiet` | Print primary key column only | flag |  |

## `rdc ls`

List VFS directory contents.

**Arguments:**

| Name | Type | Required |
|------|------|----------|
| `path` | text | no |

**Options:**

| Flag | Help | Type | Default |
|------|------|------|---------|
| `-F, --classify` | Append type indicator (/ * @) | flag |  |
| `-l, --long` | Long format (TSV with metadata) | flag |  |
| `--json` | JSON output | flag |  |
| `--no-header` | Omit TSV header (with -l) | flag |  |
| `--jsonl` | JSONL output (with -l) | flag |  |
| `-q, --quiet` | Print name only (with -l) | flag |  |

## `rdc mesh`

Export post-transform mesh as OBJ.

**Arguments:**

| Name | Type | Required |
|------|------|----------|
| `eid` | integer | no |

**Options:**

| Flag | Help | Type | Default |
|------|------|------|---------|
| `--stage` | Mesh data stage (default: vs-out) | choice | vs-out |
| `-o, --output` | Write to file | path |  |
| `--json` | JSON output | flag |  |
| `--no-header` | Suppress OBJ header comment | flag |  |

## `rdc open`

Create local default session and start daemon skeleton.

**Arguments:**

| Name | Type | Required |
|------|------|----------|
| `capture` | path | yes |

**Options:**

| Flag | Help | Type | Default |
|------|------|------|---------|
| `--preload` | Preload shader cache after open. | flag |  |

## `rdc pass`

Show detail for a single render pass by index or name.

**Arguments:**

| Name | Type | Required |
|------|------|----------|
| `identifier` | text | yes |

**Options:**

| Flag | Help | Type | Default |
|------|------|------|---------|
| `--json` | Output JSON. | flag |  |

## `rdc passes`

List render passes.

**Options:**

| Flag | Help | Type | Default |
|------|------|------|---------|
| `--json` | Output JSON. | flag |  |
| `--no-header` | Omit TSV header | flag |  |
| `--jsonl` | JSONL output | flag |  |
| `-q, --quiet` | Print primary key column only | flag |  |

## `rdc pick-pixel`

Read pixel color at (X, Y) from the current render target.

**Arguments:**

| Name | Type | Required |
|------|------|----------|
| `x` | integer | yes |
| `y` | integer | yes |
| `eid` | integer | no |

**Options:**

| Flag | Help | Type | Default |
|------|------|------|---------|
| `--target` | Color target index (default 0) | integer | 0 |
| `--json` | JSON output | flag |  |

## `rdc pipeline`

Show pipeline summary for current or specified EID.

**Arguments:**

| Name | Type | Required |
|------|------|----------|
| `eid` | integer | no |
| `section` | text | no |

**Options:**

| Flag | Help | Type | Default |
|------|------|------|---------|
| `--json` | Output JSON. | flag |  |

## `rdc pixel`

Query pixel history at (X, Y) for the current or specified event.

**Arguments:**

| Name | Type | Required |
|------|------|----------|
| `x` | integer | yes |
| `y` | integer | yes |
| `eid` | integer | no |

**Options:**

| Flag | Help | Type | Default |
|------|------|------|---------|
| `--target` | Color target index (default 0) | integer | 0 |
| `--sample` | MSAA sample index (default 0) | integer | 0 |
| `--json` | JSON output | flag |  |
| `--no-header` | Omit TSV header | flag |  |
| `--jsonl` | JSONL output | flag |  |
| `-q, --quiet` | Print primary key column only | flag |  |

## `rdc resource`

Show details of a specific resource.

**Arguments:**

| Name | Type | Required |
|------|------|----------|
| `resid` | integer | yes |

**Options:**

| Flag | Help | Type | Default |
|------|------|------|---------|
| `--json` | Output JSON. | flag |  |

## `rdc resources`

List all resources.

**Options:**

| Flag | Help | Type | Default |
|------|------|------|---------|
| `--json` | Output JSON. | flag |  |
| `--type` | Filter by resource type (exact, case-insensitive). | text |  |
| `--name` | Filter by name substring (case-insensitive). | text |  |
| `--sort` | Sort order. | choice | id |
| `--no-header` | Omit TSV header | flag |  |
| `--jsonl` | JSONL output | flag |  |
| `-q, --quiet` | Print primary key column only | flag |  |

## `rdc rt`

Export render target as PNG.

**Arguments:**

| Name | Type | Required |
|------|------|----------|
| `eid` | integer | no |

**Options:**

| Flag | Help | Type | Default |
|------|------|------|---------|
| `-o, --output` | Write to file | path |  |
| `--target` | Color target index (default 0) | integer | 0 |
| `--raw` | Force raw output even on TTY | flag |  |
| `--overlay` | Render with debug overlay | choice |  |
| `--width` | Overlay render width | integer | 256 |
| `--height` | Overlay render height | integer | 256 |

## `rdc script`

Execute a Python script inside the daemon process.

**Arguments:**

| Name | Type | Required |
|------|------|----------|
| `script_file` | file | yes |

**Options:**

| Flag | Help | Type | Default |
|------|------|------|---------|
| `--arg` | Script argument. | text |  |
| `--json` | Raw JSON output. | flag |  |

## `rdc search`

Search shader disassembly text for PATTERN (regex).

**Arguments:**

| Name | Type | Required |
|------|------|----------|
| `pattern` | text | yes |

**Options:**

| Flag | Help | Type | Default |
|------|------|------|---------|
| `--stage` | Filter by stage (vs/ps/cs/...). | text |  |
| `--limit` | Max results. | integer | 200 |
| `-C, --context` | Context lines. | integer | 0 |
| `-i, --case-sensitive` | Case-sensitive search. | flag |  |
| `--json` | JSON output. | flag |  |

## `rdc section`

Extract named section contents.

**Arguments:**

| Name | Type | Required |
|------|------|----------|
| `name` | text | yes |

**Options:**

| Flag | Help | Type | Default |
|------|------|------|---------|
| `--json` | Output as JSON. | flag |  |

## `rdc sections`

List all embedded sections.

**Options:**

| Flag | Help | Type | Default |
|------|------|------|---------|
| `--json` | Output as JSON. | flag |  |

## `rdc shader`

Show shader metadata for a stage at EID.

**Arguments:**

| Name | Type | Required |
|------|------|----------|
| `eid` | integer | no |
| `stage` | choice | no |

**Options:**

| Flag | Help | Type | Default |
|------|------|------|---------|
| `--reflect` | Include reflection data (inputs/outputs/cbuffers). | flag |  |
| `--constants` | Include constant buffer values. | flag |  |
| `--source` | Include debug source code. | flag |  |
| `--target` | Disassembly target format (e.g., 'dxil', 'spirv', 'glsl'). | text |  |
| `--targets` | List available disassembly targets. | flag |  |
| `-o, --output` | Output file path. | path |  |
| `--all` | Get all shader data for all stages. | flag |  |
| `--json` | Output JSON. | flag |  |

## `rdc shader-build`

Build a shader from source file.

**Arguments:**

| Name | Type | Required |
|------|------|----------|
| `source_file` | file | yes |

**Options:**

| Flag | Help | Type | Default |
|------|------|------|---------|
| `--stage` | Shader stage | choice |  |
| `--entry` | Entry point name | text | main |
| `--encoding` | Encoding name (default: GLSL) | text | GLSL |
| `--json` | JSON output | flag |  |
| `-q, --quiet` | Print only shader_id | flag |  |

## `rdc shader-encodings`

List available shader encodings for this capture.

**Options:**

| Flag | Help | Type | Default |
|------|------|------|---------|
| `--json` | JSON output | flag |  |

## `rdc shader-map`

Output EID-to-shader mapping as TSV.

**Options:**

| Flag | Help | Type | Default |
|------|------|------|---------|
| `--no-header` | Omit TSV header row. | flag |  |
| `--json` | JSON output. | flag |  |
| `--jsonl` | JSONL output. | flag |  |
| `-q, --quiet` | Print EID column only. | flag |  |

## `rdc shader-replace`

Replace shader at EID/STAGE with a built shader.

**Arguments:**

| Name | Type | Required |
|------|------|----------|
| `eid` | integer | yes |
| `stage` | choice | yes |

**Options:**

| Flag | Help | Type | Default |
|------|------|------|---------|
| `--with` | Built shader ID from shader-build | integer |  |
| `--json` | JSON output | flag |  |

## `rdc shader-restore`

Restore original shader at EID/STAGE.

**Arguments:**

| Name | Type | Required |
|------|------|----------|
| `eid` | integer | yes |
| `stage` | choice | yes |

**Options:**

| Flag | Help | Type | Default |
|------|------|------|---------|
| `--json` | JSON output | flag |  |

## `rdc shader-restore-all`

Restore all replaced shaders and free built resources.

**Options:**

| Flag | Help | Type | Default |
|------|------|------|---------|
| `--json` | JSON output | flag |  |

## `rdc shaders`

List unique shaders in capture.

**Options:**

| Flag | Help | Type | Default |
|------|------|------|---------|
| `--stage` | Filter by shader stage. | choice |  |
| `--sort` | Sort order. | choice | name |
| `--json` | Output JSON. | flag |  |
| `--no-header` | Omit TSV header | flag |  |
| `--jsonl` | JSONL output | flag |  |
| `-q, --quiet` | Print primary key column only | flag |  |

## `rdc snapshot`

Export a complete rendering state snapshot for a draw event.

**Arguments:**

| Name | Type | Required |
|------|------|----------|
| `eid` | integer | yes |

**Options:**

| Flag | Help | Type | Default |
|------|------|------|---------|
| `-o, --output` | Output directory | path |  |
| `--json` | JSON output | flag |  |

## `rdc stats`

Show per-pass breakdown, top draws, largest resources.

**Options:**

| Flag | Help | Type | Default |
|------|------|------|---------|
| `--json` | JSON output | flag |  |
| `--no-header` | Omit TSV header | flag |  |
| `--jsonl` | JSONL output | flag |  |
| `-q, --quiet` | Print primary key column only | flag |  |

## `rdc status`

Show current daemon-backed session status.

## `rdc tex-stats`

Show texture min/max statistics and optional histogram.

**Arguments:**

| Name | Type | Required |
|------|------|----------|
| `resource_id` | integer | yes |
| `eid` | integer | no |

**Options:**

| Flag | Help | Type | Default |
|------|------|------|---------|
| `--mip` | Mip level (default 0) | integer | 0 |
| `--slice` | Array slice (default 0) | integer | 0 |
| `--histogram` | Show 256-bucket histogram | flag |  |
| `--json` | JSON output | flag |  |

## `rdc texture`

Export texture as PNG.

**Arguments:**

| Name | Type | Required |
|------|------|----------|
| `id` | integer | yes |

**Options:**

| Flag | Help | Type | Default |
|------|------|------|---------|
| `-o, --output` | Write to file | path |  |
| `--mip` | Mip level (default 0) | integer | 0 |
| `--raw` | Force raw output even on TTY | flag |  |

## `rdc thumbnail`

Export capture thumbnail.

**Options:**

| Flag | Help | Type | Default |
|------|------|------|---------|
| `--maxsize` | Max thumbnail dimension. | integer | 0 |
| `--json` | Output as JSON. | flag |  |

## `rdc tree`

Display VFS subtree structure.

**Arguments:**

| Name | Type | Required |
|------|------|----------|
| `path` | text | no |

**Options:**

| Flag | Help | Type | Default |
|------|------|------|---------|
| `--depth` |  | integer range | 2 |
| `--json` | JSON output | flag |  |

## `rdc usage`

Show resource usage (which events read/write a resource).

**Arguments:**

| Name | Type | Required |
|------|------|----------|
| `resource_id` | integer | no |

**Options:**

| Flag | Help | Type | Default |
|------|------|------|---------|
| `--all` | Show all resources usage matrix. | flag |  |
| `--type` | Filter by resource type. | text |  |
| `--usage` | Filter by usage type. | text |  |
| `--json` | JSON output. | flag |  |
| `--no-header` | Omit TSV header | flag |  |
| `--jsonl` | JSONL output | flag |  |
| `-q, --quiet` | Print primary key column only | flag |  |
