# Tasks

## B46 - Add capture path completion for `rdc open`

- [ ] Add a local filesystem completion helper for the `CAPTURE` argument in `src/rdc/commands/session.py`.
- [ ] Wire the helper into `open_cmd` argument declaration so `rdc open <TAB>` suggests valid paths.
- [ ] Filter completion output to directories and `.rdc` files, preserving shell-friendly path formatting.

## B47 - Make VFS completion silent without a session

- [ ] Harden `_complete_vfs_path` in `src/rdc/commands/vfs.py` to return empty completions on session/RPC failures.
- [ ] Catch non-happy-path completion errors without surfacing runtime traces during TAB completion.
- [ ] Keep normal command execution errors unchanged; scope behavior change to completion-only flow.

## B48 - Support stage-only shader query after `goto`

- [ ] Update `shader` argument parsing in `src/rdc/commands/pipeline.py` to accept stage-only invocation (`rdc shader ps`).
- [ ] Resolve missing EID from session current event state before dispatching shader requests.
- [ ] Keep explicit form (`rdc shader <eid> <stage>`) behavior intact for all existing flags and outputs.

## B49 - Ensure `capture --list-apis` exits before capture flow

- [ ] Verify/adjust command flow in `src/rdc/commands/capture.py` so `--list-apis` short-circuits before executable validation.
- [ ] Ensure list mode does not enter split/local injection paths and does not require `-- EXECUTABLE` arguments.
- [ ] Keep output contract for API listing stable in text and JSON modes.

## B50 - Fix unreachable remote list error reporting

- [ ] Update `src/rdc/commands/remote.py` to surface connection failures as explicit errors for `remote list --url ...`.
- [ ] Restrict `no targets found` output to successful empty responses only.
- [ ] Align split-mode and local-mode failure handling so both return actionable connection errors.

## B51 - Clarify `pass` index base in help/docs

- [ ] Update `pass` command help/docstring in `src/rdc/commands/resources.py` to state that numeric index is 0-based.
- [ ] Update user-facing docs that reference pass lookup (for example `docs/usage.md` and `docs/index.md`) with 0-based wording.
- [ ] Keep naming lookup behavior unchanged while clarifying index semantics in CLI help text.

## Final validation

- [ ] Run `pixi run lint`.
- [ ] Run `pixi run test`.
- [ ] Execute manual verification steps from `test-plan.md` on a real capture/daemon session.
