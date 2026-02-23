# Tasks: docs-polish

**Date:** 2026-02-23

---

## Task Breakdown

### T1: Create design.astro
- [ ] Create `docs-astro/src/pages/docs/design.astro`
- [ ] Write 7 sections sourced from Obsidian decision records
- [ ] Follow existing page styling (Docs layout, prose classes)

### T2: Update commands.astro
- [ ] Add Target Control section (attach, capture-trigger, capture-list, capture-copy) with 🚧 badge
- [ ] Add Capture Metadata section (thumbnail, gpus, sections, section) with 🚧 badge
- [ ] Update `capture` command entry with new Python API options
- [ ] Verify all 60 commands are documented

### T3: Expand examples.astro
- [ ] Add ~14 new use case sections
- [ ] Mark Phase 5B examples with 🚧 badge
- [ ] Ensure code examples are accurate and runnable

### T4: Update navigation and metadata
- [ ] Add "Design" to sidebar in `layouts/Docs.astro`
- [ ] Add "Design" link to sections list in `pages/docs/index.astro`
- [ ] Update `data/stats.json` (command_count, test_count, version)

### T5: Build and verify
- [ ] `npm run build` passes
- [ ] Visual check of all modified/new pages
