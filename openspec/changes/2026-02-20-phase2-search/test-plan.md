# Test Plan: phase2-search

## Scope

### In scope
- `search` daemon handler: regex matching, stage filter, limit, context lines
- Disassembly cache: lazy build, reuse on second call
- `/shaders/<id>/info` and `/shaders/<id>/disasm` VFS routes
- `rdc search` CLI command (TSV output)
- VFS tree cache: `/shaders/` namespace population

### Out of scope
- `rdc find` (VFS tree search)
- GPU integration tests for disassembly (too slow, relies on real GPU)
- Cache eviction (no eviction — session lifetime cache)

## Test Matrix

| Layer | Scope | Runner |
|-------|-------|--------|
| Unit | daemon handler logic, cache build, regex matching | pytest |
| Unit | VFS route resolution for `/shaders/` paths | pytest |
| Unit | tree cache `/shaders/` population | pytest |
| Unit | CLI command output format | pytest + CliRunner |
| Mock | full search flow with mock disassembly data | pytest |

## Cases

### Happy path
1. **Basic search** — pattern matches lines in 2 different shaders, returns
   correct shader_id/stage/eid/line_no/text
2. **Case-insensitive** — default behavior, matches regardless of case
3. **Case-sensitive** — `case_sensitive=true`, only exact case matches
4. **Stage filter** — `stage="ps"` returns only pixel shader matches
5. **Limit** — `limit=1` returns only first match, `truncated=true`
6. **Context lines** — `context=1` includes 1 line before and after match
7. **Second search reuses cache** — cache built once, second call instant

### Error path
8. **Invalid regex** — `pattern="[unclosed"` → error -32602
9. **No adapter** — search without loaded capture → error -32002
10. **No matches** — valid pattern, no hits → empty matches, not error

### Edge cases
11. **Empty disassembly** — shader returns empty string → skip, don't crash
12. **Pattern matches every line** — limit caps output
13. **Multiple stages same shader** — shader used as both VS and PS

### VFS routes
14. **`/shaders/` list** — returns all unique shader IDs
15. **`/shaders/<id>/info`** — returns stage/uses/entry
16. **`/shaders/<id>/disasm`** — returns full disassembly text
17. **`/shaders/<id>` not found** — error -32001

### CLI
18. **`rdc search <pattern>`** — TSV output with header
19. **`rdc search` no matches** — prints "no matches" message

## Assertions

### Daemon handler
- `resp["result"]["matches"]` is a list of dicts with keys:
  `shader`, `stage`, `eid`, `line`, `text`
- `resp["result"]["total_shaders"]` equals count of unique shaders
- `resp["result"]["truncated"]` is bool, true when limit hit
- Error responses use correct JSON-RPC error codes

### VFS
- `/shaders/` node kind is `"dir"`, children are shader ID strings
- `/shaders/<id>/info` kind is `"leaf"`
- `/shaders/<id>/disasm` kind is `"leaf"`
- Route resolution returns correct handler for all `/shaders/` paths

### CLI
- Exit code 0 on success
- TSV output: tab-separated, header row, correct column order
- `--json` flag outputs JSON format

## Risks & Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Disassembly slow for many shaders | First search takes seconds | Cache is lazy + persistent for session |
| Regex DoS (catastrophic backtracking) | Daemon hangs | Set `re.compile` timeout or limit pattern complexity |
| Mock doesn't cover DisassembleShader API | Tests pass but real API fails | Mock returns realistic SPIR-V-like disassembly text |
| Large disassembly text for shader | Memory pressure | Reasonable — typical shader < 10KB disasm |
