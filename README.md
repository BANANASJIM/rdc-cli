# rdc-cli

Unix-friendly CLI for RenderDoc `.rdc` captures.

## Current status

Phase 0 bootstrap in progress.

Implemented skeleton commands:
- `rdc --version`
- `rdc doctor`
- `rdc capture` (thin wrapper to `renderdoccmd capture`)

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest
```
