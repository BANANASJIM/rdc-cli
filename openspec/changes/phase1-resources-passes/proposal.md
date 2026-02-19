# Change Proposal: phase1-resources-passes

## Why
Phase 1 Week 6 roadmap requires visibility into GPU resources (textures, buffers) and the high-level Render Pass structure. This allows users (and agents) to explore the asset inventory and the logical flow of the frame.

## What Changes
- Add CLI commands:
  - `rdc resources` — List all resources in the capture.
  - `rdc resource <id>` — Show detailed properties of a specific resource.
  - `rdc passes` — Show the frame structure (Render Passes / Marker regions).
  - `rdc pass <index>` — Show details of a specific pass (optional/stretch).
- Add Daemon JSON-RPC handlers: `resources`, `resource`, `passes`.
- Extend `query_service` to extract resource lists and pass hierarchy from `ReplayController`.
- Support `--json` output for all new commands.

## Scope
- **Resources**: ID, Name, Type, Width, Height, Depth, Format.
- **Passes**: Tree view of markers/passes with draw counts.
- **Out of Scope**: Content dumping (saving texture data to disk is Phase 2).

## Compatibility
- Requires active session (`rdc open`).
- No breaking changes.
