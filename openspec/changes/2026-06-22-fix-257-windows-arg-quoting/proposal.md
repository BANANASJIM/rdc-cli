# Fix #257: Platform-appropriate command-line quoting for child app args

## Motivation

`rdc capture -- <exe> <args>` passes child arguments to RenderDoc's
`ExecuteAndInject` as a single cmdline string built with `shlex.join`.
`shlex.join` follows POSIX quoting rules (single-quote wrapping), so a
Windows path like `D:\path\script.das` reaches the target process wrapped in
literal single quotes.  On Windows, `ExecuteAndInject` delegates to Win32
`CommandLineToArgvW`, which does not recognise POSIX quoting — the single
quotes are passed literally into `argv[0]`, breaking the launch.

## Design

Add `join_cmdline(args: list[str]) -> str` to `rdc._platform`.  The helper
dispatches on the module-level `_WIN` flag:

- **Windows**: delegates to `subprocess.list2cmdline`, which produces a
  string that `CommandLineToArgvW` parses correctly (double-quote wrapping,
  backslash escaping).
- **POSIX**: delegates to `shlex.join`, preserving existing behaviour.

`subprocess.list2cmdline` is pure-Python and ships with every CPython; no new
dependency is introduced.  Both `_platform.py` and `subprocess` are already
imported by callers, so the import footprint is zero.

Both call sites in `commands/capture.py` — the direct Python API path (line
~137) and the split-session path (line ~172) — are rerouted to
`_platform.join_cmdline(app_args)`.  The now-unused `import shlex` in
`capture.py` is removed.

## Risks

- `subprocess.list2cmdline` is a documented, stable part of the `subprocess`
  module and is the standard reference implementation for Win32 cmdline
  encoding.  Risk: negligible.
- Changing quoting on POSIX is a no-op (same `shlex.join` result), so no
  regression on Linux/macOS.
