# Test Plan: docs-polish

**Date:** 2026-02-23

---

## Verification Steps

### 1. Build Verification

```bash
cd docs-astro && npm run build
```

- Must complete without errors
- All pages generated in `dist/`

### 2. Page Completeness

| Check | Expected |
|-------|----------|
| `design.astro` exists | New page renders with 7 sections |
| Commands page sections | 12 sections (existing 10 + Target Control + Capture Metadata) |
| Commands total | 60 commands documented |
| Examples count | ~22 use cases (8 existing + 14 new) |
| 🚧 badges | Visible on Phase 5B commands and examples |

### 3. Navigation

| Link | Target |
|------|--------|
| Sidebar "Design" | `/docs/design/` |
| Index "Design" link | `/docs/design/` |
| All existing sidebar links | Still work correctly |

### 4. Content Accuracy

- Design page rationale matches Obsidian decision records (D-001 through D-025)
- Phase 5B commands match `openspec/changes/2026-02-23-phase5b-capture-unified/proposal.md`
- Command syntax matches `rdc --help` output
- `stats.json` values updated (command_count: 60)

### 5. Visual Check

- Dark mode renders correctly
- Light mode renders correctly
- Mobile responsive layout works
- Code blocks properly formatted
