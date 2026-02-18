# Proposal: phase0-session-skeleton

## Goal
Add Phase 0 session command skeleton for `open/close/status/goto` with local session state.

## Scope
- Add `rdc open`, `rdc close`, `rdc status`, `rdc goto` commands.
- Use local session file (`~/.rdc/sessions/default.json`) as temporary implementation.
- No daemon/replay behavior yet.

## Non-goals
- Real RenderDoc replay lifecycle.
- JSON-RPC transport.
