# Contributing to rdc-cli

Thanks for your interest in rdc-cli! Whether it's a bug report, feature idea, or code contribution — all are welcome.

## Reporting issues

Found a bug or have a feature request? Please [open an issue](https://github.com/BANANASJIM/rdc-cli/issues).

A good issue includes:

- **Bug reports**: what you did, what you expected, what happened instead. Include `rdc doctor` output and your OS/Python version. A minimal `.rdc` capture to reproduce is ideal but not required.
- **Feature requests**: describe the use case (what problem are you solving?), not just the solution. If you have thoughts on the CLI interface, include an example invocation.
- **Questions**: if you're unsure whether something is a bug or a usage question, open an issue anyway — we'll sort it out.

## Pull requests

### Before you start

- For non-trivial changes, **open an issue first** to discuss the approach. This avoids wasted effort if the design needs adjustment.
- Small fixes (typos, one-liner bug fixes) can go straight to a PR.

### PR description format

A good PR description helps reviewers understand your change quickly:

```
## What

One-sentence summary of what this PR does.

## Why

The problem or motivation. Link to the issue if there is one (Fixes #123).

## How

Brief description of the approach. Call out any non-obvious decisions
or trade-offs.

## Test plan

How you verified the change works:
- [ ] Added/updated unit tests
- [ ] Ran `pixi run check` (lint + typecheck + tests)
- [ ] Manual testing with a real .rdc capture (if applicable)
```

### Commit messages

We use [Conventional Commits](https://www.conventionalcommits.org/), enforced by commitlint in CI:

```
feat(cli): add frobnicate command
fix(daemon): handle missing texture gracefully
docs(readme): update install instructions
```

Common scopes: `cli`, `daemon`, `vfs`, `ci`, `build`, `docs`.

### Workflow

1. Fork and clone the repo
2. Set up the dev environment:
   ```bash
   pixi install && pixi run sync
   ```
3. Create a feature branch: `git switch -c feat/my-feature`
4. Make your changes, ensure `pixi run check` passes
5. Push and open a PR against `master`

PRs are squash-merged after review.

### Code style

Enforced by CI — just follow the tooling:

- **Linter/formatter**: ruff (`ruff check --fix` / `ruff format` to auto-fix)
- **Type checker**: mypy strict mode
- **Line length**: 100 chars
- **Output**: `click.echo()` or `logging`, never `print()`
- **Paths**: `pathlib.Path`, not `os.path`

### CI checks on PRs

- Lint (ruff) + type check (mypy)
- Unit tests — Python 3.10 / 3.12 / 3.14 on Linux + Windows
- Commitlint — conventional commit format
- Dependency audit (pip-audit)

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
