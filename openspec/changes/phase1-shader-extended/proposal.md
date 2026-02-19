# Change Proposal: phase1-shader-extended

## Why
Phase 1 Week 5 requires full shader inspection capabilities: reflection, constant buffer values, source code access, disassembly format selection, multi-stage output, pipeline state, and bindings inspection.

## What Changes

### Shader Commands
- Extend `rdc shader` CLI with new options:
  - `--reflect`: Show input/output signatures, resources, constant blocks
  - `--constants`: Show actual constant buffer values
  - `--source`: Show shader source code (fallback to disasm if no debug info)
  - `--target <format>`: Specify disassembly format
  - `--targets`: List available disassembly formats
  - `-o <file>`: Export to file
  - `--all`: Output all stages
- Add `rdc shaders [--stage STAGE] [--sort FIELD]` - list all unique shaders in frame

### Pipeline Commands
- Add `rdc pipeline [eid] [section]` - show pipeline state (ia/vs/hs/ds/gs/rs/ps/om/cs)

### Bindings Commands
- Add `rdc bindings [eid] [--set N] [--binding N]` - descriptor set details

### Backend
- Add daemon JSON-RPC handlers for new queries
- Extend query_service with reflection/constant extraction

## Scope
In scope:
- All `rdc shader`, `rdc shaders`, `rdc pipeline`, `rdc bindings` subcommands per design doc
- TSV and JSON output modes
- File export with format auto-detection

Out of scope:
- Path-addressed `cat/ls/tree` commands (separate change)
- Shader debug (Phase 4)

## Compatibility
- No breaking changes to existing commands
- New options only affect new behavior
