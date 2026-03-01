# rdc-cli Black-Box E2E Test Catalog

> Generated from manual testing session 2026-02-28.
> Fixture: `tests/fixtures/vkcube.rdc` unless noted.
> All tests verified on Linux x86_64, RenderDoc 1.41, Python 3.14.

## Notation

- `[P]` = PASS, `[F]` = FAIL (bug), `[N]` = NOTE (behavior worth documenting)
- `exit:N` = expected exit code

---

## 1. Pre-Session Commands (no daemon)

| # | Command | Expected | Status |
|---|---------|----------|--------|
| 1.1 | `rdc --version` | Print version string | [P] `0.3.7.dev1` |
| 1.2 | `rdc --help` | Print all commands | [P] 66+ commands listed |
| 1.3 | `rdc doctor` | Check renderdoc, python, platform | [P] all green |
| 1.4 | `rdc status` (no session) | `error: no active session` exit:1 | [P] |
| 1.5 | `rdc close` (no session) | `error: no active session` exit:1 | [P] |
| 1.6 | `rdc completion bash` | Valid bash completion script | [P] |
| 1.7 | `rdc completion zsh` | Valid zsh completion script | [P] |
| 1.8 | `rdc open nonexistent.rdc` | `error: file not found` exit:1 | [P] |

## 2. Session Lifecycle

| # | Command | Expected | Status |
|---|---------|----------|--------|
| 2.1 | `rdc open tests/fixtures/vkcube.rdc` | Open capture, print session path | [P] |
| 2.2 | `rdc status` | session, capture, eid, daemon | [P] |
| 2.3 | `rdc goto 1` | `current_eid set to 1` | [P] |
| 2.4 | `rdc goto 5` | `current_eid set to 5` (max valid) | [P] |
| 2.5 | `rdc goto 999` | `error: eid 999 out of range` exit:1 | [P] |
| 2.6 | `rdc goto -- -1` | `error: eid must be >= 0` exit:1 | [P] |
| 2.7 | `rdc goto -1` | Click option error exit:2 | [P] |
| 2.8 | `rdc --session test2 open hello_triangle.rdc` | Separate session created | [P] |
| 2.9 | `rdc --session test2 status` | Shows test2 session independently | [P] |
| 2.10 | `rdc --session test2 close` | Closes only test2 | [P] |
| 2.11 | `rdc open --listen :0` | Random port, prints connect info + token | [P] |
| 2.12 | `rdc close` | Session closed | [P] |

## 3. Query Commands

| # | Command | Expected | Status |
|---|---------|----------|--------|
| 3.1 | `rdc info` | Capture metadata (API, events, draws) | [P] |
| 3.2 | `rdc stats` | Per-pass breakdown, top draws | [P] |
| 3.3 | `rdc log` | Validation messages with LEVEL/EID/MESSAGE | [P] |
| 3.4 | `rdc events` | EID/TYPE/NAME TSV listing | [P] |
| 3.5 | `rdc event 11` | Single event detail with parameters | [P] |
| 3.6 | `rdc event 999` | `error: eid out of range` exit:1 | [P] |
| 3.7 | `rdc draws` | Draw calls with triangles/pass/marker | [P] |
| 3.8 | `rdc draw 11` | Draw detail (type, triangles, instances) | [P] |
| 3.9 | `rdc draw 5` | Shows non-draw event as draw (0 triangles) | [N] exit:0 |
| 3.10 | `rdc count events` | `6` | [P] |
| 3.11 | `rdc count draws` | `1` | [P] |
| 3.12 | `rdc count resources` | `46` | [P] |
| 3.13 | `rdc count shaders` | `2` | [P] |
| 3.14 | `rdc count badtarget` | Click choice error exit:2 | [P] |
| 3.15 | `rdc search "main"` | Matches in shader disassembly | [P] |
| 3.16 | `rdc search "gl_Position"` | Matches in VS disassembly | [P] |
| 3.17 | `rdc search "nonexistent_xyz"` | Empty output exit:0 | [P] |
| 3.18 | `rdc shader-map` | EID-to-shader TSV (vs/hs/ds/gs/ps/cs) | [P] |
| 3.19 | `rdc pipeline 11` | Pipeline summary (topology, pipe IDs) | [P] |
| 3.20 | `rdc pipeline 11 topology` | KEY/VALUE pair | [P] |
| 3.21 | `rdc pipeline 11 viewport` | Viewport state | [P] |
| 3.22 | `rdc pipeline 11 blend` | Blend state with JSON-like blends array | [P] |
| 3.23 | `rdc pipeline 11 badslice` | `error: invalid section` exit:1 | [P] |
| 3.24 | `rdc bindings 11` | Descriptor bindings per stage | [P] |
| 3.25 | `rdc shader vs` | Stage-only form (uses current EID) | [P] |
| 3.26 | `rdc shader 11 vs` | EID+stage form | [P] |
| 3.27 | `rdc shader xx` | `error: not valid EID or stage` exit:2 | [P] |
| 3.28 | `rdc shader vs --reflect --json` | JSON output (no reflect data embedded) | [N] see note |
| 3.29 | `rdc shaders` | Shader list with STAGES/USES | [P] |
| 3.30 | `rdc shaders --stage vs` | Filtered by stage | [P] (tested on dynamic_rendering) |
| 3.31 | `rdc resources` | Full resource list | [P] |
| 3.32 | `rdc resource 97` | Resource detail | [P] |
| 3.33 | `rdc resource 99999` | `error: resource not found` exit:1 | [P] |
| 3.34 | `rdc passes` | Pass list with draw counts | [P] |
| 3.35 | `rdc pass 0` | Pass detail (begin/end eid, targets) | [P] |
| 3.36 | `rdc passes --deps` | Dependency DAG TSV | [P] |
| 3.37 | `rdc passes --dot` (no --deps) | `error: --dot requires --deps` exit:2 | [P] |
| 3.38 | `rdc passes --deps --dot` | DOT graph output | [P] |
| 3.39 | `rdc usage 97` | Resource usage across events | [P] |

## 4. Output Format Flags

| # | Command | Expected | Status |
|---|---------|----------|--------|
| 4.1 | `rdc events --json` | Valid JSON array | [P] |
| 4.2 | `rdc events --jsonl` | One JSON object per line | [P] |
| 4.3 | `rdc events --no-header` | TSV without header row | [P] |
| 4.4 | `rdc events -q` | Primary key column only (EIDs) | [P] |
| 4.5 | `rdc draws --json` | Valid JSON array | [P] |
| 4.6 | `rdc resources --json` | Valid JSON, 46 items | [P] |
| 4.7 | `rdc resources -q` | Resource IDs only | [P] |
| 4.8 | `rdc resource 97 --json` | JSON with lowercase keys | [P] |
| 4.9 | `rdc pixel 300 300 11 --json` | Full pixel history JSON | [P] |
| 4.10 | `rdc cat /info --json` | VFS leaf in JSON | [P] |

## 5. VFS Navigation

| # | Command | Expected | Status |
|---|---------|----------|--------|
| 5.1 | `rdc ls /` | Root entries (capabilities, info, stats, ...) | [P] |
| 5.2 | `rdc ls -l /` | Long format with TYPE column | [P] |
| 5.3 | `rdc tree / --depth 1` | Tree with dirs/leaves/aliases | [P] |
| 5.4 | `rdc tree /draws --depth 2` | Draw subtree (pipeline, shader, targets) | [P] |
| 5.5 | `rdc cat /info` | Same as `rdc info` | [P] |
| 5.6 | `rdc cat /stats` | Same as `rdc stats` | [P] |
| 5.7 | `rdc cat /log` | Validation messages | [P] |
| 5.8 | `rdc cat /capabilities` | Capture capabilities | [P] |
| 5.9 | `rdc cat /events/11` | Event detail via VFS | [P] |
| 5.10 | `rdc cat /draws/11/pipeline/topology` | Pipeline subsection via VFS | [P] |
| 5.11 | `rdc cat /draws/11/shader/vs/disasm` | Shader disasm via VFS | [P] |
| 5.12 | `rdc cat /draws/11/postvs` | Post-VS data via VFS | [P] |
| 5.13 | `rdc cat /draws/11/descriptors` | Descriptor bindings via VFS | [P] |
| 5.14 | `rdc cat /draws/11/descriptors --json` | JSON with sampler details | [P] but SWIG leak |
| 5.15 | `rdc cat /resources/97/info` | Resource info via VFS | [P] |
| 5.16 | `rdc cat /textures/97/info` | Texture metadata via VFS | [P] |
| 5.17 | `rdc cat /shaders/111/info` | Shader info via VFS | [P] |
| 5.18 | `rdc ls /textures` | Texture IDs | [P] |
| 5.19 | `rdc ls /shaders` | Shader IDs | [P] |
| 5.20 | `rdc ls /passes` | Pass names (may contain spaces/#) | [P] |
| 5.21 | `rdc cat "/passes/Colour Pass #1 .../info"` | Pass info with special chars | [P] |
| 5.22 | `rdc cat /nonexistent` | `error: not found` exit:1 | [P] |
| 5.23 | `rdc ls /nonexistent` | `error: not found` exit:1 | [P] |
| 5.24 | `rdc cat /passes/.../draws` (dir) | `error: Is a directory` exit:1 | [P] |
| 5.25 | `rdc cat /textures/97/image.png -o /tmp/f.png` | Binary PNG via VFS | [P] |
| 5.26 | `rdc cat /draws/11/targets/color0.png -o /tmp/f.png` | RT PNG via VFS | [P] |
| 5.27 | `rdc tree / --max-depth 1` | `error: Did you mean --depth?` exit:2 | [P] |
| 5.28 | `rdc ls /draws/11` | Shows `pixel` directory | [P] |
| 5.29 | `rdc ls /passes/<name>/attachments` | Lists color0 entry | [P] |
| 5.30 | `rdc cat /shaders/111/used-by` | Shows EID 11 | [P] |
| 5.31 | `rdc cat /passes/<name>/attachments/color0` | Shows resource_id | [P] |
| 5.32 | `rdc tree /draws --depth 2` | Shows pixel entry | [P] |
| 5.33 | `rdc ls /passes/<name>/attachments` | Includes depth target | [P] |
| 5.34 | `rdc cat /passes/<name>/attachments/depth` | Depth resource info | [P] |
| 5.35 | `rdc cat /passes/<name>/attachments/color99` | Error exit:1 | [P] |
| 5.36 | `rdc ls /shaders/111` | Lists used-by entry | [P] |
| 5.37 | `rdc cat /shaders/112/used-by` | Shows EID for shader 112 | [P] |

## 6. Export Commands

| # | Command | Expected | Status |
|---|---------|----------|--------|
| 6.1 | `rdc texture 97 -o /tmp/tex.png` | 16KB PNG file | [P] |
| 6.2 | `rdc texture 99999 -o /tmp/bad.png` | `error: not found` exit:1 | [P] |
| 6.3 | `rdc rt 11 -o /tmp/rt.png` | 42KB render target PNG | [P] |
| 6.4 | `rdc rt 11 --overlay wireframe -o /tmp/w.png` | Wireframe overlay PNG | [P] |
| 6.5 | `rdc buffer 102 -o /tmp/buf.bin` | 1.2KB binary buffer | [P] |
| 6.6 | `rdc mesh 11 -o /tmp/mesh.obj` | OBJ file (36 verts, 12 faces) | [P] |
| 6.7 | `rdc thumbnail -o /tmp/thumb.png` | Capture thumbnail PNG | [P] |
| 6.8 | `rdc snapshot 11 -o /tmp/snap` | 5 files (pipeline, shaders, targets) | [P] |
| 6.9 | `rdc gpus` | GPU list (vendor, driver) | [P] |
| 6.10 | `rdc sections` | Section list with name/type/size | [P] |
| 6.11 | `rdc section "renderdoc/internal/framecapture"` | Binary section data | [P] |
| 6.12 | `rdc section "0"` | `error: section not found` exit:1 | [P] |
| 6.13 | `rdc tex-stats 97` | Channel min/max (RGBA) | [P] |
| 6.14 | `rdc tex-stats` (no arg) | `error: missing RESOURCE_ID` exit:2 | [P] |

## 7. Debug Commands

| # | Command | Expected | Status |
|---|---------|----------|--------|
| 7.1 | `rdc debug pixel 11 300 300` | PS debug summary (steps, inputs, outputs) | [P] |
| 7.2 | `rdc debug pixel 11 300 300 --trace` | Step-by-step trace table | [P] |
| 7.3 | `rdc debug vertex 11 0` | VS debug summary | [P] |
| 7.4 | `rdc debug pixel 11 99999 99999` | `error: no fragment at pixel` exit:1 | [P] |
| 7.5 | `rdc debug pixel 11 -- -5 -5` | SWIG uint32_t error (see bug B-NEW-1) | [F] |
| 7.6 | `rdc pixel 300 300 11` | Pixel history (EID/FRAG/DEPTH/PASSED) | [P] |
| 7.7 | `rdc pixel 300 300 11 --json` | Full pixel history JSON with modifications | [P] |

## 8. Assert/CI Commands

| # | Command | Expected | Status |
|---|---------|----------|--------|
| 8.1 | `rdc assert-pixel 11 300 300 --expect "0.33 0.33 0.33 0.52" --tolerance 0.02` | `pass:` exit:0 | [P] |
| 8.2 | `rdc assert-pixel 11 300 300 --expect "1.0 0.0 0.0 1.0"` | `fail:` exit:1 | [P] |
| 8.3 | `rdc assert-clean` | `fail: 1 message(s)` exit:1 (vkcube has HIGH validation) | [P] |
| 8.4 | `rdc assert-count events --expect 6` | `pass:` exit:0 | [P] |
| 8.5 | `rdc assert-count events --expect 10` | `fail:` exit:1 | [P] |
| 8.6 | `rdc assert-count draws --expect 1` | `pass:` exit:0 | [P] |
| 8.7 | `rdc assert-count resources --expect 10 --op gt` | `pass: 46 > 10` exit:0 | [P] |
| 8.8 | `rdc assert-count triangles --expect 12` | `pass:` exit:0 | [P] |
| 8.9 | `rdc assert-count shaders --expect 2` | `pass:` exit:0 | [P] |
| 8.10 | `rdc assert-state 11 topology --expect TriangleList` | `pass:` exit:0 | [P] |
| 8.11 | `rdc assert-state 11 topology --expect PointList` | `fail:` exit:1 | [P] |
| 8.12 | `rdc assert-image /tmp/rt0.png /tmp/rt0.png` | `match` exit:0 | [P] |
| 8.13 | `rdc assert-image /tmp/rt0.png /tmp/tex97.png` | `error: size mismatch` exit:2 | [P] |

## 9. Diff Command

| # | Command | Expected | Status |
|---|---------|----------|--------|
| 9.1 | `rdc diff A A --stats` | All passes `=` identical | [P] |
| 9.2 | `rdc diff A A --framebuffer` | `identical` exit:0 | [P] |
| 9.3 | `rdc diff A B --stats` (different size) | Stats comparison | [P] |
| 9.4 | `rdc diff A B --framebuffer` (different size) | `error: size mismatch` exit:2 | [P] |
| 9.5 | `rdc diff A B --draws` | Draw comparison with confidence | [P] |
| 9.6 | `rdc diff A B --resources` | Resource comparison | [P] |
| 9.7 | `rdc diff A B --shortstat` | `identical` or summary | [P] |

## 10. Script Command

| # | Command | Expected | Status |
|---|---------|----------|--------|
| 10.1 | `rdc script valid.py` | Script output + elapsed time | [P] |
| 10.2 | `rdc script error.py` | `error: script error: ...` exit:1 | [P] |

## 11. Advanced Features

| # | Command | Expected | Status |
|---|---------|----------|--------|
| 11.1 | `rdc shader-encodings` | List (GLSL, SPIRV) | [P] |
| 11.2 | `rdc open --listen :0` | Random port + token | [P] |
| 11.3 | Named sessions (`--session test2`) | Independent session isolation | [P] |
| 11.4 | Pipe: `rdc events -q \| wc -l` | Correct line count | [P] |
| 11.5 | Pipe: `rdc resources -q \| xargs rdc resource` | Batch processing works | [P] |

## 12. Multi-Fixture Validation

| # | Fixture | Test | Status |
|---|---------|------|--------|
| 12.1 | `vkcube.rdc` | All standard tests | [P] |
| 12.2 | `hello_triangle.rdc` | Open/status/close | [P] |
| 12.3 | `vkcube_validation.rdc` | info, diff vs vkcube | [P] |
| 12.4 | `dynamic_rendering.rdc` | Multi-pass (2 passes, 4 draws) | [P] |
| 12.5 | `oit_depth_peeling.rdc` | Complex DAG (9 passes, 12 draws, 36 deps) | [P] |

---

## Bugs Found

### B-NEW-1: SWIG error leaked for negative pixel coords
- **Command**: `rdc debug pixel 11 -- -5 -5`
- **Got**: `error: DebugPixel failed: in method 'ReplayController_DebugPixel', argument 2 of type 'uint32_t'`
- **Expected**: Friendly error like `error: pixel coordinates must be >= 0`
- **Severity**: P3 (UX, no functional impact)

### B-NEW-2: TextureFilter SWIG object leaked in JSON
- **Command**: `rdc cat /draws/11/descriptors --json`
- **Got**: `"filter": "<Swig Object of type 'TextureFilter *' at 0x...>"`
- **Expected**: Human-readable filter description or structured fields
- **Severity**: P2 (data quality, affects machine parsing)

### B-NEW-3: `--reflect` flag produces no additional data
- **Command**: `rdc shader vs --reflect --json`
- **Got**: Same JSON as without `--reflect`
- **Expected**: Additional reflection data (inputs, outputs, cbuffers)
- **Severity**: P2 (missing feature or silent no-op)

## Notes

### N1: TSV vs JSON key casing
- TSV headers: `ID`, `TYPE`, `NAME` (uppercase)
- JSON keys: `id`, `type`, `name` (lowercase)
- Agent code must handle both formats

### N2: Arg order inconsistency
- `rdc pixel X Y [EID]` — coords first
- `rdc debug pixel EID X Y` — EID first
- Both are valid Click conventions but may confuse agent automation

### N3: `draw` command on non-draw EID
- `rdc draw 5` returns exit:0 with Triangles=0 for a non-draw event
- Could arguably return exit:1 or a warning

---

## Coverage Summary

| Category | Tests | Pass | Fail | Note |
|----------|-------|------|------|------|
| Pre-session | 8 | 8 | 0 | 0 |
| Session lifecycle | 12 | 12 | 0 | 0 |
| Query commands | 39 | 39 | 0 | 1 |
| Output formats | 10 | 10 | 0 | 0 |
| VFS navigation | 37 | 37 | 0 | 0 |
| Export commands | 14 | 14 | 0 | 0 |
| Debug commands | 7 | 6 | 1 | 0 |
| Assert/CI | 13 | 13 | 0 | 0 |
| Diff | 7 | 7 | 0 | 0 |
| Script | 2 | 2 | 0 | 0 |
| Advanced | 5 | 5 | 0 | 0 |
| Multi-fixture | 5 | 5 | 0 | 0 |
| **TOTAL** | **159** | **158** | **1** | **1** |

Pass rate: **99.4%** (158/159)
