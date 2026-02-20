# OpenSpec #3: phase2-pipeline-state

## Summary

Expose all remaining PipeState query methods as VFS leaf routes under
`/draws/<eid>/pipeline/`. These are all simple `SetFrameEvent → PipeState.GetXxx()` calls
with text output (TSV/key-value).

## Motivation

The existing `/draws/<eid>/pipeline/summary` provides a high-level overview but lacks
granular state details. GPU debugging and agent analysis require inspecting individual
state components (viewport dimensions, blend equations, stencil ops, vertex layout).

All data is already available via PipeState methods — just needs VFS routing and formatting.

## Design

### VFS Routes

| Path | Kind | Handler | API |
|------|------|---------|-----|
| `/draws/<eid>/pipeline/topology` | leaf | pipe_topology | GetPrimitiveTopology() |
| `/draws/<eid>/pipeline/viewport` | leaf | pipe_viewport | GetViewport(0) |
| `/draws/<eid>/pipeline/scissor` | leaf | pipe_scissor | GetScissor(0) |
| `/draws/<eid>/pipeline/blend` | leaf | pipe_blend | GetColorBlends() |
| `/draws/<eid>/pipeline/stencil` | leaf | pipe_stencil | GetStencilFaces() |
| `/draws/<eid>/pipeline/vertex-inputs` | leaf | pipe_vinputs | GetVertexInputs() |
| `/draws/<eid>/pipeline/samplers` | leaf | pipe_samplers | GetSamplers(stage) |
| `/draws/<eid>/pipeline/vbuffers` | leaf | pipe_vbuffers | GetVBuffers() |
| `/draws/<eid>/pipeline/ibuffer` | leaf | pipe_ibuffer | GetIBuffer() |
| `/draws/<eid>/postvs` | leaf | postvs | GetPostVSData() |

No new CLI convenience commands — all accessed via `rdc cat /draws/<eid>/pipeline/<sub>`.

### Output Format

Key-value for single-value queries, TSV for list queries:

```
# topology
TriangleList

# viewport
x	0.0
y	0.0
width	1920.0
height	1080.0
minDepth	0.0
maxDepth	1.0

# blend (per-RT TSV)
rt	enabled	srcColor	dstColor	colorOp	srcAlpha	dstAlpha	alphaOp	writeMask
0	true	SrcAlpha	InvSrcAlpha	Add	One	Zero	Add	0xf

# vertex-inputs (TSV)
location	name	format	offset	perInstance
0	POSITION	R32G32B32_FLOAT	0	false
1	TEXCOORD	R32G32_FLOAT	12	false

# vbuffers (TSV)
slot	resourceId	offset	size	stride
0	42	0	4096	20

# ibuffer
resourceId	42
offset	0
size	1024
stride	2
```

### Implementation Pattern

All handlers share the same skeleton:
1. Validate adapter/eid
2. SetFrameEvent
3. GetPipelineState
4. Call specific PipeState method
5. Format as key-value or TSV
6. Return result

No binary data, no temp files, no SWIG type construction.
