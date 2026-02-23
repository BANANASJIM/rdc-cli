# Proposal: docs-automation

## Goal

Add a production-quality documentation site and release automation to rdc-cli. The landing
page (Astro, GPU theme) lives at `/rdc-cli/` and a full CLI reference (mkdocs-material +
mkdocs-click) lives at `/rdc-cli/docs/`. Both are built from master on every `v*` tag push
and deployed to `gh-pages` as pure static artifacts. release-please drives version bumps and
changelog generation via an automated Release PR workflow.

## Scope

**In scope:**
- Remove `docs/` and `scripts/*.py` from `.gitignore` (currently blocks committing mkdocs content and gen-stats.py)
- Add `_site/`, `docs-astro/dist/` to `.gitignore` (build artifacts)
- Migrate Astro source from `feat/docs-site:docs/` → `docs-astro/` in master
- Add `mkdocs.yml` and reorganise `docs/` as mkdocs content (replaces existing simple markdown)
- Add `scripts/gen-stats.py` — Click introspection → `stats.json` (command count, version, description)
- Expose badge JSONs as shields.io endpoint JSON served from gh-pages
- Add `.github/workflows/docs.yml` — unified build + deploy (trigger: `v*` tag push)
- Add `.github/workflows/release-please.yml`, `release-please-config.json`, `.release-please-manifest.json`
- Update repo description and homepage via `gh repo edit` in `docs.yml`
- Add shields.io endpoint badge lines to `README.md`

**Out of scope:**
- Modifications to `ci.yml` or `commitlint.yml`
- Runtime code changes to rdc-cli itself
- Test coverage or test suite changes
- Custom mkdocs plugins beyond mkdocs-material and mkdocs-click

## Architecture

Hybrid static site — two engines, one gh-pages branch, zero runtime server.

| URL path | Engine | Content |
|---|---|---|
| `/rdc-cli/` | Astro (Node build) | Landing: hero animation, terminal demo, feature cards |
| `/rdc-cli/docs/` | mkdocs-material | CLI reference, install, usage, VFS guide, search |

`gh-pages` contains only build artifacts — no source code. Master contains all sources.
Astro builds to `docs-astro/dist/`; mkdocs builds to `_site/`; CI copies `_site/` into
`docs-astro/dist/docs/`, then deploys the merged tree as a single pages artifact.

`gen-stats.py` introspects the Click command tree at build time and writes `stats.json`.
That file is embedded into the Astro build (imported in Hero.astro) and also written to
`docs-astro/dist/badges/` as shields.io endpoint JSONs.

## CI Pipeline

Trigger: `v*` tag push (created by release-please after Release PR is merged).

Steps in `docs.yml`:
1. Checkout at tag ref.
2. Extract version from tag (`${GITHUB_REF_NAME#v}`).
3. `uv sync` — install Python deps.
4. `python scripts/gen-stats.py --version <tag>` → `docs-astro/src/data/stats.json`.
5. `mkdocs build -d _site` — mkdocs-material + mkdocs-click → CLI reference HTML.
6. `npm ci && npm run build` inside `docs-astro/` — Astro build to `docs-astro/dist/`.
7. `cp -r _site/* docs-astro/dist/docs/` — merge mkdocs output into Astro output.
8. Generate badge endpoint JSONs into `docs-astro/dist/badges/`.
9. Deploy `docs-astro/dist/` to GitHub Pages via `actions/deploy-pages`.
10. `gh repo edit` — update description and homepage with live stats.

## Release Automation

release-please watches squash-merge commits on master for Conventional Commit prefixes.
On each qualifying merge it opens or updates a Release PR that bumps `pyproject.toml`
version, writes `CHANGELOG.md`, and updates `.release-please-manifest.json`. Merging
the Release PR triggers a `v*` tag push, which triggers `docs.yml` and the existing
`ci.yml` release job (PyPI publish).

Config:
- `release-please-config.json` — `release-type: python`, `package-name: rdc-cli`,
  changelog sections matching project commit types. (`release-type: python` natively handles
  `pyproject.toml` version bumps — no `extra-files` needed.)
- `.release-please-manifest.json` — current version `0.2.0`.

## Why release-please

| Factor | release-please | python-semantic-release |
|--------|---------------|------------------------|
| Squash-merge support | Native (reads PR title) | Needs extra config |
| Review gate | Release PR | Direct push |
| Config complexity | Minimal (2 JSON + 1 workflow) | Medium |
| pyproject.toml bump | Native (python release type) | Native |

release-please's Release PR is the key advantage: version bump is a normal PR that Jim
reviews and merges, keeping humans in the release loop.

## Non-goals

- No changes to application source code or CLI behaviour.
- No new tests; existing `pixi run test` suite unchanged.
- No server-side rendering or dynamic backend.
- No multi-version docs (single latest version only).
