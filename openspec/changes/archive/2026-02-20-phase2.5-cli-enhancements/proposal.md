# Phase 2.5 OpenSpec #2: CLI Enhancements

## Summary

Add `rdc completion` subcommand for shell completion scripts and enhance
`rdc doctor` with actionable build guidance when renderdoc is missing.

## Motivation

- Users need shell completions for productivity (`rdc <TAB>` should work)
- When `rdc doctor` reports renderdoc missing, users need clear build instructions
  instead of a bare "not found" message

## Design

### `rdc completion [bash|zsh|fish]`

- Uses Click 8's `get_completion_class` API to generate native completion scripts
- Optional shell argument; auto-detects from `$SHELL` if omitted
- Output goes to stdout for redirection; detection message goes to stderr

### `rdc doctor` enhancement

- New `_RENDERDOC_BUILD_HINT` constant with cmake build instructions
- Displayed on stderr when `renderdoc-module` check fails
- No change to exit codes or other checks

## Files Changed

- `src/rdc/commands/completion.py` (new)
- `src/rdc/commands/doctor.py` (modified)
- `src/rdc/cli.py` (register completion_cmd)
- `tests/unit/test_completion.py` (new, 5 tests)
- `tests/unit/test_doctor.py` (modified, 3 tests total)
