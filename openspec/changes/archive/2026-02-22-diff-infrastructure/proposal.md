# Proposal: diff-infrastructure

## Summary

Add the foundational dual-daemon framework for `rdc diff <a.rdc> <b.rdc>`.
Covers the Click CLI entry point, dual daemon lifecycle management, the
`diff_service` layer with concurrent query coordination, and output flag
scaffolding. Individual diff modes (draws, resources, passes, pipeline,
framebuffer) are built on top in separate OpenSpecs.

## Design References

- `设计/交互模式.md` lines 245–268 — Diff mode coordination protocol
- `设计/命令总览.md` lines 119–132 — `rdc diff` command surface
- `设计/设计原则.md` lines 80–84 — Exit codes: 0=no diff, 1=has diff, 2=error

## Changes

### New files

| File | Description |
|------|-------------|
| `src/rdc/commands/diff.py` | Click command `diff`; args `<a> <b>`; mode flags; output flags; delegates to `diff_service` |
| `src/rdc/services/diff_service.py` | `DiffContext` dataclass; `start_diff_session()`, `stop_diff_session()`, `query_both()`, `query_both_sync()` |
| `tests/unit/test_diff_service.py` | Unit tests for service lifecycle, concurrent queries, error paths |
| `tests/unit/test_diff_command.py` | Unit tests for CLI: argument validation, exit codes, cleanup guarantee |

### Modified files

| File | Change |
|------|--------|
| `src/rdc/cli.py` | Register `diff_cmd` |
| `src/rdc/services/session_service.py` | Add `idle_timeout: int = 1800` keyword-only param to `start_daemon()` |
| `src/rdc/daemon_server.py` | Fix idle check: `idle_timeout_s > 0 and ...` so `0` means "never timeout" |

## Implementation Details

### `DiffContext` dataclass

```python
@dataclass
class DiffContext:
    session_id: str    # secrets.token_hex(6)
    host: str          # "127.0.0.1"
    port_a: int
    port_b: int
    token_a: str
    token_b: str
    pid_a: int
    pid_b: int
    capture_a: str
    capture_b: str
```

In-memory only — no session files written to `~/.rdc/sessions/`.

### `start_diff_session`

```python
def start_diff_session(
    capture_a: Path,
    capture_b: Path,
    *,
    timeout_s: float = 60.0,
) -> tuple[DiffContext | None, str]:
```

1. Generate session_id, two ports, two tokens.
2. Fork daemon A with `idle_timeout=120` (short orphan timer for crash safety).
3. Fork daemon B. If Popen raises, kill A, return error.
4. Register `atexit` handler for `stop_diff_session`.
5. Wait both daemons concurrently via `threading.Thread` (full `timeout_s`).
6. On any ping failure: kill both, return `(None, error)`.
7. Return `(DiffContext(...), "")`.

### `stop_diff_session`

```python
def stop_diff_session(ctx: DiffContext) -> None:
```

Four independent best-effort steps (each in try/except):
1. RPC shutdown daemon A.
2. RPC shutdown daemon B.
3. SIGTERM pid A if alive.
4. SIGTERM pid B if alive.

Never raises. Idempotent. Registered with `atexit`.

### `query_both`

```python
def query_both(
    ctx: DiffContext,
    method: str,
    params: dict[str, Any],
    *,
    timeout_s: float = 30.0,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, str]:
```

Two `threading.Thread` workers, each prepending correct `_token`. Original
`params` never mutated. Partial results available on single-side failure.

### `query_both_sync`

```python
def query_both_sync(
    ctx: DiffContext,
    calls: list[tuple[str, dict[str, Any]]],
    *,
    timeout_s: float = 30.0,
) -> tuple[list[dict[str, Any] | None], list[dict[str, Any] | None], str]:
```

Batch variant: 2N threads for N calls to both daemons.

### CLI command

```python
@click.command("diff")
@click.argument("capture_a", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.argument("capture_b", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--draws",       "mode", flag_value="draws")
@click.option("--resources",   "mode", flag_value="resources")
@click.option("--passes",      "mode", flag_value="passes")
@click.option("--stats",       "mode", flag_value="stats")
@click.option("--framebuffer", "mode", flag_value="framebuffer")
@click.option("--pipeline",    "pipeline_marker", default=None, metavar="MARKER")
@click.option("--json",        "output_json", is_flag=True)
@click.option("--format",      "fmt", type=click.Choice(["tsv", "unified", "json"]), default="tsv")
@click.option("--shortstat",   is_flag=True)
@click.option("--no-header",   is_flag=True)
@click.option("--timeout",     default=60.0, type=float)
def diff_cmd(...) -> None:
```

Mode resolution: `--pipeline MARKER` → `mode="pipeline"`; no flag → `"summary"`.
In this phase, all modes except `"summary"` are stubs that exit 2.
`try/finally` guarantees `stop_diff_session` cleanup.

### Exit code contract

| Code | Meaning |
|------|---------|
| 0 | No differences (or summary stub) |
| 1 | Differences found (follow-on mode handlers) |
| 2 | Error (startup failure, file not found, stub mode) |

### `start_daemon` idle_timeout param

Add `idle_timeout: int = 1800` keyword-only param. Default unchanged.
Diff callers pass `120` (2-minute orphan timer for crash safety).

Fix `daemon_server.py` idle check: `if idle_timeout_s > 0 and ...` so that
`idle_timeout=0` means "never timeout" (POSIX convention). Diff uses `120`
rather than `0` so orphan daemons self-terminate after 2 minutes on crash.

## Scope

| Component | Lines |
|-----------|-------|
| `src/rdc/services/diff_service.py` | ~120 |
| `src/rdc/commands/diff.py` | ~85 |
| `src/rdc/services/session_service.py` (param) | ~5 |
| `src/rdc/daemon_server.py` (idle check fix) | ~1 |
| `src/rdc/cli.py` (registration) | ~3 |
| `tests/unit/test_diff_service.py` | ~160 |
| `tests/unit/test_diff_command.py` | ~80 |
| **Total** | **~453** |
