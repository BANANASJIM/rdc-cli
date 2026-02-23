# Proposal: docs-polish

**Date:** 2026-02-23
**Phase:** Docs
**Status:** Draft

---

## Problem Statement

The Astro docs site (GitHub Pages) has three significant gaps:

1. **Examples page incomplete** — Only 8 use cases covering ~15 of 60 commands. Major workflows (capture, target control, render pass analysis, pixel investigation, buffer decode, performance profiling) are undocumented.

2. **Commands page outdated** — Missing 8 Phase 5B commands (`attach`, `capture-trigger`, `capture-list`, `capture-copy`, `thumbnail`, `gpus`, `sections`, `section`). The `capture` command docs don't reflect the Python API rewrite with new options. `stats.json` reports 53 commands; actual count is 60.

3. **No design rationale page** — Users and contributors cannot understand *why* rdc-cli uses a daemon, TSV-first output, VFS paths, or CI assertions. The Obsidian vault has 25 decision records (D-001 through D-025) that are not publicly accessible.

---

## Proposed Solution

### 1. New page: "Why This Design" (`design.astro`)

A design rationale page sourced from Obsidian decision records covering:
- The Problem (RenderDoc is GUI-only)
- Why a Daemon (D-002: OpenCapture 30-60s, JSON-RPC over TCP)
- Why TSV by Default (D-003: pipe to grep/awk/sort/diff)
- Why VFS Paths (D-001, D-016: two-layer architecture, not FUSE)
- Why CI Assertions (D-011: 5 purpose-built + Unix composability)
- Why AI-Agent Friendly (D-009: rdc script escape hatch)
- Key Trade-offs (single-threaded daemon, GLSL-only shader edit)

### 2. Update commands page

- Add **Target Control** section (Phase 5B, marked 🚧): `attach`, `capture-trigger`, `capture-list`, `capture-copy`
- Add **Capture Metadata** section (Phase 5B, marked 🚧): `thumbnail`, `gpus`, `sections`, `section`
- Update `capture` command with new Python API options
- Update `stats.json` to reflect 60 commands

### 3. Expand examples page (~14 new use cases)

Add workflow recipes for: frame capture, end-to-end CI pipeline, target control, multi-session comparison, render pass analysis, pixel investigation ladder, buffer decode, rdc script, performance profiling, resource hunting, shader search, validation debugging, texture analysis, VFS deep exploration.

### 4. Update navigation

- Add "Design" entry to sidebar in `Docs.astro`
- Add "Design" link to sections list in `index.astro`

---

## Non-Goals

- No changes to CLI code or daemon handlers
- No changes to Obsidian vault files
- No automated doc generation (manual curation for quality)

---

## Acceptance Criteria

1. `cd docs-astro && npm run build` succeeds without errors
2. All 60 commands documented on commands page
3. Examples page has ~22 total use cases covering all major workflows
4. Design page accurately reflects Obsidian decision records
5. Navigation links work correctly across all pages
