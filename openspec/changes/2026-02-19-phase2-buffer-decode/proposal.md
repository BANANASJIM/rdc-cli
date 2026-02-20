# OpenSpec #2: phase2-buffer-decode

## Summary

Add VFS handlers and CLI commands for decoded buffer data:
- `/draws/<eid>/cbuffer/<set>/<binding>` — constant buffer variable contents (TSV)
- `/draws/<eid>/vbuffer` — vertex buffer data decoded via IA layout (TSV)
- `/draws/<eid>/ibuffer` — index buffer data (TSV)

All output is text (TSV), no binary infrastructure dependency.

## Motivation

Raw buffer bytes (`/buffers/<id>/data`) are available from OpenSpec #1, but interpreting them
requires format knowledge. These handlers decode buffer data into human/agent-readable TSV:
- cbuffer: structured variable names + values (GetCBufferVariableContents)
- vbuffer: vertex attributes decoded via Input Assembler layout
- ibuffer: uint16/uint32 index values

## Design

### VFS Routes

| Path | Kind | Handler | API |
|------|------|---------|-----|
| `/draws/<eid>/cbuffer` | dir | — | list constant blocks |
| `/draws/<eid>/cbuffer/<set>/<binding>` | leaf | cbuffer_decode | GetCBufferVariableContents |
| `/draws/<eid>/vbuffer` | leaf | vbuffer_decode | GetVBuffers + GetBufferData + IA layout |
| `/draws/<eid>/ibuffer` | leaf | ibuffer_decode | GetIBuffer + GetBufferData |

### Daemon Handlers

**cbuffer_decode**: SetFrameEvent → GetPipelineState → GetShaderReflection → GetConstantBlock →
GetCBufferVariableContents(pipeline, shader, stage, entry, idx, resource, offset, size) →
recursive ShaderVariable tree → TSV (name, type, value)

**vbuffer_decode**: SetFrameEvent → GetPipelineState → GetVBuffers + GetVertexInputs →
GetBufferData for each bound VBuffer → decode per-vertex attributes via format → TSV

**ibuffer_decode**: SetFrameEvent → GetPipelineState → GetIBuffer →
GetBufferData → decode uint16/uint32 indices → TSV

### CLI Commands

- `rdc cbuffer <eid> [--set N] [--binding N] [--stage ps]` → cat `/draws/<eid>/cbuffer/<set>/<binding>`
- `rdc vbuffer <eid>` → cat `/draws/<eid>/vbuffer`
- `rdc ibuffer <eid>` → cat `/draws/<eid>/ibuffer`

### Output Format

TSV for all three, pipeable to grep/awk/sort:

```
# cbuffer: draws/142/cbuffer/0/0 (stage=ps)
name	type	value
mvp	mat4	[[1.0, 0.0, ...], ...]
lightDir	vec3	[0.5, 0.7, 0.0]

# vbuffer: draws/142/vbuffer
idx	POSITION.x	POSITION.y	POSITION.z	TEXCOORD.x	TEXCOORD.y
0	-1.0	-1.0	0.0	0.0	0.0
1	1.0	-1.0	0.0	1.0	0.0

# ibuffer: draws/142/ibuffer
idx	value
0	0
1	1
2	2
```
