# Proposal: phase0-structure-refactor

## Why
Current Phase 0 code works but command modules hold too much business logic. We need clearer layering before adding replay-heavy features.

## What Changes
- Introduce structured layers: `core`, `transport`, `services`.
- Move session business logic into `services/session_service.py`.
- Keep CLI commands thin and orchestration-only.
- Keep existing command behavior unchanged.

## Scope
- Internal refactor only, no user-facing command changes.
- Update imports and tests accordingly.

## Non-goals
- New daemon methods.
- Replay integration.
