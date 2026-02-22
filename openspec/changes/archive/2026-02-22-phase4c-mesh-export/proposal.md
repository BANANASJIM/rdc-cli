# Phase 4C-1: Mesh Export — Proposal

## Summary

Add `mesh_data` daemon method and `rdc mesh` CLI command to export post-transform vertex data as OBJ format.

## Motivation

The existing `postvs` handler returns only metadata (resourceId, stride, numIndices, topology). Exporting mesh geometry for debugging requires decoded vertex positions from `GetBufferData()` + struct unpacking — daemon-side work since it needs the controller.

## Scope

- 1 new daemon method: `mesh_data`
- 1 new CLI command: `rdc mesh [EID] [--stage vs-out|gs-out] [-o FILE] [--json] [--no-header]`

## Design

### Daemon Handler: `_handle_mesh_data`

Location: `src/rdc/handlers/buffer.py`

Params: `{eid?, stage?}` — stage defaults to `"vs-out"`

Logic:
1. Map stage string to MeshDataStage enum value (`vs-out`→1, `gs-out`→2)
2. `GetPostVSData(0, 0, stage_val)` → MeshFormat
3. Read vertex buffer via `GetBufferData(mesh.vertexResourceId, offset, size)`
4. Decode float32 vertices using stride + format info
5. Read index buffer if `indexResourceId != 0`
6. Return structured JSON with vertices, indices, topology

Response shape:
```json
{
  "eid": 142, "stage": "vs-out", "topology": "TriangleList",
  "vertex_count": 36, "comp_count": 4, "stride": 16,
  "vertices": [[x,y,z,w], ...],
  "index_count": 0, "indices": []
}
```

### CLI Command: `rdc mesh`

Location: `src/rdc/commands/mesh.py` (new file)

Default output: OBJ format (v lines + f lines). Uses first 3 components for vertex positions. No perspective divide by default (preserves clip-space data).

Face generation by topology:
- TriangleList: sequential triples
- TriangleStrip: alternating winding
- TriangleFan: pivot on vertex 0
- PointList/LineList: no faces

## Non-Goals

- `vs-in` stage (already available via `vbuffer_decode`)
- Normal/UV extraction (future enhancement)
- Perspective divide (users post-process if needed)
