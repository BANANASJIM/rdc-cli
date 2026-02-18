# Test Plan: phase0-structure-refactor

## Scope
- In scope: command behavior parity after refactor.
- Out of scope: new feature behavior.

## Test Matrix
- Unit: service functions for open/status/goto/close.
- Regression: existing command tests must continue to pass unchanged.

## Cases
- Happy path: open/status/goto/close flow still works.
- Error path: stale session and daemon unreachable still return failure.

## Assertions
- CLI output contract remains stable.
- Exit codes remain unchanged.
