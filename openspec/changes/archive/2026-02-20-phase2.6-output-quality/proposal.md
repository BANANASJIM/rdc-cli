# Proposal: phase2.6-output-quality

## Summary

Fix three output-quality issues in the daemon server and client:
1. Enum values show as numeric repr instead of readable names
2. UINT_MAX sentinel byte-size values show as large integers instead of "-"
3. Client socket timeout is too short (2s) causing failures on slow handlers

## Motivation

- `pipe_topology`, `pipe_blend`, `pipe_stencil`, `pipe_samplers`, `postvs`: enum fields like
  topology, blend factors, stencil ops, and address modes printed as `<BlendFactor.SrcAlpha: 3>`
  instead of `"SrcAlpha"`.
- `pipe_vbuffers`, `pipe_ibuffer`: RenderDoc uses `UINT64_MAX` as sentinel for "unknown size";
  displaying as `18446744073709551615` is confusing.
- `daemon_client.send_request` defaulted to 2s timeout; shader disassembly and heavy pipeline
  queries can take longer, causing spurious `TimeoutError`.

## Design

### Helpers added to `daemon_server.py`

```python
_UINT_MAX_SENTINEL = (1 << 64) - 1

def _enum_name(v: Any) -> Any:
    return v.name if hasattr(v, "name") else v

def _sanitize_size(v: int) -> int | str:
    return "-" if v >= _UINT_MAX_SENTINEL else v
```

### Handler changes

| Handler | Field | Change |
|---|---|---|
| `pipe_topology` | `topology` | `_enum_name(GetPrimitiveTopology())` |
| `pipe_blend` | `srcColor/dstColor/colorOp/srcAlpha/dstAlpha/alphaOp` | `_enum_name(...)` |
| `pipe_stencil` | `failOperation/depthFailOperation/passOperation/function` | `_enum_name(...)` |
| `pipe_samplers` | `addressU/addressV/addressW/filter` | `_enum_name(...)` |
| `postvs` | `topology` | `_enum_name(...)` |
| `pipe_vbuffers` | `byteSize` | `_sanitize_size(...)` |
| `pipe_ibuffer` | `byteSize` | `_sanitize_size(...)` |

### Client change

`daemon_client.send_request` default `timeout` raised from `2.0` to `30.0`.
