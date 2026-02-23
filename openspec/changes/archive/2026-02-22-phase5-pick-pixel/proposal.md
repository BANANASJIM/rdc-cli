# Proposal: Phase 5 — pick-pixel

## Problem

Debugging pixel color values currently requires running `rdc pixel` (pixel history), which
returns the full modification list for a pixel across all contributing draw calls. When the
user only needs the current post-render color at a coordinate — e.g. to verify a shader
output, compare a reference value, or feed into a CI assertion — pixel history is overly
expensive and noisy. A lightweight single-call readback is missing.

## Solution

Add `rdc pick-pixel <x> <y> [eid] [--target N] [--json]` — a thin command backed by the
RenderDoc `PickPixel` API. It resolves the render target at the specified event, calls
`controller.PickPixel(rt_rid, x, y, sub, comp_type)`, and returns the RGBA float value.

## Design

### CLI

```
rdc pick-pixel <x> <y> [eid] [--target N] [--json]
```

| Argument / Option | Type | Default | Description |
|---|---|---|---|
| `x` | int (required) | — | Pixel X coordinate |
| `y` | int (required) | — | Pixel Y coordinate |
| `eid` | int (optional) | current event | Event ID to seek to before readback |
| `--target N` | int | 0 | Color render target index |
| `--json` | flag | false | Emit JSON instead of human-readable line |

Default (human-readable) output:

```
r=0.5000  g=0.3000  b=0.1000  a=1.0000
```

JSON output (via `--json`):

```json
{
  "x": 512, "y": 384, "eid": 120,
  "target": {"index": 0, "id": 42},
  "color": {"r": 0.5, "g": 0.3, "b": 0.1, "a": 1.0}
}
```

### RenderDoc API

`controller.PickPixel(texture_id, x, y, sub, typeCast)` returns a `PixelValue` whose
`floatValue` list holds `[r, g, b, a]` at indices 0–3.

- `texture_id`: `ResourceId` of the render target (resolved identically to `pixel_history`)
- `sub`: `Subresource()` — `sub.sample = 0` for non-MSAA; MSAA rejected the same as in `pixel_history`
- `typeCast`: `rd.CompType.Typeless`

### Handler: `_handle_pick_pixel`

Defined in `src/rdc/handlers/pixel.py`, registered in `HANDLERS` as `"pick_pixel"`.

Guard and RT-lookup logic is identical to `_handle_pixel_history`:

1. Reject if `state.adapter is None` → error `-32002`
2. Require `x` and `y` in params → error `-32602`
3. `_set_frame_event(state, eid)` → error `-32002` on failure
4. `pipe.GetOutputTargets()` → filter non-null → validate `target_idx` → error `-32001`
5. Check `tex.msSamp > 1` → reject MSAA → error `-32001`
6. Call `controller.PickPixel(rt_rid, x, y, sub, comp_type)`
7. Return `{x, y, eid, target: {index, id}, color: {r, g, b, a}}`

### Command: `pick_pixel_cmd`

Defined in `src/rdc/commands/pick_pixel.py`.

```python
@click.command("pick-pixel")
@click.argument("x", type=int)
@click.argument("y", type=int)
@click.argument("eid", required=False, type=int)
@click.option("--target", default=0, type=int, help="Color target index (default 0)")
@click.option("--json", "use_json", is_flag=True, help="JSON output")
def pick_pixel_cmd(x, y, eid, target, use_json):
    params = {"x": x, "y": y, "target": target}
    if eid is not None:
        params["eid"] = eid
    result = _daemon_call("pick_pixel", params)
    if use_json:
        write_json(result)
        return
    c = result["color"]
    click.echo(f"r={c['r']:.4f}  g={c['g']:.4f}  b={c['b']:.4f}  a={c['a']:.4f}")
```

Registered in `src/rdc/cli.py` as:

```python
main.add_command(pick_pixel_cmd, name="pick-pixel")
```

### Mock additions (`tests/mocks/mock_renderdoc.py`)

`PixelValue` dataclass already exists with `floatValue: list[float]`.

Add to `MockReplayController.__init__`:

```python
self._pick_pixel_map: dict[tuple[int, int], PixelValue] = {}
```

Add method:

```python
def PickPixel(self, texture_id, x, y, sub, comp_type) -> PixelValue:
    return self._pick_pixel_map.get((x, y), PixelValue())
```

### Key difference from pixel_history

| | `pixel_history` | `pick-pixel` |
|---|---|---|
| API call | `PixelHistory(...)` | `PickPixel(...)` |
| Return type | `list[PixelModification]` | `PixelValue` |
| Color access | `.shaderOut.col.floatValue` | `.floatValue[0..3]` |
| Use case | Full modification history | Current color at event |

## Files Changed

| File | Change |
|---|---|
| `src/rdc/commands/pick_pixel.py` | NEW — Click command |
| `src/rdc/handlers/pixel.py` | MODIFY — add `_handle_pick_pixel`, register in `HANDLERS` |
| `src/rdc/cli.py` | MODIFY — register `pick-pixel` command |
| `tests/mocks/mock_renderdoc.py` | MODIFY — add `_pick_pixel_map` + `PickPixel()` |
| `tests/unit/test_pick_pixel_commands.py` | NEW — CLI unit tests |
| `tests/unit/test_pick_pixel_daemon.py` | NEW — handler unit tests |
| `tests/integration/test_daemon_handlers_real.py` | MODIFY — add GPU integration tests |
