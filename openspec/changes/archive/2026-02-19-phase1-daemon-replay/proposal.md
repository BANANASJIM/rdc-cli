# Proposal: phase1-daemon-replay

## Goal

Upgrade the daemon from a stateless skeleton to a real RenderDoc replay host.
The daemon must load the `renderdoc` module, open a capture file via
`OpenCaptureFile` / `OpenCapture`, hold a live `ReplayController`, and expose
it to JSON-RPC method handlers.

This is the **shared foundation** for every Phase 1 command.

## Scope

- Import `renderdoc` module inside the daemon process (using adapter layer).
- Call `InitialiseReplay` → `OpenCaptureFile` → `OpenCapture` at startup.
- Hold `ReplayController` + `CaptureFile` + `StructuredFile` in `DaemonState`.
- Implement proper `SetFrameEvent` with incremental-replay caching.
- Wire `goto` method to real `SetFrameEvent`.
- Update `status` method to return live capture metadata (API, GPU, event count).
- Implement `shutdown` to call `controller.Shutdown()` + `cap.Shutdown()` then
  `sys.exit(0)` (never call `ShutdownReplay`—let OS reclaim).
- Add `formatters/` package with `tsv.py` for TSV output helpers.
- Add global output options infrastructure: `--no-header`, `--json`, `--jsonl`,
  `--quiet`, `--columns`, `--sort`, `--limit`, `--range`.

## Non-goals

- Specific query commands (draws, info, etc.)—those belong to parallel features.
- Multi-session support.
- Remote replay.
- asyncio migration (keep synchronous for now; single-threaded is sufficient
  since the daemon handles one request at a time).

## Key design references (Obsidian)

- 设计/交互模式 — daemon architecture, lifecycle, JSON-RPC protocol
- 设计/设计原则 — output philosophy, global options, exit codes
- 工程/技术栈 — renderdoc module discovery, adapter layer, project structure
- 设计/API 实现映射 — core lifecycle (`InitialiseReplay` → `OpenCapture`)
