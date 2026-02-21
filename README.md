```
          _
 _ __ __| | ___
| '__/ _` |/ __|
| | | (_| | (__
|_|  \__,_|\___|
```

[![PyPI](https://img.shields.io/pypi/v/rdc-cli)](https://pypi.org/project/rdc-cli/)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://pypi.org/project/rdc-cli/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Pipe-friendly TSV output, JSON mode, 33 commands, daemon-backed session for interactive exploration of [RenderDoc](https://renderdoc.org/) `.rdc` captures.

```bash
rdc open capture.rdc          # start session
rdc draws                     # list draw calls (TSV)
rdc pipeline 142              # pipeline state at EID 142
rdc shader 142 ps             # pixel shader disassembly
rdc texture 5 -o out.png      # export texture
rdc draws --json | jq '...'   # machine-readable output
rdc close                     # end session
```

---

## Install

**PyPI** (recommended)

```bash
pipx install rdc-cli
```

**AUR** (Arch Linux — builds renderdoc Python module automatically)

```bash
yay -S rdc-cli-git
```

**From source**

```bash
git clone https://github.com/BANANASJIM/rdc-cli.git
cd rdc-cli
pixi install && pixi run sync
```

## Setup renderdoc

`rdc` requires the renderdoc Python module (`renderdoc.cpython-*.so`), which is **not** included in most system packages. Your Python version must match the one used to compile renderdoc.

```bash
git clone --depth 1 https://github.com/baldurk/renderdoc.git
cd renderdoc
cmake -B build -DENABLE_PYRENDERDOC=ON -DENABLE_QRENDERDOC=OFF
cmake --build build -j$(nproc)
export RENDERDOC_PYTHON_PATH=$PWD/build/lib
```

Module discovery order:

1. `RENDERDOC_PYTHON_PATH` environment variable
2. `/usr/lib/renderdoc`, `/usr/local/lib/renderdoc`
3. Sibling directory of `renderdoccmd` on PATH

Verify with `rdc doctor`.

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
rdc completion zsh  > ~/.zfunc/_rdc
rdc completion fish > ~/.config/fish/completions/rdc.fish
```

## Development

```bash
pixi run sync                 # install deps + activate git hooks
pixi run check                # lint + typecheck + test (653 tests, 92% coverage)
pixi run verify               # full packaging verification (19 checks)
```

GPU integration tests require a real renderdoc module:

```bash
export RENDERDOC_PYTHON_PATH=/path/to/renderdoc/build/lib
pixi run test-gpu
```

## License

[MIT](LICENSE)
