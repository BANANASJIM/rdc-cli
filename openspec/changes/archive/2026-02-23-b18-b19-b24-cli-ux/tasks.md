# Tasks: Fix CLI UX Bugs B18 + B19 + B24

## Task 1: Add PID alive check to `require_session()` (B18)

- **Files**: `src/rdc/commands/_helpers.py`
- **Changes**:
  - After `load_session()` returns a non-None session, read `pid = getattr(session, "pid", None)`.
  - If `isinstance(pid, int)` and `not is_pid_alive(pid)`: call `delete_session()`,
    emit `"stale session cleaned (daemon died); run 'rdc open' to restart"` (JSON-wrapped
    when `_json_mode()` is True, plain `error: …` otherwise), and raise `SystemExit(1)`.
  - Both `is_pid_alive` and `delete_session` are already imported from `rdc.session_state`
    inside `require_session()` — no new imports needed.
  - Guard with `isinstance(pid, int)` to skip the check for sessions that predate PID
    tracking (where `pid` may be `None`).
- **Depends on**: nothing
- **Estimated complexity**: S

## Task 2: Remove `-i` short alias from `--case-sensitive` (B19)

- **Files**: `src/rdc/commands/search.py`
- **Changes**:
  - Verify that the `--case-sensitive` option declaration has no `-i` shorthand.
    Current declaration: `@click.option("--case-sensitive", is_flag=True, …)` — correct.
  - If `-i` is present as an alias (e.g., `@click.option("-i", "--case-sensitive", …)`),
    remove it so the option declaration is `--case-sensitive` only.
  - No behavioral change if `-i` was never added; the regression test (Task 6) will
    catch any future re-introduction.
- **Depends on**: nothing
- **Estimated complexity**: XS

## Task 3: Update `search` docstring for case default (B19)

- **Files**: `src/rdc/commands/search.py`
- **Changes**:
  - Ensure the `search_cmd` docstring states that search is case-insensitive by default
    and that `--case-sensitive` enables exact case matching.
  - Current docstring already contains: "Case-insensitive by default; use
    --case-sensitive to enable exact case matching." — verify this is present and
    accurate; update if needed.
- **Depends on**: nothing
- **Estimated complexity**: XS

## Task 4: Ensure capture path goes to stdout, hint to stderr (B24)

- **Files**: `src/rdc/commands/capture.py`
- **Changes**:
  - In `_emit_result`, when `result.path` is set:
    - `click.echo(result.path)` — no `err=True`; stdout only.
    - `click.echo(f"next: rdc open {result.path}", err=True)` — stderr only.
  - Verify that the `_fallback_renderdoccmd` function also follows this convention
    if it emits a path (it currently prints to stderr — either fix it or leave it as
    fallback-mode behavior with a comment).
  - No change to `--json` mode output (JSON goes to stdout unchanged).
- **Depends on**: nothing
- **Estimated complexity**: XS

## Task 5: Add B18 test — `test_require_session_cleans_stale_pid`

- **Files**: `tests/unit/test_session_commands.py`
- **Changes**:
  - Add `test_require_session_cleans_stale_pid`:
    - Build `SessionState` with `pid=99999`.
    - Monkeypatch `load_session` on `rdc.commands._helpers` to return the session.
    - Monkeypatch `rdc.session_state.is_pid_alive` to return `False`.
    - Monkeypatch `rdc.session_state.delete_session` to append to a list.
    - Assert `SystemExit` is raised and the `delete_session` mock was called.
- **Depends on**: Task 1
- **Estimated complexity**: S

## Task 6: Add B19 tests — `test_case_sensitive_flag` and `test_short_i_flag_removed`

- **Files**: `tests/unit/test_search.py`
- **Changes**:
  - Add `test_case_sensitive_flag`:
    - Monkeypatch `_daemon_call` (or equivalent) to capture params.
    - Invoke `CliRunner().invoke(main, ["search", "--case-sensitive", "Op"])`.
    - Assert `exit_code == 0` and `params["case_sensitive"] is True`.
  - Add `test_short_i_flag_removed`:
    - Invoke `CliRunner().invoke(main, ["search", "-i", "Op"])`.
    - Assert `result.exit_code != 0` (unrecognized option must cause a usage error).
    - This is a permanent regression guard against re-introducing the confusing alias.
- **Depends on**: Task 2
- **Estimated complexity**: S

## Task 7: Add B24 test — `test_capture_path_on_stdout`

- **Files**: `tests/unit/test_capture.py`
- **Changes**:
  - Add `test_capture_path_on_stdout`:
    - Monkeypatch `find_renderdoc`, `execute_and_capture` (returns success with
      `path="/tmp/test.rdc"`), and `build_capture_options`.
    - Invoke with `CliRunner(mix_stderr=False)` so stdout and stderr are separate.
    - Assert `result.exit_code == 0`.
    - Assert `/tmp/test.rdc` in `result.output` (stdout).
    - Assert `"next:"` not in `result.output` (hint must not pollute stdout).
- **Depends on**: Task 4
- **Estimated complexity**: S

## Task 8: Run lint and tests

- **Files**: none (verification step)
- **Changes**:
  - Run `pixi run lint && pixi run test`.
  - Zero failures required before PR is opened.
- **Depends on**: Tasks 1–7
- **Estimated complexity**: XS

---

## Parallelism

All implementation tasks (1–4) are independent and can run in parallel:

- **Task 1** modifies only `src/rdc/commands/_helpers.py`.
- **Task 2 + Task 3** modify only `src/rdc/commands/search.py` (can be combined
  into one atomic change).
- **Task 4** modifies only `src/rdc/commands/capture.py`.

Test tasks depend on their corresponding implementation tasks:

- **Task 5** depends on Task 1.
- **Task 6** depends on Tasks 2 + 3.
- **Task 7** depends on Task 4.
- **Task 8** depends on Tasks 5–7.

## Implementation Order

1. **Phase A (parallel)**: Tasks 1, 2+3, 4 — implementation fixes.
2. **Phase B (parallel)**: Tasks 5, 6, 7 — test coverage.
3. **Phase C**: Task 8 — lint + test verification.
