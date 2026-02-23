# Tasks: docs-automation

## Test-first tasks

- [ ] Verify `uv run python scripts/gen-stats.py` produces valid JSON with `command_count=53` without importing renderdoc.
- [ ] Verify `python -c "import yaml; yaml.safe_load(open('mkdocs.yml'))"` exits 0.
- [ ] Verify `python -m json.tool release-please-config.json` exits 0.
- [ ] Verify `python -m json.tool .release-please-manifest.json` exits 0.
- [ ] Verify `grep -rE 'uses:.*@v[0-9]' .github/workflows/docs.yml .github/workflows/release-please.yml` returns 0 matches (all SHAs pinned).
- [ ] Verify `node docs-astro/tests/validate.mjs` exits 0 after Astro build.

## Implementation tasks

### T0 — .gitignore

- [ ] **T0-1** Remove `docs/` from `.gitignore` (line 18) — this line blocks mkdocs content from being committed.
- [ ] **T0-2** Remove `scripts/*.py` from `.gitignore` (line 19) — this line blocks `gen-stats.py` from being committed.
- [ ] **T0-3** Add build artifact ignores: append `_site/` and `docs-astro/dist/` to `.gitignore`.

### T1 — Astro migration

- [ ] **T1-1** Extract Astro source from `feat/docs-site` branch into `docs-astro/`:
  ```
  mkdir -p docs-astro
  git -C /home/jim_z/Dev/rdc-cli archive feat/docs-site -- docs/ | \
    tar -x --strip-components=1 -C docs-astro/
  ```
  Confirm `docs-astro/package.json` and `docs-astro/astro.config.mjs` are present after extraction.

- [ ] **T1-2** Create `docs-astro/src/data/stats.json` placeholder (CI overwrites at build time).
  First: `mkdir -p docs-astro/src/data/`.
  ```json
  {
    "command_count": 53,
    "test_count": 1641,
    "coverage": "95.79%",
    "version": "0.2.0",
    "description": "Unix-friendly CLI for RenderDoc .rdc captures"
  }
  ```

- [ ] **T1-3** Update `docs-astro/astro.config.mjs`:
  - Confirm `base: '/rdc-cli/'` is set.
  - Confirm `outDir: 'dist'`.
  - Do not change any other config keys.

- [ ] **T1-4** Update `docs-astro/src/components/Hero.astro`:
  - Add: `import stats from '../data/stats.json';`
  - Replace every hardcoded `33` command-count literal with `{stats.command_count}`.

- [ ] **T1-5** Update `docs-astro/src/components/Commands.astro`:
  - Same import and replacement as T1-4.

- [ ] **T1-6** Update `docs-astro/tests/validate.mjs`:
  - Read `docs-astro/src/data/stats.json` to get actual `command_count`.
  - Replace hardcoded `33` assertion with: assert built HTML contains `String(stats.command_count)`.
  - Do not remove the validation — replace it with a dynamic check.

### T2 — mkdocs setup

- [ ] **T2-1** Create `mkdocs.yml` at repo root:
  - `site_name: rdc-cli`, `repo_url: https://github.com/BANANASJIM/rdc-cli`.
  - Theme: `material` with dark/light palette toggle, `features: [navigation.tabs, content.code.copy, search.highlight]`.
  - Plugins: `search`, `mkdocs-click`.
  - Nav: Home, Installation, Usage, VFS, CLI Reference.
  - `docs_dir: docs`.

- [ ] **T2-2** Create `docs/index.md` — port from current `docs/index.md` and README intro.
- [ ] **T2-3** Create `docs/install.md` — requirements, pip, pipx, AUR, dev install.
- [ ] **T2-4** Create `docs/usage.md` — basic workflow, daemon mode, output formats.
- [ ] **T2-5** Create `docs/vfs.md` — VFS path namespace (`rdc://<session>/<path>`), examples.

- [ ] **T2-6** Create `docs/cli-reference.md` (≤10 lines):
  ```markdown
  # CLI Reference

  ::: mkdocs-click
      :module: rdc.cli
      :command: main
      :prog_name: rdc
      :style: table
      :depth: 1
  ```
  Verify `:command:` matches the Click group name exported from `src/rdc/cli.py`.

### T3 — gen-stats.py

- [ ] **T3-1** Create `scripts/gen-stats.py`:
  - Click introspection: import root CLI group, count non-hidden leaf commands recursively.
  - `--version` flag: overrides version from `pyproject.toml`. Tag injects `v0.3.0`; script strips leading `v`.
    Use `importlib.metadata.version("rdc-cli")` as default (avoids `tomllib`/Python 3.10 compat issue).
  - `--test-count` (int, default 0) and `--coverage` (str, default `""`) flags for CI injection.
  - Output JSON: `command_count`, `version`, `description`, `test_count`, `coverage`.
  - Must NOT import `renderdoc`; guard with `try/except ImportError` if needed.
  - Dependencies: only `click` and `importlib.metadata` (stdlib), both available on Python ≥3.10.

- [ ] **T3-2** Verify: `uv run python scripts/gen-stats.py` outputs valid JSON, `command_count == 53`.

### T4 — release-please

- [ ] **T4-1** Create `release-please-config.json`:
  Note: `release-type: python` natively handles `pyproject.toml` version bumps — no `extra-files` needed.
  ```json
  {
    "packages": {
      ".": {
        "release-type": "python",
        "package-name": "rdc-cli",
        "bump-minor-pre-major": true,
        "changelog-sections": [
          {"type": "feat", "section": "Features"},
          {"type": "fix", "section": "Bug Fixes"},
          {"type": "perf", "section": "Performance"},
          {"type": "refactor", "section": "Refactoring", "hidden": true},
          {"type": "chore", "section": "Miscellaneous", "hidden": true}
        ]
      }
    }
  }
  ```

- [ ] **T4-2** Create `.release-please-manifest.json`: `{".": "0.2.0"}`.

- [ ] **T4-3** Fetch pinned SHA for `googleapis/release-please-action@v4`:
  ```bash
  gh api /repos/googleapis/release-please-action/git/refs/tags/v4 --jq '.object.sha'
  # if type == "tag", dereference to commit SHA:
  gh api /repos/googleapis/release-please-action/git/tags/<sha> --jq '.object.sha'
  ```

- [ ] **T4-4** Create `.github/workflows/release-please.yml`:
  - Trigger: `push: branches: [master]`.
  - Permissions: `contents: write`, `pull-requests: write`.
  - `googleapis/release-please-action` at pinned SHA from T4-3 with `# v4` comment.
  - No mutable `@vN` tags.

### T5 — docs.yml workflow

- [ ] **T5-1** Fetch pinned SHAs for actions not in `ci.yml`:
  ```bash
  # For each, resolve tag → commit SHA (dereference if type=="tag"):
  gh api /repos/actions/setup-node/git/refs/tags/v4 --jq '.object.sha'
  gh api /repos/actions/upload-pages-artifact/git/refs/tags/v3 --jq '.object.sha'
  gh api /repos/actions/deploy-pages/git/refs/tags/v4 --jq '.object.sha'
  ```
  Reuse from `ci.yml` (no re-fetch):
  - `actions/checkout` → `11bd71901bbe5b1630ceea73d27597364c9af683 # v4`
  - `astral-sh/setup-uv` → `eac588ad8def6316056a12d4907a9d4d84ff7a3b # v7.3.0`

- [ ] **T5-2** Create `.github/workflows/docs.yml`:
  - Triggers: `push: tags: ['v*']` and `workflow_dispatch`.
  - Permissions: `contents: write`, `pages: write`, `id-token: write`.
  - `concurrency: {group: pages, cancel-in-progress: false}`.
  - Environment: `name: github-pages`.
  - Steps (single job `build-and-deploy`):
    1. `actions/checkout` (pinned SHA).
    2. Extract version: `echo "version=${GITHUB_REF_NAME#v}" >> "$GITHUB_OUTPUT"`.
    3. `astral-sh/setup-uv` (pinned) + `uv sync`.
    4. `uv run python scripts/gen-stats.py --version <tag>` → `docs-astro/src/data/stats.json`.
    5. `uv run --with mkdocs-material --with mkdocs-click mkdocs build -d _site`.
    6. `actions/setup-node` (pinned) + `cd docs-astro && npm ci && npm run build`.
    7. `cp -r _site/ docs-astro/dist/docs/`.
    8. Generate badge JSONs into `docs-astro/dist/badges/`.
    9. `actions/upload-pages-artifact` (pinned) with `path: docs-astro/dist`.
    10. `actions/deploy-pages` (pinned, `id: deployment`).
    11. `gh repo edit --description "... ${CMD} commands ..." --homepage "..."`.
  - No mutable `@vN` tags anywhere.

### T6 — README badges

- [ ] **T6-1** Add shields.io endpoint badges to `README.md`:
  ```markdown
  [![Commands](https://img.shields.io/endpoint?url=https://bananasjim.github.io/rdc-cli/badges/commands.json)](https://bananasjim.github.io/rdc-cli/)
  [![Tests](https://img.shields.io/endpoint?url=https://bananasjim.github.io/rdc-cli/badges/tests.json)](https://bananasjim.github.io/rdc-cli/)
  [![Coverage](https://img.shields.io/endpoint?url=https://bananasjim.github.io/rdc-cli/badges/coverage.json)](https://bananasjim.github.io/rdc-cli/)
  ```

## Validation checklist (run after all tasks complete)

- [ ] `python -c "import yaml; yaml.safe_load(open('mkdocs.yml'))"` exits 0.
- [ ] `python -m json.tool release-please-config.json` exits 0.
- [ ] `python -m json.tool .release-please-manifest.json` exits 0.
- [ ] `uv run python scripts/gen-stats.py` outputs valid JSON with `command_count` == 53.
- [ ] `grep -rE 'uses:.*@v[0-9]' .github/workflows/docs.yml .github/workflows/release-please.yml` returns 0 matches.
- [ ] `pixi run lint && pixi run test` exits 0 (confirm no runtime changes broken).
