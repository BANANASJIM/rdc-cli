# Tasks: phase3c-ci-assertions

## Phase A: Tests first

### `_assert_call` helper tests
- [ ] In `tests/unit/test_assert_ci_commands.py`, add `test_assert_call_no_session`: monkeypatch `load_session` to return `None`; call `_assert_call("count")`; assert `SystemExit` with code 2; captured stderr contains `"no active session"`
- [ ] Add `test_assert_call_rpc_error`: monkeypatch `send_request` to return `{"error": {"message": "no capture loaded"}}`; call `_assert_call("count")`; assert `SystemExit` with code 2; captured stderr contains `"no capture loaded"`
- [ ] Add `test_assert_call_success`: monkeypatch `send_request` to return `{"result": {"value": 42}}`; call `_assert_call("count")`; assert return value is `{"value": 42}`

### `assert-pixel` tests
- [ ] Add `test_assert_pixel_exact_match`: mock `_assert_call` returning `{"modifications": [{"eid": 88, "passed": true, "post_mod": {"r": 0.5, "g": 0.3, "b": 0.1, "a": 1.0}}]}`; invoke `assert-pixel 88 512 384 --expect "0.5 0.3 0.1 1.0" --tolerance 0`; assert exit 0; stdout starts with `"pass:"`
- [ ] Add `test_assert_pixel_within_tolerance`: mock post_mod differs by 0.005 per channel; `--tolerance 0.01`; assert exit 0
- [ ] Add `test_assert_pixel_outside_tolerance`: mock post_mod R=0.52; `--expect "0.5 0.3 0.1 1.0" --tolerance 0.01`; assert exit 1; stdout starts with `"fail:"`
- [ ] Add `test_assert_pixel_tolerance_boundary`: mock post_mod R=0.51; `--expect "0.5 0.3 0.1 1.0" --tolerance 0.01`; assert exit 0 (inclusive: `|0.51 - 0.5| = 0.01 <= 0.01`)
- [ ] Add `test_assert_pixel_no_passing_mod`: mock all modifications have `passed=False`; assert exit 2; stderr contains `"no passing modification"`
- [ ] Add `test_assert_pixel_empty_modifications`: mock `{"modifications": []}`; assert exit 2; stderr contains `"no passing modification"`
- [ ] Add `test_assert_pixel_last_passing_used`: mock 3 modifications: `[{passed=True, post_mod=A}, {passed=False}, {passed=True, post_mod=B}]`; `--expect` matches B; assert exit 0
- [ ] Add `test_assert_pixel_json_pass`: matching pixel; `--json`; assert exit 0; parse JSON; assert `data["pass"] is True` and `"expected"` and `"actual"` keys present
- [ ] Add `test_assert_pixel_json_fail`: mismatching pixel; `--json`; assert exit 1; parse JSON; assert `data["pass"] is False`
- [ ] Add `test_assert_pixel_target_forwarded`: invoke with `--target 1`; capture params passed to `_assert_call`; assert `params["target"] == 1`

### `assert-clean` tests
- [ ] Add `test_assert_clean_no_messages`: mock `{"messages": []}`; assert exit 0; stdout starts with `"pass:"`
- [ ] Add `test_assert_clean_below_threshold`: mock `{"messages": [{"level": "INFO", "eid": 1, "message": "info msg"}, {"level": "INFO", "eid": 2, "message": "info msg 2"}]}`; `--min-severity HIGH`; assert exit 0
- [ ] Add `test_assert_clean_at_threshold`: mock `{"messages": [{"level": "HIGH", "eid": 1, "message": "high msg"}]}`; `--min-severity HIGH`; assert exit 1; stdout starts with `"fail:"`
- [ ] Add `test_assert_clean_above_threshold`: mock `{"messages": [{"level": "HIGH", "eid": 1, "message": "high msg"}]}`; `--min-severity MEDIUM`; assert exit 1 (HIGH rank 0 <= MEDIUM rank 1)
- [ ] Add `test_assert_clean_mixed_severities`: mock `[{"level": "HIGH", ...}, {"level": "INFO", ...}]`; `--min-severity MEDIUM`; assert exit 1; stdout contains `"1 message(s)"` (only HIGH matches, INFO filtered out)
- [ ] Add `test_assert_clean_default_severity_high`: no `--min-severity` flag; mock only INFO messages; assert exit 0
- [ ] Add `test_assert_clean_json_pass`: no matching messages; `--json`; assert exit 0; JSON has `"pass": true, "count": 0`
- [ ] Add `test_assert_clean_json_fail`: 2 matching messages; `--json`; assert exit 1; JSON has `"pass": false, "count": 2, "messages"` list of length 2

### `assert-count` tests
- [ ] Add `test_assert_count_eq_pass`: mock `{"value": 42}`; `--expect 42 --op eq`; assert exit 0
- [ ] Add `test_assert_count_eq_fail`: mock `{"value": 42}`; `--expect 43 --op eq`; assert exit 1
- [ ] Add `test_assert_count_gt_pass`: mock `{"value": 10}`; `--expect 5 --op gt`; assert exit 0
- [ ] Add `test_assert_count_gt_fail_boundary`: mock `{"value": 5}`; `--expect 5 --op gt`; assert exit 1
- [ ] Add `test_assert_count_lt_pass`: mock `{"value": 3}`; `--expect 5 --op lt`; assert exit 0
- [ ] Add `test_assert_count_ge_pass_boundary`: mock `{"value": 5}`; `--expect 5 --op ge`; assert exit 0
- [ ] Add `test_assert_count_le_fail`: mock `{"value": 6}`; `--expect 5 --op le`; assert exit 1
- [ ] Add `test_assert_count_default_op_eq`: no `--op` flag; mock `{"value": 42}`; `--expect 42`; assert exit 0
- [ ] Add `test_assert_count_pass_forwarded`: invoke with `--pass GBuffer`; capture params passed to `_assert_call`; assert `params["pass"] == "GBuffer"`
- [ ] Add `test_assert_count_json`: mock `{"value": 42}`; `--expect 42 --json`; assert exit 0; JSON has `"pass": true, "what": "draws", "actual": 42, "expected": 42, "op": "eq"`

### `assert-state` tests
- [ ] Add `test_assert_state_simple_match`: mock `_assert_call("pipeline", ...)` returns `{"topology": "TriangleList"}`; key-path `topology.topology`; `--expect TriangleList`; assert exit 0
- [ ] Add `test_assert_state_simple_mismatch`: same mock; `--expect LineList`; assert exit 1
- [ ] Add `test_assert_state_nested_path`: mock returns `{"blends": [{"enabled": True}]}`; key-path `blend.blends.0.enabled`; `--expect true`; assert exit 0
- [ ] Add `test_assert_state_array_index`: mock returns `{"blends": [{"colorBlend": {"source": "One"}}, {"colorBlend": {"source": "Zero"}}]}`; key-path `blend.blends.1.colorBlend.source`; `--expect Zero`; assert exit 0
- [ ] Add `test_assert_state_bool_case_insensitive`: mock returns `{"blends": [{"enabled": True}]}`; `--expect True` exits 0; `--expect true` exits 0; `--expect TRUE` exits 0
- [ ] Add `test_assert_state_numeric_value`: mock returns `{"width": 1920}`; key-path `viewport.width`; `--expect 1920`; assert exit 0
- [ ] Add `test_assert_state_invalid_section`: key-path `nosuch.field`; assert exit 2; stderr contains `"invalid section"`
- [ ] Add `test_assert_state_key_not_found`: mock returns `{"blends": [...]}`; key-path `blend.nosuchkey`; assert exit 2; stderr contains `"not found"`
- [ ] Add `test_assert_state_index_out_of_range`: mock returns `{"blends": [{"enabled": True}]}`; key-path `blend.blends.99.enabled`; assert exit 2
- [ ] Add `test_assert_state_hyphenated_section`: key-path `depth-stencil.depthEnable`; mock returns `{"depthEnable": True}`; `--expect true`; assert exit 0; verify `_assert_call` was called with `section="depth-stencil"`
- [ ] Add `test_assert_state_json_pass`: matching state; `--json`; assert exit 0; JSON has `"pass": true, "key_path", "actual", "expected", "eid"`
- [ ] Add `test_assert_state_json_fail`: mismatching state; `--json`; assert exit 1; JSON has `"pass": false`

### CLI registration tests
- [ ] Add `test_assert_commands_in_help`: `CliRunner().invoke(main, ["--help"])` output contains `assert-pixel`, `assert-clean`, `assert-count`, `assert-state`
- [ ] Add `test_assert_commands_help_exits_0`: for each of the 4 commands, `CliRunner().invoke(main, [cmd, "--help"])` exits 0

## Phase B: Implementation

### Shared helper
- [ ] Create `src/rdc/commands/assert_ci.py`
- [ ] Implement `_assert_call(method, params)`:
  - Load session via `load_session()`; if None, `click.echo("error: no active session", err=True)` + `sys.exit(2)`
  - Build JSON-RPC payload via `_request(method, 1, {"_token": session.token, **(params or {})})`
  - Call `send_request(session.host, session.port, payload.to_dict())`; catch `Exception` and `sys.exit(2)`
  - If `"error"` in response: `click.echo` error message to stderr + `sys.exit(2)`
  - Return `response["result"]`

### `assert-pixel` command
- [ ] Implement `assert_pixel_cmd` Click command:
  - Arguments: `eid` (int), `x` (int), `y` (int)
  - Options: `--expect` (required, str), `--tolerance` (float, default 0.01), `--target` (int, default 0), `--json`
  - Parse `--expect` into 4 floats; validate count
  - Call `_assert_call("pixel_history", {"eid": eid, "x": x, "y": y, "target": target})`
  - Filter modifications to `passed == True`, take last; if none, `sys.exit(2)` with stderr message
  - Compare each RGBA channel: `|actual - expected| <= tolerance`
  - Exit 0 on pass, 1 on fail; output text or JSON

### `assert-clean` command
- [ ] Implement `assert_clean_cmd` Click command:
  - Options: `--min-severity` (Choice HIGH/MEDIUM/LOW/INFO, default HIGH), `--json`
  - Define `_SEVERITY_RANK = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "INFO": 3, "UNKNOWN": 4}`
  - Call `_assert_call("log")`
  - Filter messages where `_SEVERITY_RANK.get(msg["level"], 4) <= _SEVERITY_RANK[min_severity]`
  - Exit 0 if empty, 1 if any violations; output text or JSON

### `assert-count` command
- [ ] Implement `assert_count_cmd` Click command:
  - Arguments: `what` (Choice draws/events/resources/triangles/passes/dispatches/clears)
  - Options: `--expect` (required, int), `--op` (Choice eq/gt/lt/ge/le, default eq), `--pass` (str, optional), `--json`
  - Define `_OPS = {"eq": operator.eq, "gt": operator.gt, "lt": operator.lt, "ge": operator.ge, "le": operator.le}`
  - Call `_assert_call("count", {"what": what, **({"pass": pass_name} if pass_name else {})})`
  - Apply `_OPS[op](actual, expected)`
  - Exit 0 if true, 1 if false; output text or JSON

### `assert-state` command
- [ ] Implement `_VALID_SECTIONS` frozenset with all 20 section names
- [ ] Implement `_HYPHENATED_SECTIONS = {"depth-stencil", "push-constants"}`
- [ ] Implement `_parse_key_path(key_path: str) -> tuple[str, list[str]]`:
  - Check hyphenated sections first (prefix match)
  - Fallback: split on `.`, first element is section, rest is field path
- [ ] Implement `_traverse_path(data: Any, path: list[str]) -> Any`:
  - For each segment: if data is list, try `int(seg)` for indexing; if dict, key lookup
  - On any failure (KeyError, IndexError, ValueError): `click.echo` error to stderr + `sys.exit(2)`
- [ ] Implement `_normalize_value(v: Any) -> str`:
  - `bool`: `str(v).lower()`
  - Otherwise: `str(v)`
- [ ] Implement `assert_state_cmd` Click command:
  - Arguments: `eid` (int), `key_path` (str)
  - Options: `--expect` (required, str), `--json`
  - Parse key-path; validate section in `_VALID_SECTIONS`; exit 2 if invalid
  - Call `_assert_call("pipeline", {"eid": eid, "section": section})`
  - Traverse path; normalize actual and expected; compare
  - Exit 0 if equal, 1 if not; output text or JSON

### CLI registration
- [ ] In `src/rdc/cli.py`, add imports:
  ```python
  from rdc.commands.assert_ci import (
      assert_clean_cmd,
      assert_count_cmd,
      assert_pixel_cmd,
      assert_state_cmd,
  )
  ```
- [ ] Add 4 registration lines:
  ```python
  main.add_command(assert_pixel_cmd, name="assert-pixel")
  main.add_command(assert_clean_cmd, name="assert-clean")
  main.add_command(assert_count_cmd, name="assert-count")
  main.add_command(assert_state_cmd, name="assert-state")
  ```
- [ ] Verify all Phase A unit tests pass: `pixi run test -k test_assert`

## Phase C: Integration

### GPU integration tests
- [ ] In `tests/integration/test_daemon_handlers_real.py`, add `test_assert_pixel_pass`:
  call `pixel_history` on hello_triangle to learn center pixel color, then invoke
  `assert_pixel_cmd` via `CliRunner` with that color as `--expect`; assert exit 0
- [ ] Add `test_assert_pixel_fail`: invoke `assert_pixel_cmd` with deliberately wrong
  color `"0.0 0.0 0.0 0.0"` on a pixel that is not background; assert exit 1
- [ ] Add `test_assert_clean_pass`: invoke `assert_clean_cmd` on hello_triangle
  (should have no HIGH messages); assert exit 0
- [ ] Add `test_assert_count_pass`: first call `count` handler to get actual draw count,
  then invoke `assert_count_cmd` with that value as `--expect`; assert exit 0
- [ ] Add `test_assert_count_fail`: invoke `assert_count_cmd` with `--expect 999999`;
  assert exit 1
- [ ] Add `test_assert_state_pass`: invoke `assert_state_cmd` with key-path
  `topology.topology` and `--expect TriangleList` at a known draw EID; assert exit 0

### Full test suite
- [ ] Run full unit test suite: `pixi run test` -- all tests green, coverage >= 80%
- [ ] Run lint and type check: `pixi run lint` -- zero ruff errors, zero mypy strict errors
- [ ] Run GPU tests: `RENDERDOC_PYTHON_PATH=/path/to/renderdoc/build/lib pixi run test-gpu -k test_assert`

## Phase D: Verify

- [ ] `pixi run check` passes (= lint + typecheck + test, all green)
- [ ] Manual: `rdc assert-pixel <eid> <x> <y> --expect "R G B A"` on a real capture, verify exit 0
- [ ] Manual: `rdc assert-pixel` with wrong color, verify exit 1
- [ ] Manual: `rdc assert-clean` on a clean capture, verify exit 0
- [ ] Manual: `rdc assert-count draws --expect <N>` on a real capture, verify exit 0
- [ ] Manual: `rdc assert-state <eid> topology.topology --expect TriangleList`, verify exit 0
- [ ] Archive: move `openspec/changes/2026-02-22-phase3c-ci-assertions/` -> `openspec/changes/archive/`
- [ ] Update `进度跟踪.md` in Obsidian vault
