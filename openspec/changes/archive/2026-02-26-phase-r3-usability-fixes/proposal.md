# Phase R3: Usability Fixes (B46-B51)

## Motivation

Manual CLI usage surfaced six high-friction bugs that break expected workflows,
mainly around completion behavior, command argument ergonomics, and error
messaging clarity. These issues reduce trust in basic interactive usage even
when backend functionality is correct.

This change focuses on predictable operator experience for the existing command
surface, without introducing new feature scope.

## Scope

In scope:

- B46: add capture-path completion for `rdc open`
- B47: silence VFS completion errors when no active session/daemon
- B48: support stage-only shader invocation after `goto`
- B49: make `capture --list-apis` an explicit early-return mode
- B50: report unreachable `remote list --url` as connection failure
- B51: clarify 0-based index semantics for `pass`

Out of scope:

- Any new command beyond behavior fixes above
- New completion features unrelated to B46/B47
- Changes to replay/data query core semantics

## Design

### B46: `open` tab completion

- Add capture-path completion for `rdc open` so `<TAB>` offers local `.rdc`
  candidates from the filesystem.

### B47: VFS completion with no session

- Treat missing session / daemon-not-ready cases as completion-time no-result
  conditions, not user-facing runtime errors.
- Completion handlers return empty candidates on recoverable lookup failures.

### B48: `shader` stage-only form after `goto`

- Support `rdc shader <stage>` by resolving EID from session `current_eid`.
- Preserve explicit form `rdc shader <eid> <stage>` with unchanged precedence.

### B49: `capture --list-apis` execution path

- Ensure `--list-apis` is handled as an early-return information mode.
- Skip executable validation and injection-related flow when this flag is set.

### B50: `remote list --url` unreachable endpoint

- Separate transport/connectivity failures from valid-but-empty target lists.
- Report unreachable endpoint as a connection error with actionable wording,
  not "no targets found".

### B51: pass index base clarity

- Standardize user-facing wording to explicitly state pass indices are 0-based.
- Align command help and docs text to remove ambiguity.

## Risks

- Completion-path changes may affect shell-specific completion adapters
  (bash/zsh/fish) if output assumptions are inconsistent.
- Mixed-form `shader` argument parsing can regress if dispatch order is not
  strictly defined.
- Refined `remote list` errors may require updates where tests assert exact
  message strings.
