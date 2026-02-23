# Test Plan: Mock Accuracy Improvements (Track A)

## Scope
New file: `tests/unit/test_mock_renderdoc.py`
All tests run under `pixi run check` (no GPU required).

## Test Cases

### T1 — ResourceId has no .value attribute
```python
def test_resource_id_no_value_attribute():
    rid = ResourceId(42)
    with pytest.raises(AttributeError):
        _ = rid.value

def test_resource_id_int_works():
    rid = ResourceId(42)
    assert int(rid) == 42
```

### T2 — SaveTexture configurable failure
```python
def test_save_texture_success_by_default(mock_ctrl):
    texsave = MagicMock(); texsave.resourceId = ResourceId(1)
    assert mock_ctrl.SaveTexture(texsave, "/tmp/out.png") is True

def test_save_texture_failure_when_flag_set(mock_ctrl):
    mock_ctrl._save_texture_fails = True
    texsave = MagicMock(); texsave.resourceId = ResourceId(1)
    assert mock_ctrl.SaveTexture(texsave, "/tmp/out.png") is False
```

### T3 — GetTextureData/GetBufferData per-resource behavior
```python
def test_get_texture_data_default(mock_ctrl):
    sub = MagicMock()
    data = mock_ctrl.GetTextureData(ResourceId(99), sub)
    assert isinstance(data, bytes) and len(data) > 0

def test_get_texture_data_configurable(mock_ctrl):
    mock_ctrl._texture_data[5] = b"custom"
    data = mock_ctrl.GetTextureData(ResourceId(5), MagicMock())
    assert data == b"custom"

def test_get_texture_data_raises_on_error_id(mock_ctrl):
    mock_ctrl._raise_on_texture_id.add(7)
    with pytest.raises(Exception):
        mock_ctrl.GetTextureData(ResourceId(7), MagicMock())
```

### T4 — ContinueDebug index-based (not consumable)
```python
def test_continue_debug_index_based(mock_ctrl):
    debugger = object()
    mock_ctrl._debug_states[id(debugger)] = [[state1], [state2]]
    # First call returns batch 0
    assert mock_ctrl.ContinueDebug(debugger) == [state1]
    # Second call returns batch 1
    assert mock_ctrl.ContinueDebug(debugger) == [state2]
    # Third call returns [] (exhausted)
    assert mock_ctrl.ContinueDebug(debugger) == []
    # Calling again still returns [] (not error)
    assert mock_ctrl.ContinueDebug(debugger) == []
```

### T5 — FreeTrace double-free detection
```python
def test_free_trace_records_freed(mock_ctrl):
    trace = MagicMock()
    mock_ctrl.FreeTrace(trace)
    assert id(trace) in mock_ctrl._freed_traces

def test_free_trace_double_free_raises(mock_ctrl):
    trace = MagicMock()
    mock_ctrl.FreeTrace(trace)
    with pytest.raises(RuntimeError, match="double-free"):
        mock_ctrl.FreeTrace(trace)
```

## Regression Guarantee
All existing tests in `tests/unit/` must still pass. Run `pixi run check` before PR.
