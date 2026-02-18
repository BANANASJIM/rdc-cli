# Test Plan: phase0-session-skeleton

## Scope
- In scope:
  - command contract for open/close/status/goto
  - session file create/read/update/delete
  - exit code behavior for missing session
- Out of scope:
  - daemon process checks
  - replay controller calls

## Test Matrix
- Unit:
  - open writes session file
  - status reads session file
  - goto updates current_eid
  - close removes session file
- Mock:
  - isolated temp HOME for session path
- Integration:
  - deferred

## Cases
- Happy path:
  - open -> status -> goto -> status -> close
- Error path:
  - goto without session returns non-zero
  - close without session returns non-zero
- Edge cases:
  - goto with negative eid rejected

## Assertions
- Exit codes:
  - success 0, failure 1
- Output contract:
  - status contains capture/current_eid/opened_at

## Risks & Rollback
- Risk: temporary schema diverges from later daemon schema
- Rollback: map fields in a migration helper when daemon lands
