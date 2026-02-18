# Test Plan: phase0-pixi-env

## Scope
- In scope: pixi config presence, task definitions, and docs update.
- Out of scope: full pixi runtime integration tests in CI.

## Test Matrix
- Unit/static: assert pixi.toml exists and includes required tasks.

## Cases
- Happy path: `pixi.toml` defines lint/typecheck/test/check.
- Error path: missing task should fail static test.

## Assertions
- README contains pixi usage section.
- pixi config includes python and uv.
