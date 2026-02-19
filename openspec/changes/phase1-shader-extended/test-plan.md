# Test Plan: phase1-shader-extended

## Goals
Validate extended shader, pipeline, and bindings inspection features across service, daemon, and CLI layers.

## Test Layers
- Unit:
  - query_service reflection extraction helpers
  - query_service constant buffer value extraction
  - query_service pipeline state extraction
  - query_service bindings extraction
  - formatter output normalization
- Mock daemon:
  - JSON-RPC methods for new shader/pipeline/bindings queries
- CLI:
  - command options parsing
  - no-session and invalid-eid handling
  - file export behavior

## Happy Path Cases
1. `rdc shader --targets` returns available disassembly formats
2. `rdc shader --reflect` returns input/output signatures and constant blocks
3. `rdc shader --constants` returns actual buffer values
4. `rdc shader --source` returns source code (or fallback to disasm)
5. `rdc shader --target <fmt>` uses specified format
6. `rdc shader -o <file>` writes to file
7. `rdc shader --all` outputs all stages
8. `rdc shaders` returns all unique shaders in frame
9. `rdc pipeline` returns full pipeline state
10. `rdc pipeline <eid> vs` returns VS stage only
11. `rdc bindings` returns all descriptor sets
12. `rdc bindings --set 0` returns set 0 only

## Failure Cases
1. No active session -> error + nonzero exit
2. Invalid eid -> not found response
3. No shader bound at stage -> clear empty response
4. No debug info for --source -> fallback to disasm
5. Invalid --target format -> error with available formats
6. Invalid pipeline section -> error with available sections
7. Invalid --set value -> error

## Assertions
- Output format matches design doc examples
- Exit code conventions unchanged (0 success, 1 error)
- File export handles large shaders correctly
- TSV output pipe-safe (tab-separated, no embedded newlines in data)
