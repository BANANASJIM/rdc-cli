# Normalize `localhost` to `127.0.0.1` in proxy remote URL

## Problem

`rdc open <cap> --proxy localhost:39920` stalls indefinitely at "uploading: 0%"
on dual-stack hosts. Root cause: `localhost` resolves to `::1` (IPv6) on such
hosts, while `renderdoccmd remoteserver` binds IPv4-only (`0.0.0.0:39920`).
`rd.CreateRemoteServerConnection("localhost:39920")` therefore connects to `::1`
and blocks forever — no error, no timeout surfaced to the user.

`--proxy 127.0.0.1:39920` works immediately. The failure mode is a silent
indefinite stall, the worst possible UX signal (the user can't distinguish a
slow upload from a hang).

Verified on real GPU hardware.

## Entry paths traced

Every path where a user-supplied host string eventually reaches a RenderDoc API
or rdc-cli socket call:

| # | Entry point | File : line | Host string flow |
|---|-------------|-------------|-----------------|
| 1 | `rdc open CAP --proxy HOST:PORT` | `commands/session.py:147` — `proxy_url` option | `proxy_url` → `open_session(remote_url=proxy_url)` → `start_daemon(remote_url=...)` → daemon argv `--remote-url HOST:PORT` → `daemon_server.py:817` → `_load_remote_replay(state, remote_url)` → `rd.CreateRemoteServerConnection(remote_url)` at `daemon_server.py:568` |
| 2 | `rdc open CAP --listen ADDR --proxy HOST:PORT` | `commands/session.py:295` | same `proxy_url` → `listen_open_session(remote_url=proxy_url)` → same daemon path |
| 3 | `rdc open CAP --android` | `commands/session.py:230` | `_resolve_android_url()` returns `f"localhost:{port}"` at `session.py:97` — this is the same literal-localhost problem, currently in the Android path; the forwarded port is IPv4 only |
| 4 | `rdc remote connect HOST:PORT` | `commands/remote.py:96` | `parse_url(url)` → `host, port` → `build_conn_url(host, port)` → `connect_remote_server(rd, conn_url)` → `rd.CreateRemoteServerConnection(conn_url)` at `remote_core.py:105` |
| 5 | `rdc remote list` / `rdc remote capture` | `commands/remote.py:133,244` | host from `--url` via `parse_url`, **or from saved state** via `_resolve_url` → `load_latest_remote_state()` (`remote.py:49`) → same `build_conn_url(host, port)` → same `rd.CreateRemoteServerConnection` |
| 6 | `rdc android setup` | `commands/android.py:339` | `conn_url = f"localhost:{forwarded_port}"` → `connect_remote_server(rd, conn_url)` at `android.py:342` |
| 7 | `rdc android capture` (target control) | `commands/android.py:464` | `rd.CreateTargetControl("localhost", local_port, ...)` — this is `CreateTargetControl`, not `CreateRemoteServerConnection`; same IPv6 risk |
| 8 | `capture_core.py:100,103` | internal enumeration | `rd.EnumerateRemoteTargets("localhost", ...)` — local capture use only, no user-visible flag |
| 9 | `rdc attach IDENT` / `capture-trigger` / `capture-list` / `capture-copy` | `commands/capture_control.py:47,72,88,139` — `--host` option (default `localhost`) | `host` → `_connect(rd, host, ident)` (`capture_control.py:32`) → `rd.CreateTargetControl(host, ident, ...)` — user-supplied `--host` (default and explicit `localhost`/`LOCALHOST`) reaches `CreateTargetControl` un-normalized; same IPv4-only risk class |

The critical path for the reported bug is entry #1. Paths #3, #6, #7, #8 also
use the literal `"localhost"` string hardcoded in the implementation; the user
has no control over them. The `parse_url` function in `remote_core.py` is the
shared parser for path #4 and for path #5 when `--url` is given; without
`--url`, path #5 takes its host from the saved state file and bypasses
`parse_url` entirely.

## Root-cause seam

`daemon_server.py:568` — `rd.CreateRemoteServerConnection(remote_url)` — receives
`remote_url` as a plain string passed through from the CLI argument without any
host normalization. The string `"localhost:39920"` is passed directly to the
RenderDoc C++ API, which resolves it via `getaddrinfo` with no `AI_ADDRCONFIG`
or family hint, returning `::1` first on a dual-stack host.

## Solution

### Normalization function

Add `_normalize_remote_host(host: str) -> str` to `remote_core.py`. If the
input is the literal string `"localhost"` (case-insensitive), return
`"127.0.0.1"`. Otherwise return the input unchanged. Emit one `logging.debug`
line when normalization fires.

```
def _normalize_remote_host(host: str) -> str:
    if host.lower() == "localhost":
        logging.getLogger(__name__).debug(
            "normalizing 'localhost' -> '127.0.0.1' (RenderDoc remote protocol is IPv4-only)"
        )
        return "127.0.0.1"
    return host
```

### Why only the literal `localhost` string

- `::1` literals: genuine IPv6 intent — must not be rewritten.
- Non-loopback hostnames: may resolve to IPv6 on an IPv6-native remote server
  that actually runs a dual-stack `renderdoccmd` — must not break.
- Only `localhost` triggers the systematic mismatch: DNS resolves it to `::1`
  first on dual-stack Linux; `renderdoccmd remoteserver` never listens on `::1`.

### Chosen normalization point: `parse_url` in `remote_core.py`

`parse_url` (`remote_core.py:52`) is the single entry-point for all
user-supplied `HOST[:PORT]` strings on the `rdc remote` command family (paths
#4, #5). Applying normalization there covers those paths with one change.

For path #1 (the bug), `--proxy` bypasses `parse_url` entirely: `proxy_url` is
passed as a raw string directly to `open_session`. Two options:

**Option A** — normalize inside `parse_url` only, and also add a thin wrapper
`_parse_proxy_url(url)` called from `open_session` / `listen_open_session` (or
at `session.py:320`) that strips port and normalizes.

**Option B** — add a standalone `_normalize_remote_host` and call it at the
single RenderDoc API boundary: `daemon_server.py:568` before passing to
`rd.CreateRemoteServerConnection`.

**Decision: Option B**, single callsite at `daemon_server.py:568`. Rationale:

- The daemon subprocess receives the raw `--remote-url` argv; normalizing there
  means the fix covers every path (#1, #2, #3) without touching the CLI parsing
  layer.
- Placement detail: normalize at the top of `_load_remote_replay`
  (`daemon_server.py:552`), not inline at the call, so the normalized string is
  used both by `rd.CreateRemoteServerConnection` (line 568) and by the
  `state.remote_url` assignment (line 574) — `rdc status` reads
  `state.remote_url` (`handlers/core.py:35`) and must report `127.0.0.1:PORT`.
- Guard: `--proxy` also accepts protocol URLs (`adb://SERIAL`, see
  `session.py:149` metavar). The daemon-side normalization must not parse or
  rewrite those — use a plain string check (`remote_url.lower() == "localhost"`
  or `remote_url.lower().startswith("localhost:")` → replace the `localhost`
  prefix), which leaves `adb://...`, bracketed IPv6, and everything else
  untouched.
- `parse_url` normalization would not reach path #1 without additional plumbing,
  and would leave daemon_server.py unguarded if called via any other route.
- Additionally, call `_normalize_remote_host` inside `parse_url` (which feeds
  paths #4, #5) so `rdc remote connect localhost:39920` also works.
- Additionally, call `_normalize_remote_host` inside `build_conn_url`
  (`remote_core.py:38`). This closes a path the two seams above do not cover:
  `rdc remote list/capture/status` without `--url` load the host from a saved
  state file (`_resolve_url` → `load_latest_remote_state()` at
  `commands/remote.py:49`). A state file written before this fix may contain
  `host: "localhost"`, which would reach `rd.CreateRemoteServerConnection`
  un-normalized via `build_conn_url`. The same applies to the split-mode daemon
  handlers (`handlers/capture.py:96,122,162`), which also assemble via
  `build_conn_url`.
- The hardcoded literal `"localhost"` strings are **in scope** and changed to
  `"127.0.0.1"` directly (same IPv4-only renderdoc client risk class):
  - `commands/android.py:339` — `conn_url = f"localhost:{forwarded_port}"`
  - `commands/android.py:464` — `rd.CreateTargetControl("localhost", ...)`
  - `capture_core.py:100,103` — `rd.EnumerateRemoteTargets("localhost", ...)`
  - `commands/session.py:97` (`_resolve_android_url` returning
    `f"localhost:{port}"`) needs no literal change: it flows through the daemon
    `--remote-url` argv and is normalized at the daemon seam (path #3).
- Path #9 (`commands/capture_control.py`) takes a user-facing `--host` option
  (default `localhost`) that flows through `_connect` into
  `rd.CreateTargetControl`. This is normalized by calling `_normalize_remote_host`
  at the top of `_connect` (`capture_control.py:32`) — covering both the default
  and an explicit `--host localhost`/`--host LOCALHOST` — without changing the
  click default (cosmetic once `_connect` normalizes; minimal diff). The
  standalone helper is imported from `remote_core.py`, no logic is duplicated.

### State-file key implication

`remote_state.py:_state_path(host, port)` keys files on the host string as
provided. A user who previously ran `rdc remote connect localhost:39920` has a
state file at `~/.rdc/remote/localhost_39920.json`. After normalization inside
`parse_url`, the same command would save to `127.0.0.1_39920.json`. The
`localhost_39920.json` file becomes stale (a ghost entry). The read path does
not break on it: `load_latest_remote_state` iterates the directory and picks
the most-recently-saved file by `connected_at` timestamp; the ghost is valid
JSON.

The ghost is **not** purely cosmetic, however: if it is the *latest* state
(user connected pre-upgrade, then runs `rdc remote list` post-upgrade without
reconnecting), `_resolve_url(None)` returns `host="localhost"` from the file.
This is why `build_conn_url` also normalizes (see Solution above) — the stale
host is rewritten at URL-assembly time and the stall cannot recur. No file
migration is needed. The stale file can be cleaned with `rdc remote
disconnect` + reconnect. This should be noted in the changelog.

## Split-mode IPv6 analysis (not a bug — no change needed)

Split mode (`rdc open --listen` / `rdc open --connect`) uses rdc-cli's own
JSON-RPC socket, not `CreateRemoteServerConnection`. The server side (`run_server`
at `daemon_server.py:724`) binds via `socket.socket(socket.AF_INET, ...)` —
explicitly IPv4 only. The client side (`daemon_client.py:17,35`) uses Python's
`socket.create_connection((host, port), ...)`, which iterates **all**
`getaddrinfo` results in order: on a dual-stack host where `localhost` resolves
to `::1` first, the connect to `::1` (no listener) fails with an immediate
`ECONNREFUSED`, and `create_connection` falls through to `127.0.0.1`, which
succeeds. There is no silent stall — the failure mode that motivates this
change does not exist here, because the Python socket layer retries across
address families while RenderDoc's C++ client does not.

`--connect localhost:PORT` (`session.py:261-278`, parsed via `rsplit`, no
`parse_url`) therefore works as-is and is intentionally **not** normalized by
this change. Analyzed and closed; not an open question.

## Risks

- **None for genuine IPv6 deployments**: `::1` literal and non-loopback
  hostnames are untouched.
- **`rdc remote setup`** also calls `parse_url` → benefits from normalization in
  `parse_url` path.
- **Spec file** (`openspec/specs/daemon/spec.md`): the remote replay scenario
  should gain a note; no behavioral specification change is needed because the
  behavior is now correct by construction.
