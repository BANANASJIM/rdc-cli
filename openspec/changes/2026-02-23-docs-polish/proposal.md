# Proposal: docs-polish

**Date:** 2026-02-23
**Phase:** Docs
**Status:** In Progress

---

## Problem Statement

The Astro docs site (GitHub Pages) has several gaps:

1. **Examples page incomplete** — Only 8 use cases covering ~15 of 60 commands. Major workflows (capture, target control, render pass analysis, pixel investigation, buffer decode, performance profiling) are undocumented.

2. **Commands page outdated** — Missing 8 Phase 5B commands (`attach`, `capture-trigger`, `capture-list`, `capture-copy`, `thumbnail`, `gpus`, `sections`, `section`). The `capture` command docs don't reflect the Python API rewrite with new options.

3. **No design rationale page** — Users and contributors cannot understand *why* rdc-cli uses a daemon, TSV-first output, VFS paths, or CI assertions.

4. **Install docs incomplete** — No mention of `build-renderdoc.sh` convenience script or both AUR package variants (`rdc-cli` stable vs `rdc-cli-git`).

5. **README structure** — Install section buried after feature description; should be more prominent.

6. **No live terminal demo** — Hero section only types commands without showing output. Visitors can't see what rdc-cli actually produces.

---

## Proposed Solution

### 1. New page: "Why This Design" (`design.astro`) — DONE

Design rationale page sourced from Obsidian decision records.

### 2. Update commands page — DONE

Add Target Control and Capture Metadata sections for Phase 5B.

### 3. Expand examples page (~14 new use cases) — DONE

Add workflow recipes covering: output formats, quick metrics, compute shaders, advanced assertions, Vulkan features, capture, CI, target control, multi-session, render pass, pixel investigation, buffer decode, rdc script, profiling, resource hunting, shader search, validation, texture analysis, VFS exploration.

### 4. Update install documentation — DONE

- README: move Install before Quickstart, show both AUR packages, highlight `build-renderdoc.sh`
- `install.astro`: add build script section, both AUR variants, `~/.local/renderdoc` discovery
- `Install.astro` (landing page): show `build-renderdoc.sh` curl, both AUR packages

### 5. Terminal replay animation — IN PROGRESS

Replace Typed.js single-command-line animation with data-driven terminal session replay:

- **`scripts/gen-replay.py`** — runs real `rdc` commands against `tests/fixtures/hello_triangle.rdc`, captures output, generates `docs-astro/src/data/replay.json`
- **Playlist rotation** — 7 themed playlists (inspection, shaders, VFS, unix-pipes, state/pixel, events/stats, CI/JSON) that rotate on each loop
- **`Hero.astro`** — custom animation: types commands char-by-char, reveals output line-by-line, auto-scrolls, dynamic terminal height
- **`pixi.toml`** — `gen-replay` / `check-replay` tasks
- **Typed.js removed** from dependencies (replaced by custom ~80-line script)

### 6. Update navigation — DONE

Add "Design" to sidebar and index page.

---

## Non-Goals

- No changes to CLI code or daemon handlers
- No changes to Obsidian vault files

---

## Acceptance Criteria

1. `cd docs-astro && npm run build` succeeds without errors
2. All 60+ commands documented on commands page
3. Examples page has ~22 total use cases covering all major workflows
4. Design page accurately reflects Obsidian decision records
5. Navigation links work correctly across all pages
6. Install docs show both AUR variants and build-renderdoc.sh
7. Terminal replay plays 7 rotating themed playlists with real command output
8. `pixi run gen-replay` produces valid `replay.json`
