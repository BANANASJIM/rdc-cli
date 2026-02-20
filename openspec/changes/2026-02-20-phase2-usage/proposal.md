# Proposal: phase2-usage

## Summary

Add `rdc usage <resource_id>` command and `/resources/<id>/usage` VFS leaf
to expose per-resource cross-reference data via `GetUsage()`. Also add
`rdc usage --all` for a full-frame resource×event usage matrix.

## Motivation

Debugging GPU issues requires understanding resource lifecycles: which events
read, write, clear, or barrier a given texture/buffer. Currently rdc-cli can
list resources (`rdc resources`) and show detail (`rdc resource <id>`), but
cannot answer "who touches this resource?"

RenderDoc's `GetUsage(resourceId)` returns exactly this: a list of
`EventUsage{eventId, usage}` with 46 distinct `ResourceUsage` enum values
(VertexBuffer, PS_Constants, ColorTarget, CopySrc, etc.).

`rdc usage` exposes this as pipeable TSV, and `--all` provides the full matrix
an agent can ingest in a single call to understand the entire frame's
resource flow.

## Design

### Daemon handler: `usage`

**Params:**
- `id` (int, required) — resource ID
- `resolve_names` (bool, default true) — include resource name in response

**Response:**
```json
{
  "id": 97,
  "name": "2D Image 97",
  "entries": [
    {"eid": 6, "usage": "Clear"},
    {"eid": 11, "usage": "ColorTarget"},
    {"eid": 12, "usage": "CopySrc"}
  ]
}
```

### Daemon handler: `usage_all`

**Params:**
- `type` (string, optional) — filter by resource type (Texture/Buffer/...)
- `usage` (string, optional) — filter by usage type (ColorTarget/VertexBuffer/...)

**Response:**
```json
{
  "rows": [
    {"id": 97, "name": "2D Image 97", "eid": 11, "usage": "ColorTarget"},
    {"id": 105, "name": "Buffer 105", "eid": 11, "usage": "VS_Constants"}
  ],
  "total": 2
}
```

### VFS

```
/resources/<id>/usage    → leaf, handler "usage"
```

Add `usage` to each resource's children in tree_cache.

### CLI: `rdc usage`

```
rdc usage <resource_id>          # single resource
rdc usage --all                  # full matrix
rdc usage --all --type Texture   # filter by type
rdc usage --all --usage ColorTarget  # filter by usage
rdc usage <id> --json            # JSON output
```

**Single resource output (TSV):**
```
EID     USAGE
6       Clear
11      ColorTarget
12      CopySrc
```

**`--all` output (TSV):**
```
ID      NAME                    EID     USAGE
97      2D Image 97             11      ColorTarget
105     Buffer 105              11      VS_Constants
276     2D Depth Attachment     6       Clear
276     2D Depth Attachment     11      DepthStencilTarget
```

### VFS extractor

`rdc cat /resources/<id>/usage` outputs the same TSV as `rdc usage <id>`.

### Error handling

- Resource not found → `-32001`
- No replay loaded → `-32002`
- Resource with zero usage entries → empty TSV body (header only), not error

## Scope

**In scope:**
- `usage` daemon handler (single resource)
- `usage_all` daemon handler (full matrix)
- VFS route `/resources/<id>/usage` + tree_cache update
- `rdc usage` CLI command with `--all`, `--type`, `--usage`, `--json`
- TSV formatter for usage output
- Mock `GetUsage` + `EventUsage` in mock_renderdoc

**Out of scope:**
- Pass dependency graph (derivable from usage data, future `rdc passes --deps`)
- Usage-based anomaly detection (e.g. "unused resources")
- Resource timeline visualization
