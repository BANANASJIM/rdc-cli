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
| Commands total | 60+ commands documented |
| Examples count | ~22 use cases |

### 3. Install Documentation

| Check | Expected |
|-------|----------|
| README Install section | Before Quickstart, shows PyPI + build-renderdoc.sh + both AUR variants |
| `install.astro` | Build script section, both AUR packages, `~/.local/renderdoc` discovery |
| Landing page Install block | PyPI with curl, AUR with stable+git |

### 4. Terminal Replay

| Check | Expected |
|-------|----------|
| `python scripts/gen-replay.py` | Runs without error, outputs valid JSON |
| `replay.json` | 7 playlists, each with open → commands → close |
| Hero terminal animation | Types commands, shows output, rotates playlists |
| No typed.js in bundle | Removed from package.json, no import errors |

### 5. Navigation

| Link | Target |
|------|--------|
| Sidebar "Design" | `/docs/design/` |
| Index "Design" link | `/docs/design/` |
| All existing sidebar links | Still work correctly |

### 6. Visual Check

- Dark mode renders correctly
- Light mode renders correctly
- Terminal replay visible on mobile (responsive)
- Code blocks properly formatted
