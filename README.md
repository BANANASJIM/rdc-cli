# rdc-cli

Unix-friendly CLI for RenderDoc `.rdc` captures. Pipe-friendly TSV output, JSON mode, daemon-backed session for interactive exploration.

## Requirements

- **Python >= 3.14**
- **renderdoc** Python module (bundled with [RenderDoc](https://renderdoc.org/) >= 1.33, or build from source)

## Install

```bash
pip install rdc-cli
```

Or from source with [pixi](https://pixi.sh/):

```bash
pixi install
pixi run sync
```

### RenderDoc module discovery

`rdc` auto-discovers the renderdoc Python module in this order:

1. `RENDERDOC_PYTHON_PATH` environment variable
2. `/usr/lib/renderdoc`, `/usr/local/lib/renderdoc`
3. Sibling directory of `renderdoccmd` on PATH

Verify with:

```bash
rdc doctor
```

## Usage

### Session workflow

```bash
rdc open capture.rdc          # Start daemon, load capture
rdc status                    # Current session info
rdc goto 142                  # Navigate to event 142
rdc close                     # Stop daemon
```

### Inspection commands

```bash
rdc info                      # Capture metadata
rdc stats                     # Per-pass breakdown, top draws
rdc events                    # List all events
rdc events --type draw        # Filter by type
rdc draws                     # List draw calls
rdc draw 142                  # Draw detail at EID
rdc event 42                  # API call detail at EID
rdc log                       # API validation messages
```

### GPU state

```bash
rdc pipeline 142              # Pipeline state at EID
rdc bindings 142              # Bound resources per stage
rdc shader 142 ps             # Shader disassembly
rdc shaders                   # List unique shaders
rdc shader-map                # EID-to-shader TSV mapping
```

### Resources and passes

```bash
rdc resources                 # List all resources
rdc resource 42               # Resource detail by ID
rdc passes                    # List render passes
rdc usage 42                  # Resource usage across frame
rdc usage --all               # Full resource usage matrix
```

### Export (binary)

```bash
rdc texture 5 -o out.png      # Export texture as PNG
rdc rt 142 -o color0.png      # Render target at EID
rdc buffer 3 -o data.bin      # Raw buffer data
```

### Search and counters

```bash
rdc search "gl_Position"      # Grep across all shaders
rdc counters --list           # Available GPU counters
rdc counters                  # Fetch counter values
rdc counters --eid 142        # Counters at specific event
```

### VFS (virtual filesystem)

```bash
rdc ls /                      # List VFS root
rdc ls /draws/142/            # List draw subnodes
rdc cat /draws/142/pipeline   # Read VFS leaf
rdc tree /draws/142 --depth 3 # Tree view
```

### Unix helpers

```bash
rdc count draws               # Single integer count
rdc count resources
rdc events --type draw | wc -l
rdc draws --json | jq '.draws[] | .triangles'
```

All commands support `--json` for machine-readable output.

## Development

```bash
pixi install
pixi run sync                 # Install Python deps
pixi run lint                 # ruff check + format
pixi run typecheck            # mypy
pixi run test                 # Unit tests (637 tests, 92% coverage)
pixi run check                # lint + typecheck + test
```

### GPU integration tests

Requires a real renderdoc module and a GPU:

```bash
export RENDERDOC_PYTHON_PATH=/path/to/renderdoc/build/lib
pixi run test-gpu             # 150 GPU integration tests
pixi run test-all             # Full suite
```

## Docker

```bash
docker build -t rdc-cli-dev -f docker/Dockerfile .
docker run --rm -it -v "$PWD":/workspace rdc-cli-dev bash
# Inside container:
uv sync && rdc doctor
```

## License

MIT
