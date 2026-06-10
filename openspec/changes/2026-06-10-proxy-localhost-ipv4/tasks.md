# Tasks: normalize `localhost` to `127.0.0.1` in proxy remote URL

- [x] `remote_core.py`: add `_normalize_remote_host(host: str) -> str`; maps
      `"localhost"` (case-insensitive) → `"127.0.0.1"`, else identity; emits
      `logging.debug` when it fires
- [x] `remote_core.py`: call `_normalize_remote_host` inside `parse_url` on the
      extracted `host` before returning — covers `rdc remote connect/list/capture/setup`
- [x] `remote_core.py`: call `_normalize_remote_host` inside `build_conn_url` —
      covers hosts loaded from pre-fix state files (`_resolve_url` →
      `load_latest_remote_state`) and split-mode daemon handlers
      (`handlers/capture.py:96,122,162`)
- [x] `daemon_server.py`: normalize the `localhost` host portion of `remote_url`
      at the top of `_load_remote_replay` (plain string check; skip protocol
      URLs like `adb://`) so both `rd.CreateRemoteServerConnection` (line 568)
      and `state.remote_url` (line 574, shown by `rdc status`) see the
      normalized value — covers `rdc open --proxy` (the primary bug path) and
      the Android open path (`session.py:97`)
- [x] `commands/android.py:339`: `f"localhost:{forwarded_port}"` →
      `f"127.0.0.1:{forwarded_port}"`
- [x] `commands/android.py:464`: `rd.CreateTargetControl("localhost", ...)` →
      `"127.0.0.1"`
- [x] `capture_core.py:100,103`: `rd.EnumerateRemoteTargets("localhost", ...)` →
      `"127.0.0.1"`
- [x] `tests/unit/test_remote_core.py`: add `TestNormalizeRemoteHost` (items 1-7
      in test-plan); update `TestParseUrl.test_localhost` + add items 8-11;
      update `TestBuildConnUrl` (items 13a-13b, including the existing
      `localhost` assertion at line 76); add item 14
- [x] `tests/unit/test_daemon_server_unit.py`: add item 12 (normalization at
      `CreateRemoteServerConnection` boundary)
- [x] `tests/unit/test_android_commands.py`: update the existing assertion
      `CreateRemoteServerConnection.assert_called_once_with("localhost:12345")`
      (line 325) to `"127.0.0.1:12345"`; assert `CreateTargetControl` receives
      `"127.0.0.1"` (item 15)
- [x] `tests/unit/test_capture_core.py`: assert `EnumerateRemoteTargets`
      receives `"127.0.0.1"` as host (item 16)
- [x] `pixi run check` green (lint + typecheck + tests)
- [ ] Changelog note: state files previously keyed on `localhost` become stale
      after upgrade; `rdc remote disconnect && rdc remote connect 127.0.0.1:PORT`
      to clean up
- [ ] Fresh review of the diff
- [ ] Open PR targeting `master`
- [ ] Archive this OpenSpec folder after merge

## Out of scope

- Split-mode `--connect localhost:PORT` — analyzed and confirmed not a bug; no
  change needed (see proposal, "Split-mode IPv6 analysis").
