# Test Plan: Fix CLI UX Bugs B18 + B19 + B24

## B18: Stale PID detection in `require_session()`

### Root Cause Summary

`require_session()` in `src/rdc/commands/_helpers.py` loads the session file
but never verifies that the daemon PID recorded in the session is still alive.
When the daemon has died, any subsequent command fails with a cryptic TCP error
rather than an actionable message. The fix adds an `is_pid_alive(session.pid)`
check immediately after `load_session()` returns a non-None result.

### Unit tests — `tests/unit/test_session_commands.py`

**`test_require_session_cleans_stale_pid`**

- Build a `SessionState` with `pid=99999` (an integer unlikely to be a live
  process but guaranteed not to be `None`).
- Monkeypatch `load_session` (on `rdc.commands._helpers`) to return the
  session object.
- Monkeypatch `rdc.session_state.is_pid_alive` to return `False`.
- Monkeypatch `rdc.session_state.delete_session` to record calls in a list.
- Call `helpers_mod.require_session()`.
- Assert: `SystemExit` is raised.
- Assert: `delete_session` was called exactly once (stale file cleaned).

**Regression: `test_require_session_no_session`** (existing)

- Monkeypatch `load_session` to return `None`.
- Assert: `SystemExit(1)` raised with "no active session" message.
- Must still pass — the B18 path does not affect the no-session case.

**Regression: `test_require_session_live_pid`** (new or existing)

- Build a `SessionState` with `pid=<os.getpid()>` (current process is always
  alive).
- Monkeypatch `load_session` to return the session.
- Monkeypatch `rdc.session_state.is_pid_alive` to return `True`.
- Assert: `require_session()` returns without raising.
- Assert: `delete_session` is never called.

**Regression: `test_require_session_no_pid_field`** (new)

- Build a `SessionState` with no `pid` field (or `pid=None` if supported by
  the dataclass), to simulate sessions created before PID tracking.
- Monkeypatch `load_session` to return this session.
- Assert: `require_session()` returns without raising (the `getattr` guard
  must skip the PID check when `pid` is `None` or absent).

---

## B19: `-i` short alias must not exist on `--case-sensitive`

### Root Cause Summary

The grep convention is `-i` = case-insensitive. Binding `-i` to
`--case-sensitive` (which *enables* case-sensitive matching) is a semantic
inversion that confuses users with grep muscle memory. The fix is to ensure
the `--case-sensitive` option has no `-i` alias and that the long form is the
only way to enable case-sensitive mode.

### Unit tests — `tests/unit/test_search.py`

**`test_case_sensitive_flag`**

- Monkeypatch `_daemon_call` (or the equivalent send path) on the search
  command to capture the params dict passed to the daemon.
- Invoke `CliRunner().invoke(main, ["search", "--case-sensitive", "Op"])`.
- Assert: `exit_code == 0`.
- Assert: captured `params["case_sensitive"] is True`.

**`test_short_i_flag_removed`**

- Invoke `CliRunner().invoke(main, ["search", "-i", "Op"])` with `catch_exceptions=False`
  disabled so Click's error handling runs.
- Assert: `result.exit_code != 0` (Click must treat `-i` as an unrecognized
  option and exit with a usage error).
- Rationale: this is a regression guard. If a future developer accidentally
  adds `-i` as a short alias for `--case-sensitive`, this test will catch the
  semantic inversion before it ships.

**Regression: `test_case_insensitive_default`** (new)

- Invoke `CliRunner().invoke(main, ["search", "Op"])` (no case flag).
- Assert: captured `params["case_sensitive"] is False` (default must be False,
  i.e., case-insensitive by default).

---

## B24: Capture path must appear on stdout

### Root Cause Summary

After a successful capture, the captured file path must be emitted to stdout
so that command substitution (`$(rdc capture ... -- app)`) captures the path
for use in subsequent commands. The `next: rdc open <path>` hint is a human
UI message and must go to stderr only.

### Unit tests — `tests/unit/test_capture.py`

**`test_capture_path_on_stdout`**

- Monkeypatch `find_renderdoc` to return a mock (Python API path).
- Monkeypatch `execute_and_capture` to return a `CaptureResult` with
  `success=True`, `path="/tmp/test.rdc"`, and all other fields default.
- Monkeypatch `build_capture_options` to return a mock.
- Invoke `CliRunner(mix_stderr=False).invoke(capture_cmd, ["-o", "/tmp/test.rdc", "--", "/usr/bin/app"])`.
- Assert: `result.exit_code == 0`.
- Assert: `/tmp/test.rdc` appears in `result.output` (stdout).
- Assert: `"next:"` does NOT appear in `result.output` (stdout must be clean).
- Assert: `"next: rdc open /tmp/test.rdc"` appears in the stderr stream.

**Regression: `test_python_api_success`** (existing)

- Must still pass — the path `/tmp/test.rdc` appears in `result.output`
  (CliRunner merges stderr by default, so this still holds). Exit code 0.

**Regression: `test_capture_json_output`** (existing)

- Invoke with `--json`.
- Assert: JSON is valid; `"path"` key present; exit code 0.
- JSON mode output goes to stdout regardless; must not be broken by B24 fix.

---

## Test Matrix

| Test | Type | File | Covers |
|------|------|------|--------|
| `test_require_session_cleans_stale_pid` | unit | `test_session_commands.py` | B18 |
| `test_require_session_live_pid` | unit | `test_session_commands.py` | B18 regression |
| `test_require_session_no_pid_field` | unit | `test_session_commands.py` | B18 regression |
| `test_require_session_no_session` | unit | `test_session_commands.py` | B18 regression |
| `test_case_sensitive_flag` | unit | `test_search.py` | B19 |
| `test_short_i_flag_removed` | unit | `test_search.py` | B19 regression guard |
| `test_case_insensitive_default` | unit | `test_search.py` | B19 regression |
| `test_capture_path_on_stdout` | unit | `test_capture.py` | B24 |
| `test_python_api_success` | unit | `test_capture.py` | B24 regression |
| `test_capture_json_output` | unit | `test_capture.py` | B24 regression |
