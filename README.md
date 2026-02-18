# rdc-cli

Unix-friendly CLI for RenderDoc `.rdc` captures.

## Current status

Phase 0 bootstrap in progress.

Implemented skeleton commands:
- `rdc --version`
- `rdc doctor`
- `rdc capture` (thin wrapper to `renderdoccmd capture`)

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
