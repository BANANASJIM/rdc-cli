# Test Plan: GPU Test Coverage Expansion (Track B)

## Fixture Pattern
All new test classes MUST follow the existing pattern:
- `_setup` autouse fixture takes `vkcube_replay` AND `rd_module`
- `self.state = _make_state(vkcube_replay, rd_module)`
- Call via `_call(self.state, method, params)` — state is FIRST arg

## Test Classes and Methods

### Class: `TestBufferDecodeReal`

```python
@pytest.mark.gpu
class TestBufferDecodeReal:
    @pytest.fixture(autouse=True)
    def _setup(self, vkcube_replay: tuple[Any, Any, Any], rd_module: Any) -> None:
        self.state = _make_state(vkcube_replay, rd_module)

    def _first_draw_eid(self) -> int:
        result = _call(self.state, "events")
        events = result["events"]
        assert len(events) > 0, "no events in capture"
        return events[0]["eid"]

    def test_cbuffer_decode_returns_data(self) -> None:
        """cbuffer_decode returns variables dict for VS stage cbuffer."""
        eid = self._first_draw_eid()
        # stage is a string name ("vs"), binding (not slot) is the key
        result = _call(self.state, "cbuffer_decode", {"eid": eid, "stage": "vs", "set": 0, "binding": 0})
        # If no cbuffer at binding 0, handler returns -32001; otherwise returns variables
        assert "variables" in result or "set" in result

    def test_vbuffer_decode_returns_vertex_data(self) -> None:
        """vbuffer_decode returns columns + vertices for a draw event."""
        eid = self._first_draw_eid()
        result = _call(self.state, "vbuffer_decode", {"eid": eid})
        assert "columns" in result
        assert "vertices" in result
```

### Class: `TestShaderMapAndAllReal`

```python
@pytest.mark.gpu
class TestShaderMapAndAllReal:
    @pytest.fixture(autouse=True)
    def _setup(self, vkcube_replay: tuple[Any, Any, Any], rd_module: Any) -> None:
        self.state = _make_state(vkcube_replay, rd_module)

    def test_shader_map_returns_rows(self) -> None:
        """shader_map returns {"rows": [...]} with at least VS + FS entries."""
        result = _call(self.state, "shader_map")
        assert "rows" in result
        assert len(result["rows"]) >= 2

    def test_shader_all_returns_stages(self) -> None:
        """shader_all returns {"eid": ..., "stages": [...]} with at least VS + FS."""
        result = _call(self.state, "shader_all")
        assert "stages" in result
        assert len(result["stages"]) >= 2
```

## Notes
- `_call` signature: `_call(state, method, params=None)` — state is first arg (not last)
- `cbuffer_decode` test uses `assert "variables" in result or "set" in result`:
  vkcube may not have a cbuffer at set=0/binding=0 for the VS stage — both outcomes
  (populated variables OR an empty-but-valid `{"eid":..., "set":0, "binding":0, "variables":[]}`)
  are acceptable. Do NOT use `assert "error" not in result` — `_call` already asserts that.
- `vbuffer_decode` with no `count` param reads all vertices automatically
- `shader_map` wraps rows in `{"rows": [...]}` (NOT a flat dict)
- `shader_all` wraps result in `{"eid": ..., "stages": [...]}` (NOT a bare list)

## Regression
All existing GPU test classes must still pass. Run full `pixi run test-gpu` after adding new classes.
