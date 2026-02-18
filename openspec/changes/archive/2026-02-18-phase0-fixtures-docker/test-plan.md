# Test Plan: phase0-fixtures-docker

## Scope
- In scope: script argument validation and Dockerfile presence.
- Out of scope: real capture generation in CI.

## Test Matrix
- Unit: helper function arg checks.
- Static checks: files exist and include expected commands.

## Cases
- Happy path: script builds renderdoccmd command with target executable.
- Error path: missing executable argument returns non-zero.

## Assertions
- Script uses `renderdoccmd capture -c`.
- Dockerfile includes python and uv setup.
