# Test Plan: normalize `localhost` to `127.0.0.1` in proxy remote URL

## Unit (mocked — no GPU required)

`tests/unit/test_remote_core.py` (`TestNormalizeRemoteHost`, new class):

1. `_normalize_remote_host("localhost")` returns `"127.0.0.1"`.
2. `_normalize_remote_host("LOCALHOST")` returns `"127.0.0.1"` (case-insensitive).
3. `_normalize_remote_host("Localhost")` returns `"127.0.0.1"`.
4. `_normalize_remote_host("127.0.0.1")` returns `"127.0.0.1"` unchanged.
5. `_normalize_remote_host("192.168.1.5")` returns unchanged.
6. `_normalize_remote_host("::1")` returns `"::1"` unchanged — genuine IPv6.
7. `_normalize_remote_host("myserver.local")` returns unchanged.

`tests/unit/test_remote_core.py` (`TestParseUrl` — extend existing class):

8. `parse_url("localhost")` returns `("127.0.0.1", 39920)` — normalization in parser.
9. `parse_url("localhost:39920")` returns `("127.0.0.1", 39920)`.
10. `parse_url("[::1]:39920")` returns `("::1", 39920)` — IPv6 bracket form untouched.
11. Existing `test_localhost` test updated: `parse_url("localhost")` now returns
    `("127.0.0.1", 39920)`, not `("localhost", 39920)`.

`tests/unit/test_daemon_server_unit.py` (new test targeting `_load_remote_replay`
mock path, or a direct unit for the normalization call at the `CreateRemoteServerConnection`
boundary):

12. `_load_remote_replay` called with `remote_url="localhost:39920"`: verify that
    `rd.CreateRemoteServerConnection` receives `"127.0.0.1:39920"`, not
    `"localhost:39920"`. (Mock `rd` and `find_renderdoc`.)

`tests/unit/test_remote_core.py` (`TestBuildConnUrl` — extend existing class):

13a. `build_conn_url("127.0.0.1", 39920)` still returns `"127.0.0.1:39920"`.
13b. `build_conn_url("localhost", 39920)` returns `"127.0.0.1:39920"` — this
     updates the existing assertion at `test_remote_core.py:76` (covers hosts
     loaded from pre-fix state files and split-mode daemon handlers).

State-file key consistency:

14. (In `tests/unit/test_remote_core.py` or a dedicated unit) After
    `parse_url("localhost:39920")` returns `("127.0.0.1", 39920)`, the resulting
    `_state_path("127.0.0.1", 39920)` is `…/127.0.0.1_39920.json` — confirm
    no `localhost` key appears in the path.

Hardcoded literals (`tests/unit/test_android_commands.py`,
`tests/unit/test_capture_core.py`):

15. Android setup (`android.py:339,342`): the existing assertion at
    `test_android_commands.py:325` changes from
    `CreateRemoteServerConnection.assert_called_once_with("localhost:12345")`
    to `"127.0.0.1:12345"`. Android target control (`android.py:464`): assert
    the mocked `rd.CreateTargetControl` first argument is `"127.0.0.1"`.
16. `capture_core.py:100,103`: assert the mocked `rd.EnumerateRemoteTargets`
    host argument is `"127.0.0.1"` (the existing `_discover_latest_target`
    tests use `lambda _host, ...` mocks — extend or add one assertion capturing
    the host).

`tests/unit/test_capture_control.py` (TargetControl `--host` option,
`_connect` seam at `capture_control.py:32`):

17. `rdc attach 12345` (no `--host`): the mocked `rd.CreateTargetControl` first
    argument is `"127.0.0.1"` (default `localhost` normalized).
18. `rdc attach 12345 --host LOCALHOST`: the mocked `rd.CreateTargetControl`
    first argument is `"127.0.0.1"` (explicit, case-insensitive).
19. `rdc attach 12345 --host 192.168.1.50`: the mocked `rd.CreateTargetControl`
    first argument is `"192.168.1.50"` unchanged (non-localhost passthrough).

Run: `pixi run test` (unit only). Full gate: `pixi run check`.

## Manual / real-GPU

Prerequisites: dual-stack Linux host; `renderdoccmd remoteserver` running on
`localhost:39920` (binds `0.0.0.0:39920`); a valid `.rdc` capture file.

1. **Before fix (baseline)**: `rdc open frame.rdc --proxy localhost:39920` stalls
   at "uploading: 0%" indefinitely — confirm the regression under test.
2. **After fix**: same command completes normally; `rdc status` shows
   `remote: 127.0.0.1:39920`; a replay query (`rdc draws`) succeeds.
3. **IPv4 explicit still works**: `rdc open frame.rdc --proxy 127.0.0.1:39920`
   behaves identically to (2).
4. **IPv6 not broken**: if a genuine IPv6 remoteserver is running on `[::1]:39920`,
   `rdc open frame.rdc --proxy [::1]:39920` still connects (literal `::1` is
   not normalized).
5. **`rdc remote connect localhost:39920`** succeeds; `rdc remote status` shows
   host `127.0.0.1`; `~/.rdc/remote/127.0.0.1_39920.json` exists (not
   `localhost_39920.json`).

(Steps 1-3 directly reproduce and verify the reported real-GPU issue.)
