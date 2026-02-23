# Test Plan: Phase 5 — pick-pixel

## Unit Tests

### PP-U: CLI command (`tests/unit/test_pick_pixel_commands.py`)

Monkeypatch `_daemon_call` on the `rdc.commands.pick_pixel` module. Use `CliRunner`.

| ID | Description | Input | Expected |
|---|---|---|---|
| PP-U-01 | Default output format | `pick-pixel 512 384` | stdout `r=0.5000  g=0.3000  b=0.1000  a=1.0000` |
| PP-U-02 | JSON output | `pick-pixel 512 384 --json` | valid JSON with `x`, `y`, `eid`, `target`, `color` keys |
| PP-U-03 | JSON color values correct | `pick-pixel 512 384 --json` | `color.r == 0.5`, `color.g == 0.3`, `color.b == 0.1`, `color.a == 1.0` |
| PP-U-04 | EID argument forwarded | `pick-pixel 512 384 120` | params `eid == 120` sent to daemon |
| PP-U-05 | No EID omits key from params | `pick-pixel 512 384` | `"eid"` not in captured params |
| PP-U-06 | `--target` forwarded | `pick-pixel 512 384 --target 2` | params `target == 2` sent to daemon |
| PP-U-07 | Default target is 0 | `pick-pixel 512 384` | params `target == 0` |
| PP-U-08 | Non-integer x rejected | `pick-pixel abc 384` | exit code 2 |
| PP-U-09 | Non-integer y rejected | `pick-pixel 512 xyz` | exit code 2 |
| PP-U-10 | Missing session exits 1 | monkeypatch `load_session` → None | exit code 1 |
| PP-U-11 | Daemon error exits 1 | `_daemon_call` raises `SystemExit(1)` | exit code 1 |
| PP-U-12 | Command registered in CLI | `rdc --help` | output contains `pick-pixel` |
| PP-U-13 | Float formatting 4 decimal places | response with `r=1.0, g=0.0, b=0.0, a=0.5` | `r=1.0000  g=0.0000  b=0.0000  a=0.5000` |
| PP-U-14 | Method name sent to daemon | `pick-pixel 512 384` | captured method == `"pick_pixel"` |

### PP-D: Handler (`tests/unit/test_pick_pixel_daemon.py`)

Use `DaemonState` + `MockReplayController` with `_pick_pixel_map`. Invoke via `_handle_request`.

| ID | Description | Setup | Expected |
|---|---|---|---|
| PP-D-01 | Happy path returns color | `_pick_pixel_map[(512,384)] = PixelValue([0.5,0.3,0.1,1.0])` | `result.color == {r:0.5, g:0.3, b:0.1, a:1.0}` |
| PP-D-02 | Result contains x, y, eid | same as PP-D-01 | `result.x == 512`, `result.y == 384`, `result.eid == 120` |
| PP-D-03 | Result contains target index and id | default target idx 0, rt ResourceId(42) | `result.target == {index:0, id:42}` |
| PP-D-04 | Target index 1 selects second RT | two output targets (RIDs 42, 43) | `result.target == {index:1, id:43}` |
| PP-D-05 | EID defaults to `state.current_eid` | no `eid` in params, `state.current_eid = 120` | `result.eid == 120` |
| PP-D-06 | EID param overrides current | `eid=88` in params | `_set_frame_event` called with 88 |
| PP-D-07 | SetFrameEvent called with force=True | `eid=120` in params | `(120, True)` in `ctrl._set_frame_event_calls` |
| PP-D-08 | Missing `x` → error -32602 | params `{y:0}` | error code -32602, message contains "x" |
| PP-D-09 | Missing `y` → error -32602 | params `{x:0}` | error code -32602, message contains "y" |
| PP-D-10 | No adapter → error -32002 | `state.adapter = None` | error code -32002 |
| PP-D-11 | EID out of range → error -32002 | `eid=9999`, `state.max_eid=120` | error code -32002 |
| PP-D-12 | No color targets → error -32001 | all output target resources are null (RID 0) | error code -32001, message contains "no color targets" |
| PP-D-13 | Target index out of range → error -32001 | one target, `target=5` | error code -32001 |
| PP-D-14 | MSAA texture rejected → error -32001 | `tex.msSamp = 4` | error code -32001, message contains "MSAA" |
| PP-D-15 | Unknown pixel returns zero RGBA | `_pick_pixel_map` empty | `color == {r:0.0, g:0.0, b:0.0, a:0.0}` |
| PP-D-16 | `keep_running` always True | any valid request | second element of handler return is `True` |
| PP-D-17 | Handler registered under `"pick_pixel"` | inspect `HANDLERS` dict in `rdc.handlers.pixel` | key `"pick_pixel"` present |

## GPU Integration Tests

Added to `tests/integration/test_daemon_handlers_real.py` in the `TestDaemonHandlersReal` class.
All tests use the existing `vkcube.rdc` fixture and the `vkcube_replay` session fixture.

| ID | Description | Setup | Assertions |
|---|---|---|---|
| PP-G-01 | pick_pixel at draw event returns valid RGBA | seek to first draw EID, pick pixel at center of viewport | `color` dict present; all values are floats; each value in `[0.0, 1.0]` (or slightly outside for HDR — assert finite) |
| PP-G-02 | pick_pixel result has expected schema | same as PP-G-01 | result has keys `x`, `y`, `eid`, `target`, `color`; `color` has keys `r`, `g`, `b`, `a` |
| PP-G-03 | target index and id are non-zero integers | same as PP-G-01 | `result["target"]["id"] > 0`, `result["target"]["index"] == 0` |
| PP-G-04 | Different pixels return different values | pick (0,0) and (width//2, height//2) at same draw EID | at least one channel differs between the two results (vkcube renders a colored spinning cube) |
| PP-G-05 | EID param is echoed in response | explicit `eid` param set to draw EID | `result["eid"] == draw_eid` |

### GPU test helper pattern

```python
def test_pick_pixel_valid_rgba(self) -> None:
    events_result = _call(self.state, "events", {"type": "draw"})
    draw_eid = events_result["events"][0]["eid"]
    result = _call(self.state, "pick_pixel", {"x": 320, "y": 240, "eid": draw_eid})
    c = result["color"]
    for ch in ("r", "g", "b", "a"):
        assert isinstance(c[ch], float)
        assert math.isfinite(c[ch])
```

## Coverage Requirements

- All new source lines in `src/rdc/commands/pick_pixel.py` and the new handler in
  `src/rdc/handlers/pixel.py` must be covered by unit tests.
- `pixi run lint && pixi run test` must pass with zero failures before PR.
- GPU tests run only under `pytest.mark.gpu` and are excluded from the default CI run.
