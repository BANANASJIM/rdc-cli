# Test Plan: phase0-core-checks

## Scope
- In scope:
  - adapter version parsing and compatibility selection
  - doctor check coverage and exit-code contract
  - capture `--list-apis` command behavior
- Out of scope:
  - real replay initialization on CI

## Test Matrix
- Unit:
  - adapter parsing and fallback behavior
  - doctor check output includes expected check names
  - capture list-apis argv mapping
- Mock:
  - mock renderdoc module with/without API surfaces
  - monkeypatch subprocess return codes
- Integration:
  - deferred to later phase
- Regression:
  - keep existing `rdc capture` passthrough behavior

## Cases
- Happy path:
  - doctor passes with mocked renderdoc + renderdoccmd
  - capture --list-apis calls `renderdoccmd capture --list-apis`
- Error path:
  - renderdoc import failure
  - capture subprocess non-zero bubbles up
- Edge cases:
  - malformed version string still handled safely by adapter

## Assertions
- Exit codes:
  - doctor: 0 pass, 1 any failure
  - capture: subprocess return code passthrough
- Output contract:
  - doctor errors on stderr-marked lines via Click output stream

## Risks & Rollback
- Risk: overfitting doctor to local environment
- Rollback: reduce checks to non-invasive subset
