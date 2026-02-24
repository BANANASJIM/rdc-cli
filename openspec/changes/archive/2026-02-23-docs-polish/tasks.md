# Tasks: docs-polish

**Date:** 2026-02-23

---

## Task Breakdown

### T1: Create design.astro — DONE
- [x] Create `docs-astro/src/pages/docs/design.astro`
- [x] Write 7 sections sourced from Obsidian decision records
- [x] Follow existing page styling (Docs layout, prose classes)

### T2: Update commands.astro — DONE
- [x] Add Target Control section (attach, capture-trigger, capture-list, capture-copy)
- [x] Add Capture Metadata section (thumbnail, gpus, sections, section)
- [x] Update `capture` command entry with new Python API options
- [x] Verify all 60 commands are documented

### T3: Expand examples.astro — DONE
- [x] Add ~14 new use case sections
- [x] Ensure code examples are accurate

### T4: Update navigation and metadata — DONE
- [x] Add "Design" to sidebar in `layouts/Docs.astro`
- [x] Add "Design" link to sections list in `pages/docs/index.astro`

### T5: Update install documentation — DONE
- [x] README: move Install before Quickstart, both AUR packages, build-renderdoc.sh
- [x] `install.astro`: add build script section, both AUR variants
- [x] `Install.astro` (landing page): update PyPI and AUR blocks

### T6: Terminal replay animation — IN PROGRESS
- [x] Create `scripts/gen-replay.py` (runs real rdc commands, outputs playlist JSON)
- [x] Generate `docs-astro/src/data/replay.json` with 7 themed playlists
- [x] Replace Typed.js in `Hero.astro` with custom replay animation
- [x] Remove typed.js dependency from package.json
- [x] Add `gen-replay` / `check-replay` tasks to pixi.toml
- [x] Add `.replay-cursor` blink CSS
- [ ] Code review
- [ ] Visual verification by Jim

### T7: Build and verify
- [x] `npm run build` passes
- [ ] Visual check of all modified/new pages
- [ ] Push and create/update PR
