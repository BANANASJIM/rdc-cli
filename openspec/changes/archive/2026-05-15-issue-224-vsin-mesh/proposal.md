# OpenSpec: issue-224-vsin-mesh

## Summary

Expose vertex shader input (VS-In) mesh geometry through the existing `rdc mesh` CLI command
and the underlying daemon mesh handler.

## Motivation

The `rdc mesh` command currently supports `--stage vs-out` and `--stage gs-out` but not
`--stage vs-in`. VS-In corresponds to `MeshDataStage.VSIn = 0` in the RenderDoc API and
represents the raw per-vertex data fed to the Input Assembler — the most common geometry
inspection target for artists and tools debugging vertex attribute issues.

This change completes part of the unshipped geometry export plan from archived
`openspec/changes/archive/2026-02-19-phase2-buffer-decode`.

**Premise correction (adversarial review, 2026-05-15).** An earlier draft of this
proposal asserted that `_handle_mesh_data` and the OBJ-export path were "already generic;
only the stage map and the CLI option list need extending" and that "no changes needed
below the map". **That premise is RETRACTED.** Cross-checking against RenderDoc's official
`decode_mesh.py` reference revealed three correctness defects that are masked for
`vs-out`/`gs-out` (where `baseVertex == 0` and the position attribute is element 0) but
break `vs-in`:

1. `mesh.baseVertex` was never applied to decoded indices. RenderDoc's reference adds
   `mesh.baseVertex` to every index. For base-vertex `vs-in` draws the decoded mesh was
   wrong; for `vs-out`/`gs-out` it is a no-op (`baseVertex == 0`).
2. The position was read at `i*stride` (start of the interleaved vertex) instead of
   `i*stride + mesh.vertexByteOffset`, so `vs-in` positions were wrong whenever POSITION
   is not the first element of the vertex.
3. Index-buffer width is honored from `mesh.indexByteStride` (16-bit vs 32-bit), matching
   the reference; this is now covered by explicit regression tests.

The fix applies `baseVertex` and `vertexByteOffset` uniformly (not stage-special-cased),
exactly as the reference does, with a regression test asserting `vs-out` behavior is
unchanged.

## Design

### Daemon layer

`_MESH_STAGE_MAP` in `buffer.py` maps CLI stage strings to `MeshDataStage` integer values.
Add `"vs-in": 0` alongside the existing `"vs-out": 1` and `"gs-out": 2` entries.

The decode path calls `GetPostVSData(instance, view, stage_int)` and decodes the returned
`MeshFormat`. The decoder is corrected to match RenderDoc's `decode_mesh.py` reference:
indices are offset by `mesh.baseVertex`, the position attribute is read at
`i*stride + mesh.vertexByteOffset`, and the index width follows `mesh.indexByteStride`.
These corrections are applied uniformly across all stages (no stage special-casing); they
are no-ops for `vs-out`/`gs-out` where `baseVertex == 0` and the position is element 0.

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

### What vs-in supports

- **Position geometry**: the single position attribute described by `mesh.format`,
  located at `mesh.vertexByteOffset` within the interleaved vertex stride. Decoded
  positions are `vertexByteOffset`-correct.
- **Triangle connectivity**: `TriangleList` / `TriangleStrip` / `TriangleFan`, with
  indices that are `baseVertex`-correct (RenderDoc `decode_mesh` parity).

### Known limitations (vs-in)

- **Only the position attribute is exported**, not full per-attribute IA. Other vertex
  attributes (normals, UVs, colors) are not decoded. The lower-level fallback
  (`GetVertexInputs` / `GetVBuffers` / `GetIBuffer`) for full per-attribute IA decoding is
  explicitly out of scope for this change.
- **Packed / non-float position formats are unsupported**: the decoder only handles
  1/2/4-byte float-style components; packed formats (e.g. `R10G10B10A2`, SNORM/UNORM
  integer-packed) are not decoded.
- **Non-triangle topology exports vertices only**: `LineList`, `PointList`, patch and
  adjacency topologies produce no OBJ faces. Rather than silently emitting an empty/
  face-less OBJ, the CLI now prints a clear stderr warning naming the topology
  (e.g. `mesh: topology 'PatchList_3' has no OBJ face mapping; exported N vertices,
  0 faces`) so geometry loss is never silent.

- **D3D12 on Linux**: This development box runs Linux; D3D12 captures cannot be exercised
  locally. Verification follows the established model: ship the change, reporter
  (@Misaka-Mikoto-Tech) verifies against real D3D12 captures (same approach as PR #226).
