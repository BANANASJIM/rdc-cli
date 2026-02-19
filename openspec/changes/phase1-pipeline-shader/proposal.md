# Change Proposal: phase1-pipeline-shader

## Why
Phase 1 Week 5 in roadmap requires read-only pipeline/shader inspection commands so users can inspect shader stage state, resource bindings, and shader metadata without GUI.

## What Changes
- Add CLI commands:
  - `rdc pipeline [eid] [section]`
  - `rdc bindings [eid]`
  - `rdc shader [eid] [stage]`
  - `rdc shaders`
- Add daemon JSON-RPC handlers for the above queries.
- Extend query service with pipeline/shader extraction helpers.
- Preserve current output conventions (TSV default + JSON mode).

## Scope
In scope (MVP for Week 5):
- Stage-level metadata and available shader handles
- Bound resource listing per stage (read-only)
- Basic shader inventory (`rdc shaders` unique set)

Out of scope for this change:
- Full disassembly target matrix
- Constant buffer recursive expansion
- Source/debuginfo fallback complexity
- Path-addressed `cat/ls/tree` commands

## Compatibility
- No breaking changes to existing commands
- Requires active daemon session with replay available
