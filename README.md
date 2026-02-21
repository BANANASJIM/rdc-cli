# rdc-cli

Unix-friendly CLI for [RenderDoc](https://renderdoc.org/) `.rdc` captures. Pipe-friendly TSV output, JSON mode, 33 commands, daemon-backed session for interactive exploration.

```bash
rdc open capture.rdc          # Start session
rdc draws                     # List draw calls (TSV)
rdc pipeline 142              # Pipeline state at EID 142
rdc shader 142 ps             # Pixel shader disassembly
rdc texture 5 -o out.png      # Export texture
rdc draws --json | jq '...'   # Machine-readable output
rdc close                     # End session
```

## Install

### PyPI (recommended)

```bash
pipx install rdc-cli
```

### AUR (Arch Linux)

```bash
yay -S rdc-cli-git
```

This builds the renderdoc Python module automatically — no extra setup needed.

### From source

```bash
git clone https://github.com/BANANASJIM/rdc-cli.git
cd rdc-cli
pixi install && pixi run sync
```

## Setup renderdoc

`rdc` requires the renderdoc Python module (`renderdoc.cpython-*.so`), which is **not** included in most system packages. Your Python version must match the one used to compile renderdoc.

### Build from source

```bash
git clone --depth 1 https://github.com/baldurk/renderdoc.git
cd renderdoc
cmake -B build -DENABLE_PYRENDERDOC=ON -DENABLE_QRENDERDOC=OFF
cmake --build build -j$(nproc)
export RENDERDOC_PYTHON_PATH=$PWD/build/lib
```

### Module discovery order

1. `RENDERDOC_PYTHON_PATH` environment variable
2. `/usr/lib/renderdoc`, `/usr/local/lib/renderdoc`
3. Sibling directory of `renderdoccmd` on PATH

### Verify

```bash
rdc doctor
```

## Commands

Run `rdc --help` for the full command list, or `rdc <command> --help` for details.

| Category | Commands |
|----------|----------|
| Session | `open`, `close`, `status`, `goto` |
| Inspection | `info`, `stats`, `events`, `draws`, `event`, `draw`, `log` |
| GPU state | `pipeline`, `bindings`, `shader`, `shaders`, `shader-map` |
| Resources | `resources`, `resource`, `passes`, `pass`, `usage` |
| Export | `texture`, `rt`, `buffer` |
| Search | `search`, `counters` |
| VFS | `ls`, `cat`, `tree` |
| Utility | `doctor`, `completion`, `capture`, `count` |

All commands support `--json` for machine-readable output.

### Shell completions

```bash
rdc completion bash > ~/.local/share/bash-completion/completions/rdc
rdc completion zsh > ~/.zfunc/_rdc
eval "$(rdc completion bash)"
```

## Development

```bash
pixi run sync                 # Install Python deps
pixi run check                # lint + typecheck + test (653 tests, 92% coverage)
```

GPU integration tests require a real renderdoc module:

```bash
export RENDERDOC_PYTHON_PATH=/path/to/renderdoc/build/lib
pixi run test-gpu
```

## License

MIT
