# Proposal: phase2-search

## Summary

Add `rdc search <pattern>` command for grep-style searching across all shader
disassembly in a capture. Also adds a daemon-side disassembly cache for
performance and the `/shaders/` VFS namespace population.

## Motivation

GPU debugging often requires finding which shader uses a specific instruction,
register, variable name, or pattern. Currently users must manually disassemble
each shader one at a time via `rdc shader <eid> <stage>`. With hundreds of
unique shaders in a production capture, this is impractical.

`rdc search` provides unix `grep`-like semantics: regex pattern → matching
lines with context (shader ID, stages, line number, first-use EID).

## Design

### Architecture

```
CLI: rdc search <pattern>
  → daemon JSON-RPC: "search" {pattern, stage?, target?}
    → build disassembly cache (lazy, first call only)
    → regex search across cached disassembly text
    → return [{shader, stages, first_eid, line, text}]
```

### Daemon handler: `search`

**Params:**
- `pattern` (string, required) — regex pattern (Python `re` syntax, max 500 chars)
- `stage` (string, optional) — filter by stage (vs/ps/cs/...)
- `target` (string, optional) — disassembly target (SPIR-V/GLSL/DXIL)
- `case_sensitive` (bool, default false) — case-sensitive matching
- `limit` (int, default 200) — max results to return
- `context` (int, default 0) — lines of context around each match

**Response:**
```json
{
  "matches": [
    {
      "shader": 42,
      "stages": ["ps"],
      "first_eid": 150,
      "line": 37,
      "text": "  %result = OpFMul %float %a %b",
      "context_before": [],
      "context_after": []
    }
  ],
  "truncated": false
}
```

### Disassembly cache

New fields on `DaemonState`:

```python
disasm_cache: dict[int, str]           # shader_id → disassembly text
shader_meta: dict[int, dict[str, Any]] # shader_id → {stages, uses, first_eid, entry}
_shader_cache_built: bool              # sentinel to avoid re-walk
```

Built lazily on first `search` call by iterating unique shaders:
1. Reuse `_collect_pipe_states` to find all unique shader IDs
2. For each unique shader: `SetFrameEvent` → `DisassembleShader`
3. Cache the result keyed by `int(shader_id)`
4. Subsequent searches reuse the cache (instant)

The disassembly target defaults to the first available target from
`GetDisassemblyTargets(True)`. If `target` param is specified, cache is
per-target (key becomes `(shader_id, target)`).

### VFS: `/shaders/` namespace

Currently `/shaders/` is a placeholder dir. This OpenSpec populates it:

```
/shaders/
  <shader_id>/         → dir, one per unique shader
    info               → leaf: stage, uses, entry point
    disasm             → leaf: full disassembly text
```

VFS population reuses the same disassembly cache. Tree cache gets a
`populate_shaders_subtree` helper called as a side effect of cache build.

### CLI: `rdc search`

```
rdc search <pattern> [--stage STAGE] [-i] [--limit N] [-C N] [--json]
```

Output format (grep-style, colon-delimited):
```
shader:42[ps]:37:  %result = OpFMul %float %a %b
shader:42[ps]:42:  %color = OpCompositeConstruct %v4float ...
shader:88[vs]:15:  %pos = OpAccessChain %_ptr_Input_v4float ...
```

With `-C 1`, context lines use `-` separator:
```
shader:42[ps]:37-  %a = OpLoad %float ...
shader:42[ps]:37:  %result = OpFMul %float %a %b
shader:42[ps]:37-  OpStore %out %result
```

### Error handling

- Invalid regex → `-32602` (invalid params)
- Pattern too long (>500 chars) → `-32602` (invalid params)
- No shaders found → empty matches list (not an error)
- Disassembly fails for a shader → skip, store empty string, continue

## Scope

**In scope:**
- `search` daemon handler with regex matching
- Disassembly cache in DaemonState
- `/shaders/<id>/info` and `/shaders/<id>/disasm` VFS leaves
- `rdc search` CLI command
- VFS routes for new shader paths

**Out of scope:**
- `rdc find` (VFS tree search — separate OpenSpec)
- Source-level search (requires debug info, rare)
- Streaming/incremental search (all shaders disassembled upfront)
- Cache invalidation (cache lives for session lifetime)
