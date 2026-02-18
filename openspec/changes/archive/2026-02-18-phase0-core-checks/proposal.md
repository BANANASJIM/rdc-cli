# Proposal: phase0-core-checks

## Goal
Strengthen Phase 0 foundation with adapter skeleton, richer doctor checks, and capture API discovery.

## Scope
- Add `adapter.py` with RenderDoc version parsing and method compatibility helpers.
- Expand `rdc doctor` checks to match current design baseline.
- Add `rdc capture --list-apis` passthrough mode.

## Non-goals
- Replay daemon implementation.
- GPU integration tests.
