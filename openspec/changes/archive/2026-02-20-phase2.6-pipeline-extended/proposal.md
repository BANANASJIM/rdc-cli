# Proposal: phase2.6-pipeline-extended

## Summary

Add 4 new pipeline state sections as VFS leaves under `/draws/<eid>/pipeline/`:
`push-constants`, `rasterizer`, `depth-stencil`, `msaa`.

## Motivation

Phase 2 established the pipeline VFS namespace. Phase 2.6 extends it with the
remaining common Vulkan state blocks that renderers typically inspect for
debugging rasterization and depth/stencil behavior.

## Design

Each section is a leaf node resolved by a new route in `router.py` and handled
in `daemon_server.py`. Data is read from `get_pipeline_state()` attributes:

| Section         | Handler               | Source attribute      |
|-----------------|-----------------------|-----------------------|
| push-constants  | pipe_push_constants   | GetShaderReflection   |
| rasterizer      | pipe_rasterizer       | pipe_state.rasterizer |
| depth-stencil   | pipe_depth_stencil    | pipe_state.depthStencil |
| msaa            | pipe_msaa             | pipe_state.multisample |

### push-constants
Iterates active shader stages. For each stage with a shader bound, reads
`pushConstantRangeByteOffset` and `pushConstantRangeByteSize` from shader
reflection. Returns list of `{stage, offset, size}`.

### rasterizer
Reads `fillMode`, `cullMode`, `frontCCW`, `depthBiasEnable`,
`depthBiasConstantFactor`, `depthBiasClamp`, `depthBiasSlopeFactor`,
`lineWidth` from `pipe_state.rasterizer`. Enum values serialized via `.name`.

### depth-stencil
Reads `depthTestEnable`, `depthWriteEnable`, `depthFunction`,
`depthBoundsEnable`, `minDepthBounds`, `maxDepthBounds`, `stencilTestEnable`
from `pipe_state.depthStencil`. Enum values serialized via `.name`.

### msaa
Reads `rasterSamples`, `sampleShadingEnable`, `minSampleShading`,
`sampleMask` from `pipe_state.multisample`.

## Non-Goals

- No binary/image output
- No write operations
- No D3D11/D3D12/GL-specific path (getattr-safe, returns partial data)
