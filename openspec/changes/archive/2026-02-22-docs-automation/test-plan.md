# Test Plan: docs-automation

## Scope

- In scope: `.gitignore`, `scripts/gen-stats.py`, `mkdocs.yml`, `docs/` content,
  `docs-astro/` source tree, `release-please-config.json`, `.release-please-manifest.json`,
  `.github/workflows/release-please.yml`, `.github/workflows/docs.yml`.
- Out of scope: runtime `src/` behaviour, unit tests, GPU tests.

## Test Matrix

- Unit: `gen-stats.py` invoked as a standalone script (no renderdoc required).
- Validation: static file inspection, YAML/JSON parse checks, local build smoke tests.
- CI: workflow YAML syntax validation.

## Cases

### .gitignore

- `.gitignore` does NOT contain `docs/` (removed to allow mkdocs content to be committed).
- `.gitignore` does NOT contain `scripts/*.py` (removed to allow gen-stats.py to be committed).
- `.gitignore` contains `_site/` (build artifact, newly added).
- `.gitignore` contains `docs-astro/dist/` (build artifact, newly added).

### gen-stats.py

- Script imports succeed without renderdoc: `uv run python scripts/gen-stats.py` exits 0
  in an env where `renderdoc` is not on `PYTHONPATH`.
- Output is valid JSON: `uv run python scripts/gen-stats.py | python -m json.tool` exits 0.
- `command_count` equals 53: matches recursive non-hidden leaf command count.
- `--version v0.3.0` strips leading `v`: JSON field `version` == `"0.3.0"`.
- JSON contains all required keys: `command_count`, `version`, `description`, `test_count`, `coverage`.

### mkdocs.yml

- Valid YAML: `python -c "import yaml; yaml.safe_load(open('mkdocs.yml'))"` exits 0.
- Contains `mkdocs-click` in the plugins list.
- `docs/cli-reference.md` contains the mkdocs-click directive (`::: mkdocs-click`).
- Smoke build: `mkdocs build -d /tmp/mkdocs-test` exits 0.

### Astro source (docs-astro/)

- `docs-astro/package.json` exists and contains `"astro"` as a dependency key.
- `docs-astro/astro.config.mjs` contains `base: '/rdc-cli/'`.
- `docs-astro/src/data/stats.json` exists and is valid JSON with key `command_count`.
- `docs-astro/src/components/Hero.astro` does NOT contain the literal `33 commands`.
- `docs-astro/tests/validate.mjs` does NOT contain a hardcoded assertion on `33`.

### release-please

- `release-please-config.json` is valid JSON; `release-type` == `"python"`.
- `.release-please-manifest.json` is valid JSON; key `"."` == `"0.2.0"`.
- `.github/workflows/release-please.yml` is valid YAML.
- `release-please.yml` `on:` triggers on `push: branches: [master]`.

### docs.yml workflow

- Valid YAML: `python -c "import yaml; yaml.safe_load(open('.github/workflows/docs.yml'))"` exits 0.
- `on:` contains `push: tags: ['v*']` and `workflow_dispatch`.
- Contains a step invoking `scripts/gen-stats.py`.
- Contains a step invoking `mkdocs build`.
- Contains a step invoking `npm run build` (Astro).
- Contains a step copying `_site/` into `dist/docs/`.
- Contains a step writing badge JSON artifacts.
- Contains an `actions/deploy-pages` step.
- Contains a `gh repo edit` step.
- Every `uses:` line has a 40-char hex SHA — `grep 'uses:.*@v[0-9]'` returns 0 matches.
- `permissions:` includes `contents: write`, `pages: write`, `id-token: write`.
