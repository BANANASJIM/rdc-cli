# Fix CLI UX Bugs B18 + B19 + B24

## Summary

Three independent CLI usability bugs: B18 causes a cryptic error when the daemon
has crashed and the session file still exists; B19 binds `-i` to
`--case-sensitive`, which is the opposite of the universal grep convention;
B24 sends the captured file path only to stderr, making it inaccessible to
machine-parseable consumers.

## Motivation

B18 (P2): The most common failure mode after a daemon crash is to run any rdc
command and receive `daemon unreachable`. The user has no indication that the
session file is stale or that `rdc open` is the correct recovery action.
Cleaning the stale file and printing an actionable message eliminates confusion.

B19 (P3): Every Unix grep-like tool uses `-i` for case-insensitive. Binding `-i`
to `--case-sensitive` (the inverse) trips up any user who has grep muscle memory.
Removing the short form entirely avoids the semantic conflict without breaking the
long-form option.

B24 (P3): Scripts and CI pipelines commonly do `PATH=$(rdc capture ... -- app)`.
If the path goes only to stderr the substitution captures nothing and
subsequent commands (e.g., `rdc open "$PATH"`) silently receive an empty string.
The path must appear on stdout; human-readable hints stay on stderr.

---

## Bug Analysis

### B18: `require_session()` does not check if daemon PID is alive (P2)

#### Current behavior

After daemon process death, `require_session()` in
`src/rdc/commands/_helpers.py` loads the session file successfully (session
data is still valid on disk), then tries to talk to the dead daemon. The TCP
connection attempt fails with an `OSError`, which `call()` formats as:

```
error: daemon unreachable: [Errno 111] Connection refused
```

The stale session file remains on disk. The user does not know that the session
is stale, that they need to run `rdc open`, or that the session file can be
deleted.

#### Root cause

`require_session()` calls `load_session()` and checks for `None` (no session
file), but never checks whether the daemon recorded in the session is still
alive. The `SessionState` dataclass includes a `pid` field populated by
`rdc open` at session creation time.

#### Proposed fix

After `load_session()` returns a non-None session, check `is_pid_alive(session.pid)`.
If the daemon PID is dead:

1. Call `delete_session()` to remove the stale file.
2. Emit an actionable error message: `stale session cleaned (daemon died); run 'rdc open' to restart`.
3. Raise `SystemExit(1)`.

Both `is_pid_alive` and `delete_session` are already exported from
`rdc.session_state`. The `pid` attribute may be absent on sessions created
before PID tracking was added; guard with `getattr(session, "pid", None)` and
skip the check if `pid` is `None` or not an `int`.

```python
pid = getattr(session, "pid", None)
if isinstance(pid, int) and not is_pid_alive(pid):
    delete_session()
    msg = "stale session cleaned (daemon died); run 'rdc open' to restart"
    if _json_mode():
        click.echo(json.dumps({"error": {"message": msg}}), err=True)
    else:
        click.echo(f"error: {msg}", err=True)
    raise SystemExit(1)
```

---

### B19: `-i` bound to `--case-sensitive` (opposite of grep convention) (P3)

#### Current behavior

In `src/rdc/commands/search.py`, the `--case-sensitive` flag declaration is:

```python
@click.option("--case-sensitive", is_flag=True, help="Case-sensitive search.")
```

There is no `-i` shorthand currently in the file. However, if a previous
version introduced `-i` as a short alias, or if a developer adds it, the
meaning would be inverted relative to grep (`grep -i` = case-insensitive;
`rdc search -i` = case-sensitive). The correct fix is to ensure `-i` is never
registered as a shorthand for `--case-sensitive`.

#### Root cause

The grep convention (`-i` = ignore case = insensitive) is universally adopted.
Binding `-i` to the flag that *enables* case-sensitive matching is a semantic
inversion. Even if `-i` is not currently present, the risk of it being added
accidentally (e.g., for brevity) justifies an explicit test that it is
unrecognized.

#### Proposed fix

Ensure the `--case-sensitive` option declaration has no `-i` alias. The long
form `--case-sensitive` is descriptive enough; no short form is needed. Update
the docstring to clarify the default:

```
Searches across all unique shaders in the capture. Case-insensitive by
default; use --case-sensitive to enable exact case matching.
```

The fix is a no-op if `-i` was never added, but the regression test makes it
impossible to accidentally introduce the confusing alias in the future.

---

### B24: Capture path goes only to stderr (P3)

#### Current behavior

After a successful capture, `_emit_result` in `src/rdc/commands/capture.py`
prints:

```python
click.echo(result.path)            # stdout
click.echo(f"next: rdc open {result.path}", err=True)  # stderr
```

This is already partially correct in the current codebase. However, verify
that the machine-parseable path is on stdout and that the `next:` hint is
strictly on stderr, so that `$(rdc capture ... -- app)` command substitution
captures only the path.

#### Root cause

If the path line was previously emitted to stderr (via `err=True`), any script
using `$()` substitution or stdout-piping would receive empty output, causing
silent failures in CI pipelines or automation scripts.

#### Proposed fix

The `_emit_result` function must emit `result.path` (bare path, no prefix) on
stdout, and the `next: rdc open <path>` hint on stderr only:

```python
if result.path:
    click.echo(result.path)                          # stdout — machine parseable
    click.echo(f"next: rdc open {result.path}", err=True)  # stderr — human hint
```

This is the standard Unix convention: data on stdout, UI hints on stderr.

---

## Files Modified

| File | Bug | Change |
|------|-----|--------|
| `src/rdc/commands/_helpers.py` | B18 | Add PID alive check after `load_session()` |
| `src/rdc/commands/search.py` | B19 | Ensure no `-i` alias on `--case-sensitive` |
| `src/rdc/commands/capture.py` | B24 | Emit path on stdout, hints on stderr only |
| `tests/unit/test_session_commands.py` | B18 | `test_require_session_cleans_stale_pid` |
| `tests/unit/test_search.py` | B19 | `test_case_sensitive_flag`, `test_short_i_flag_removed` |
| `tests/unit/test_capture.py` | B24 | `test_capture_path_on_stdout` |

## Risk Assessment

**B18**: Low. Adds a conditional block that only fires when `is_pid_alive`
returns `False`. Normal sessions (live daemon) are completely unaffected. The
`getattr` guard ensures backward compatibility with old session files that may
lack the `pid` field.

**B19**: Very low. No functional change if `-i` was never added. The only
effect is a regression test that fails if a future developer accidentally
introduces the confusing alias.

**B24**: Very low if path was already on stdout. If the path was on stderr, the
fix restores the expected Unix convention. No change to exit codes or JSON
output mode.

## Alternatives Considered

**B18 — check TCP connectivity instead of PID**: Attempt a test connection
before every command. Rejected: adds latency to every invocation; the PID check
is O(1) via `/proc/<pid>/cmdline` and is the canonical approach for local
daemon liveness checking.

**B19 — add `-I` as case-insensitive alias**: Mirror grep's `-i` = insensitive
behavior by adding a new `-I` flag (insensitive) alongside `--case-sensitive`.
Rejected: adds flag surface area and the existing `--case-sensitive` long form
is already unambiguous.

**B24 — emit both stdout and stderr**: Print path to both stdout and stderr.
Rejected: stdout must be machine-parseable; mixing human hints into stdout
breaks `$()` and pipeline consumers.
