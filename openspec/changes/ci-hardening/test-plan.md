# Test Plan: ci-hardening

## Scope
- In scope: commitlint config and workflow syntax.
- Out of scope: runtime behavior of GitHub hosted runners.

## Test Matrix
- Unit: none.
- Mock: none.
- Validation: workflow YAML + local commitlint config parse.

## Cases
- Happy path: conventional commit passes.
- Error path: non-conventional message fails.

## Assertions
- CI exposes commitlint as required check.
