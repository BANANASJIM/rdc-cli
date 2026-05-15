# OpenSpec: issue-224-vsin-mesh

## Summary

Expose vertex shader input (VS-In) mesh geometry through the existing `rdc mesh` CLI command
and the underlying daemon mesh handler.

## Motivation

The `rdc mesh` command currently supports `--stage vs-out` and `--stage gs-out` but not
`--stage vs-in`. VS-In corresponds to `MeshDataStage.VSIn = 0` in the RenderDoc API and
represents the raw per-vertex data fed to the Input Assembler — the most common geometry
inspection target for artists and tools debugging vertex attribute issues.

The handler `_handle_mesh_data` in `buffer.py` and the OBJ-export path in `mesh.py` are
already generic; only the stage map and the CLI option list need extending. This change
completes part of the unshipped geometry export plan from archived
`openspec/changes/archive/2026-02-19-phase2-buffer-decode`.

## Design

### Daemon layer

`_MESH_STAGE_MAP` in `buffer.py` maps CLI stage strings to `MeshDataStage` integer values.
Add `"vs-in": 0` alongside the existing `"vs-out": 1` and `"gs-out": 2` entries.

The existing decode path calls `GetPostVSData(instance, view, stage_int)` and passes the
returned `MeshFormat` to the generic geometry decoder — no changes needed below the map.

The error string at the invalid-stage guard (~buffer.py:283) currently reads
`"invalid stage <name>; use vs-out or gs-out"`. This change must update that string to
include `vs-in` so callers see a consistent list of valid values.

### CLI layer

The `--stage` Click `Choice` in `mesh_cmd` (`mesh.py`) hardcodes `["vs-out", "gs-out"]`.
Add `"vs-in"` as a valid choice. No other CLI logic changes.

## Risks and Limitations

- **Non-draw events**: `GetPostVSData(VSIn)` returns an empty `MeshFormat` (zero
  `vertexResourceId` / `vertexByteStride`) for compute or non-draw events. The existing
  guard at ~buffer.py:293 returns JSON-RPC error `-32001` `"no PostVS data at this event"`
  in this case — identical to the contract `vs-out` and `gs-out` already have. No
  silent-empty path exists; behavior is consistent across all three stages.

- **Multi-stream IA / topology mismatch**: VSIn may carry multiple vertex streams or
  non-Triangle* topologies. The OBJ face generator in `mesh.py` (~line 75-95) only handles
  Triangle* topologies, matching the existing limitation for `vs-out` and `gs-out`. This
  is acceptable and documented as a known limitation; the lower-level fallback
  (`GetVertexInputs` / `GetVBuffers` / `GetIBuffer`) is out of scope for this change.

- **D3D12 on Linux**: This development box runs Linux; D3D12 captures cannot be exercised
  locally. Verification follows the established model: ship the change, reporter
  (@Misaka-Mikoto-Tech) verifies against real D3D12 captures (same approach as PR #226).
