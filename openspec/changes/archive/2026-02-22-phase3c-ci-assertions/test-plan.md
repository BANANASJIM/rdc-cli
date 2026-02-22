# Test Plan: phase3c-ci-assertions

## Scope

### In scope
- `_assert_call` helper: exit 2 on no session, exit 2 on daemon RPC error, exit 2 on daemon
  unreachable, returns result dict on success
- `assert-pixel`: pixel_history composition, tolerance comparison, no-passing-mod error,
  last-passing-mod selection, `--json` output, `--target` forwarding
- `assert-clean`: log composition, severity ranking and filtering, default severity,
  `--json` output, message listing on failure
- `assert-count`: count composition, all 5 operators (eq/gt/lt/ge/le), boundary conditions,
  `--pass` forwarding, `--json` output
- `assert-state`: pipeline composition, key-path parsing (simple + hyphenated sections),
  path traversal (dict + list indexing), value normalization (bool/numeric/string),
  invalid section/path error handling, `--json` output
- CLI registration: all 4 commands visible in `--help`
- GPU integration tests on `hello_triangle.rdc`

### Out of scope
- Daemon handler tests (existing methods `pixel_history`, `log`, `count`, `pipeline`
  already tested)
- `assert-image` (separate module, already tested in Phase 3A)
- Performance benchmarking of assertion commands
- CI YAML template generation

## Test Matrix

| Layer | Scope | File |
|-------|-------|------|
| Unit | `_assert_call` helper (3 cases) | `tests/unit/test_assert_ci_commands.py` |
| Unit | `assert-pixel` command (10 cases) | `tests/unit/test_assert_ci_commands.py` |
| Unit | `assert-clean` command (8 cases) | `tests/unit/test_assert_ci_commands.py` |
| Unit | `assert-count` command (10 cases) | `tests/unit/test_assert_ci_commands.py` |
| Unit | `assert-state` command (12 cases) | `tests/unit/test_assert_ci_commands.py` |
| Unit | CLI registration (2 cases) | `tests/unit/test_assert_ci_commands.py` |
| GPU | `assert-pixel` pass on real capture | `tests/integration/test_daemon_handlers_real.py` |
| GPU | `assert-pixel` fail on real capture | `tests/integration/test_daemon_handlers_real.py` |
| GPU | `assert-clean` on hello_triangle | `tests/integration/test_daemon_handlers_real.py` |
| GPU | `assert-count` pass on real capture | `tests/integration/test_daemon_handlers_real.py` |
| GPU | `assert-count` fail on real capture | `tests/integration/test_daemon_handlers_real.py` |
| GPU | `assert-state` topology on real capture | `tests/integration/test_daemon_handlers_real.py` |

## Cases

### `_assert_call` helper

1. **No active session**: `load_session` returns `None`; function calls `sys.exit(2)`;
   stderr contains `"no active session"`.
2. **Daemon RPC error**: `send_request` returns `{"error": {"message": "no capture loaded"}}`;
   function calls `sys.exit(2)`; stderr contains `"no capture loaded"`.
3. **Success path**: `send_request` returns `{"result": {"value": 42}}`; function returns
   `{"value": 42}` without exiting.

### `assert-pixel`

4. **Exact match — pass**: `pixel_history` returns one modification with `passed=True`,
   `post_mod={"r": 0.5, "g": 0.3, "b": 0.1, "a": 1.0}`; `--expect "0.5 0.3 0.1 1.0"`
   with `--tolerance 0`; exit 0; stdout starts with `"pass:"`.
5. **Within tolerance — pass**: `post_mod` differs by 0.005 per channel from `--expect`;
   `--tolerance 0.01`; exit 0.
6. **Outside tolerance — fail**: `post_mod` R differs by 0.02 from expected; `--tolerance 0.01`;
   exit 1; stdout starts with `"fail:"`.
7. **Tolerance boundary — pass (inclusive)**: channel diff equals tolerance exactly
   (e.g. `|0.51 - 0.5| = 0.01`, `--tolerance 0.01`); exit 0.
8. **No passing modifications**: all modifications have `passed=False`; exit 2; stderr
   contains `"no passing modification"`.
9. **Empty modifications list**: `modifications` is `[]`; exit 2; stderr contains
   `"no passing modification"`.
10. **Multiple mods — last passing used**: 3 modifications: `[passed=True post_mod=A,
    passed=False, passed=True post_mod=B]`; command uses `post_mod=B` (last passing);
    `--expect` matches B; exit 0.
11. **JSON pass output**: matching pixel; exit 0; output is valid JSON with `"pass": true`,
    `"expected"`, `"actual"`, `"tolerance"` keys.
12. **JSON fail output**: mismatching pixel; exit 1; output is valid JSON with
    `"pass": false`.
13. **`--target` forwarded**: `--target 1` is passed; monkeypatched `_assert_call` receives
    `params` with `"target": 1`.

### `assert-clean`

14. **No messages at all**: `log` returns `{"messages": []}`; exit 0; stdout starts with
    `"pass:"`.
15. **Messages below threshold**: 2 messages with `level="INFO"`, `--min-severity HIGH`;
    exit 0 (INFO rank 3 > HIGH rank 0, so messages are filtered out).
16. **Messages at threshold**: 1 message with `level="HIGH"`, `--min-severity HIGH`;
    exit 1 (rank 0 <= rank 0); stdout starts with `"fail:"`.
17. **Messages above threshold**: 1 message with `level="HIGH"`, `--min-severity MEDIUM`;
    exit 1 (rank 0 <= rank 1).
18. **Mixed severities — partial match**: `[HIGH, INFO]` messages, `--min-severity MEDIUM`;
    exit 1 (HIGH matches, INFO does not); `"fail: 1 message(s)"` in stdout.
19. **Default min-severity is HIGH**: no `--min-severity` flag, only `INFO` messages;
    exit 0.
20. **JSON pass**: no matching messages; exit 0; JSON has `"pass": true, "count": 0,
    "messages": []`.
21. **JSON fail**: 2 matching messages; exit 1; JSON has `"pass": false, "count": 2`,
    `"messages"` is a list of length 2.

### `assert-count`

22. **eq pass**: daemon returns `{"value": 42}`; `--expect 42 --op eq`; exit 0.
23. **eq fail**: daemon returns `{"value": 42}`; `--expect 43 --op eq`; exit 1.
24. **gt pass**: daemon returns `{"value": 10}`; `--expect 5 --op gt`; exit 0.
25. **gt fail at boundary**: daemon returns `{"value": 5}`; `--expect 5 --op gt`; exit 1
    (5 is not strictly greater than 5).
26. **lt pass**: daemon returns `{"value": 3}`; `--expect 5 --op lt`; exit 0.
27. **ge pass at boundary**: daemon returns `{"value": 5}`; `--expect 5 --op ge`; exit 0.
28. **le fail**: daemon returns `{"value": 6}`; `--expect 5 --op le`; exit 1.
29. **Default op is eq**: no `--op` flag; daemon returns `{"value": 42}`; `--expect 42`;
    exit 0.
30. **`--pass` forwarded**: `--pass "GBuffer"` is passed; monkeypatched `_assert_call`
    receives params with `"pass": "GBuffer"`.
31. **JSON output**: daemon returns `{"value": 42}`; `--expect 42`; exit 0; JSON has
    `"pass": true, "what": "draws", "actual": 42, "expected": 42, "op": "eq"`.

### `assert-state`

32. **Simple key match**: key-path `topology.topology`, pipeline returns
    `{"topology": "TriangleList"}`; `--expect TriangleList`; exit 0.
33. **Simple key mismatch**: key-path `topology.topology`, pipeline returns
    `{"topology": "TriangleList"}`; `--expect LineList`; exit 1.
34. **Nested path — dict traversal**: key-path `blend.blends.0.enabled`, pipeline returns
    `{"blends": [{"enabled": true, ...}]}`; `--expect true`; exit 0.
35. **Array index traversal**: key-path `blend.blends.1.colorBlend.source`, pipeline returns
    `{"blends": [{"colorBlend": {"source": "One"}}, {"colorBlend": {"source": "Zero"}}]}`;
    `--expect Zero`; exit 0 (index 1 correctly selected).
36. **Boolean case-insensitive**: pipeline returns `{"blends": [{"enabled": True}]}`;
    `--expect True` vs `--expect true` vs `--expect TRUE` all exit 0.
37. **Numeric value comparison**: key-path `viewport.width`, pipeline returns
    `{"width": 1920}`; `--expect 1920`; exit 0 (`str(1920) == "1920"`).
38. **Invalid section — exit 2**: key-path `nosuch.field`; section `"nosuch"` is not in
    the valid set; exit 2; stderr contains `"invalid section"`.
39. **Invalid path — key not found**: key-path `blend.nosuchkey`; pipeline returns
    `{"blends": [...]}`; `_traverse_path` fails; exit 2; stderr contains `"not found"`.
40. **Invalid path — index out of range**: key-path `blend.blends.99.enabled`; pipeline
    returns `{"blends": [{"enabled": true}]}`; exit 2; stderr contains error.
41. **Hyphenated section — depth-stencil**: key-path `depth-stencil.depthEnable`,
    `_parse_key_path` returns `("depth-stencil", ["depthEnable"])`; pipeline called with
    `section="depth-stencil"`; exit 0 if value matches.
42. **JSON pass**: matching state; exit 0; JSON has `"pass": true, "key_path"`, `"actual"`,
    `"expected"`, `"eid"`.
43. **JSON fail**: mismatching state; exit 1; JSON has `"pass": false`.

### CLI registration

44. **Commands visible in --help**: `CliRunner().invoke(main, ["--help"])` output contains
    `assert-pixel`, `assert-clean`, `assert-count`, `assert-state`.
45. **Individual --help exits 0**: `CliRunner().invoke(main, ["assert-pixel", "--help"])`
    exits 0 for all 4 commands.

## GPU Integration Tests

| # | Test | Setup | Assertion |
|---|------|-------|-----------|
| G1 | `test_assert_pixel_pass` | Call `pixel_history` on hello_triangle center pixel to learn actual color, then invoke `assert-pixel` with that color | exit 0 |
| G2 | `test_assert_pixel_fail` | Invoke `assert-pixel` with deliberately wrong color `"0.0 0.0 0.0 0.0"` on a non-background pixel | exit 1 |
| G3 | `test_assert_clean_pass` | Invoke `assert-clean` on hello_triangle (should have no HIGH messages) | exit 0 |
| G4 | `test_assert_count_pass` | First call `count` to get actual draw count, then invoke `assert-count draws --expect <actual>` | exit 0 |
| G5 | `test_assert_count_fail` | Invoke `assert-count draws --expect 999999` | exit 1 |
| G6 | `test_assert_state_pass` | Invoke `assert-state <draw_eid> topology.topology --expect TriangleList` on hello_triangle | exit 0 |

## Assertions

### Exit code contract (all 4 commands)
- Exit 0: assertion passed
- Exit 1: assertion failed (comparison mismatch)
- Exit 2: error (no session, daemon unreachable, RPC error, invalid arguments like
  missing path key, bad section name, no passing modification)
- This matches `assert-image` semantics

### `assert-pixel` contracts
- `--expect` must have exactly 4 space-separated float values
- Uses last modification where `passed == True`
- Tolerance comparison is inclusive: `|actual - expected| <= tolerance` passes
- Each channel compared independently; first failing channel reported in text output
- `--target` defaults to 0

### `assert-clean` contracts
- Severity rank: `HIGH=0, MEDIUM=1, LOW=2, INFO=3, UNKNOWN=4`
- Messages with `rank(level) <= rank(min_severity)` are violations
- `--min-severity` default is `HIGH`
- Unknown severity levels default to rank 4 (lowest severity, most permissive)

### `assert-count` contracts
- `what` choices: `draws`, `events`, `resources`, `triangles`, `passes`, `dispatches`,
  `clears` (same as `rdc count`)
- `--op` choices: `eq`, `gt`, `lt`, `ge`, `le` (default `eq`)
- `--expect` is required, integer type
- `--pass` is optional, forwarded as `"pass"` param to daemon

### `assert-state` contracts
- Key-path must contain at least one `.` (section + field)
- Hyphenated sections (`depth-stencil`, `push-constants`) parsed before splitting on `.`
- Valid sections: `topology`, `viewport`, `scissor`, `blend`, `stencil`, `rasterizer`,
  `depth-stencil`, `msaa`, `vbuffers`, `ibuffer`, `samplers`, `push-constants`, `vinputs`,
  `vs`, `hs`, `ds`, `gs`, `ps`, `cs`
- Numeric path segments index into lists; non-numeric segments are dict keys
- Boolean normalization: `True`/`False`/`true`/`false` all compared as lowercase
- Numeric values compared as `str(value) == expected`

### Error output contract
- All error messages printed to stderr via `click.echo(..., err=True)`
- Error messages start with `"error: "`
- Pass messages printed to stdout, start with `"pass: "`
- Fail messages printed to stdout, start with `"fail: "`
- JSON output always to stdout, never to stderr

## Risks & Rollback

| Risk | Impact | Mitigation |
|------|--------|------------|
| `pixel_history` response format changes | assert-pixel comparison breaks | Tests mock exact response shape; GPU tests validate real format |
| Pipeline section response varies by API | assert-state path may not exist on D3D | Test with Vulkan captures; section names are from Vulkan pipeline |
| Boolean serialization inconsistency | Python `True` vs JSON `true` | `_normalize_value` normalizes booleans to lowercase string |
| Large log output in assert-clean --json | JSON output very large on noisy captures | Limit `messages` array in JSON to first 100 entries |
| `_assert_call` exit semantics differ from `call()` | Confusion for contributors | Docstring clearly states exit 2 behavior; name prefix `_assert` makes intent clear |
| Rollback | Revert `assert_ci.py` and 4 registration lines in `cli.py` | No daemon changes to undo |
