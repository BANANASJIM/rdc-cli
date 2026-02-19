# rdc-cli

Unix-friendly CLI for RenderDoc `.rdc` captures.

## Install

```bash
pip install rdc-cli
```

## Usage

```bash
rdc doctor                    # Check environment
rdc open capture.rdc          # Open capture
rdc info                     # Capture metadata
rdc draws                    # List draw calls
rdc events                   # List all events
rdc pipeline 142            # Pipeline state at event 142
rdc shader 142 ps             # Shader disassembly
rdc resources                # List resources
rdc passes                   # List render passes
```

## Development

```bash
uv sync --extra dev
make check
```

## Docker

```bash
docker build -t rdc-cli-dev -f docker/Dockerfile .
```
