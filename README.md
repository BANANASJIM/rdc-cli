# rdc-cli

Unix-friendly CLI for RenderDoc `.rdc` captures.

## Current status

Phase 0 bootstrap in progress.

Implemented skeleton commands:
- `rdc --version`
- `rdc doctor`
- `rdc capture` (thin wrapper to `renderdoccmd capture`)
- `rdc capture --list-apis`
- `rdc open` / `rdc close` / `rdc status` / `rdc goto` (Phase 0 daemon-transport skeleton)

## Development (uv)

```bash
# one-time
uv sync --extra dev

# run tests
uv run pytest

# run quality gates
make check
```

## Build / packaging

```bash
uv build
```

## Fixture capture helper

Generate a local fixture with RenderDoc:

```bash
./scripts/capture_fixture.sh triangle /path/to/your-app [args...]
```

This writes `tests/fixtures/triangle.rdc`.

## Docker dev image

```bash
docker build -t rdc-cli-dev -f docker/Dockerfile .
docker run --rm -it -v "$PWD":/workspace rdc-cli-dev bash
```

## Required CI checks

- lint (ruff)
- typecheck (mypy)
- test (pytest, py3.10/3.11/3.12)
- commitlint (Conventional Commits)

