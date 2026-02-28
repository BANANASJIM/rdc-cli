# Test Plan: Phase R3 Usability Fixes (B46-B51)

## Scope and Validation Strategy

This plan covers behavioral regressions and expected UX semantics for:

- B46: open path completion
- B47: completion silence on no-session for VFS
- B48: shader stage-only invocation after goto
- B49: `capture --list-apis` behavior
- B50: remote list unreachable error semantics
- B51: pass help/docs index clarity

Validation is split into:

- unit tests (command-level and helper-level behavior)
- CLI regression tests (stdout/stderr, exit code, and argument handling)
- shell completion checks (bash/zsh/fish)
- manual verification on a real capture workflow

---

## B46: `open` Path Completion

### Unit tests to add/update

- Add completion tests for `open` that validate path suggestions are produced for valid local paths.
- Add tests that completion output is filtered by typed prefix and does not emit unrelated paths.
- Add tests that directory candidates include the shell-appropriate trailing separator when required by completion framework.

### CLI regression cases

- `rdc open <TAB>` at repo root returns path candidates, no stack traces.
- `rdc open tests/<TAB>` returns entries under `tests/` only.
- Completing a non-existent prefix returns no candidates and no error text.

### Shell completion matrix

- **bash**: verify candidate emission format used by bash completion script.
- **zsh**: verify candidate list is shown and remains prefix-filtered.
- **fish**: verify completion descriptions (if present) do not break candidate parsing.

### Acceptance criteria

- Completion for `open` returns deterministic, prefix-filtered path candidates across bash/zsh/fish.
- No stderr noise for normal completion flow.
- Exit code `0` for completion invocation paths.

---

## B47: Completion Silence on No Session for VFS

### Unit tests to add/update

- Add tests for VFS-backed completion when no active session exists: completion returns empty results.
- Add tests that no user-facing error message is emitted during completion when session is absent.
- Add tests that unexpected internal exceptions still map to controlled completion behavior (no traceback output).

### CLI regression cases

- Invoke VFS completion on a fresh environment (no prior `open`/session): no candidates, no error text.
- Re-run after opening a session: completion returns VFS candidates normally.

### Shell completion matrix

- **bash/zsh/fish**: same expected silent-empty behavior with no-session state.

### Acceptance criteria

- No-session completion path is silent (no stderr/stdout diagnostics) and returns zero candidates.
- Completion invocation exits with code `0`.
- Behavior is consistent across bash, zsh, and fish.

---

## B48: Shader Stage-Only Invocation After `goto`

### Unit tests to add/update

- Add tests for shader-related command invocation that provide only stage argument after `goto` selected event/context.
- Add tests that stage-only invocation resolves against current event/pipeline context.
- Add negative test: without required context (no event/session), command fails with clear usage/error semantics.

### CLI regression cases

- `rdc goto <event>` then shader command with stage only (e.g., `vs`/`ps`) succeeds and prints expected section header/output fragment.
- Same stage-only invocation before `goto` fails with expected error message and non-zero exit.

### Acceptance criteria

- After valid `goto`, stage-only shader invocation succeeds with exit code `0`.
- Without required context, command fails with stable, user-facing error and exit code `!= 0`.
- No ambiguous argument parsing regressions introduced for existing full-form shader invocation.

---

## B49: `capture --list-apis` Behavior

### Unit tests to add/update

- Add tests that `capture --list-apis` returns supported API list without requiring capture target arguments.
- Add tests that list output format is stable (one API per line or documented canonical format).
- Add tests that `capture --list-apis --json` returns valid JSON and still bypasses executable validation.
- Add tests that incompatible flag combinations produce deterministic error messaging.

### CLI regression cases

- `rdc capture --list-apis` prints API list and exits successfully.
- `rdc capture --list-apis --json` prints valid JSON and exits successfully.
- `rdc capture --list-apis` in environments with no active capture target still succeeds.
- Invalid combo case returns non-zero exit and concise usage/error output.

### Acceptance criteria

- `capture --list-apis` is self-contained and exits `0` on success.
- Output contains expected known API names (at least one canonical API token expected by docs).
- `capture --list-apis --json` returns parseable JSON and exits `0`.
- Invalid flag combinations exit `!= 0` with explicit error text.

---

## B50: `remote list` Unreachable Error Semantics

### Unit tests to add/update

- Add tests for network-unreachable daemon/host: command returns user-friendly connectivity error.
- Add tests that unreachable errors are classified distinctly from empty remote list success cases.
- Add tests that timeout/refused variants map to consistent exit code and message category.

### CLI regression cases

- `rdc remote list --url <unreachable-host:port>` returns non-zero exit and clear "unreachable/connection" wording.
- `rdc remote list --url <reachable-host:port>` with no remotes returns success with empty-state output.

### Acceptance criteria

- Unreachable endpoint: exit code `!= 0`, no misleading empty-list success message.
- Reachable but empty: exit code `0` with explicit empty-state output.
- Error wording is actionable (indicates connectivity problem rather than data absence).

---

## B51: `pass` Help / Docs Index Clarity

### Unit tests to add/update

- Add tests for `rdc pass --help` content to ensure key usage lines and terminology are unambiguous.
- Add tests for docs/help text references to explicitly state numeric pass indices are 0-based.
- Add snapshot-style assertion for critical help fragment (`0-based`) to prevent wording regression.

### CLI regression cases

- `rdc pass --help` includes concise description and explicit `0-based` index wording.
- Docs pages that mention `pass <index|name>` include explicit 0-based wording.

### Acceptance criteria

- Help output for `pass` is discoverable and clear for first-time users.
- `pass` help/docs explicitly state index base (`0-based`).
- Help commands exit with code `0` and do not emit stderr noise in normal flow.

---

## Cross-Cutting Manual Verification (Real Capture Workflow)

Run on a real capture file and live daemon/session setup.

```bash
pixi run rdc open <real-capture.rdc>
pixi run rdc goto <valid-event-id>
pixi run rdc shader <stage-only>
pixi run rdc capture --list-apis
pixi run rdc capture --list-apis --json
pixi run rdc remote list --url <reachable-host:port>
pixi run rdc remote list --url <unreachable-host:port>
pixi run rdc pass --help
```

Manual checks:

- completion behavior for `open` and VFS paths under bash/zsh/fish
- stage-only shader behavior before and after `goto`
- clear distinction between unreachable remote errors and empty successful lists
- help/docs wording clarity for `pass`

Expected outcomes:

- success paths return exit code `0`
- connectivity/invalid-context failures return exit code `!= 0`
- stderr is only used for true error conditions
