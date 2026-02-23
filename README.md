```
 _____  _____   _____
|  __ \|  __ \ / ____|
| |__) | |  | | |
|  _  /| |  | | |
| | \ \| |__| | |____
|_|  \_\_____/ \_____|  cli
```

[![PyPI](https://img.shields.io/pypi/v/rdc-cli)](https://pypi.org/project/rdc-cli/)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://pypi.org/project/rdc-cli/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Commands](https://img.shields.io/endpoint?url=https://bananasjim.github.io/rdc-cli/badges/commands.json)](https://bananasjim.github.io/rdc-cli/)
[![Tests](https://img.shields.io/endpoint?url=https://bananasjim.github.io/rdc-cli/badges/tests.json)](https://bananasjim.github.io/rdc-cli/)
[![Coverage](https://img.shields.io/endpoint?url=https://bananasjim.github.io/rdc-cli/badges/coverage.json)](https://bananasjim.github.io/rdc-cli/)

Pipe-friendly TSV output, JSON mode, 51 commands, daemon-backed session for interactive exploration of [RenderDoc](https://renderdoc.org/) `.rdc` captures.

**[Full documentation →](https://bananasjim.github.io/rdc-cli/)**

```bash
rdc open capture.rdc            # start session
rdc draws                       # list draw calls (TSV)
rdc pipeline 142                # pipeline state at EID 142
rdc shader 142 ps               # pixel shader disassembly
rdc texture 5 -o out.png        # export texture
rdc debug 142 ps 400 300        # debug pixel shader at (400,300)
rdc assert-pixel 142 400 300 \
    --expect 0.5,0.0,0.0,1.0   # CI pixel assertion
rdc draws --json | jq '...'     # machine-readable output
rdc close                       # end session
```

## Install

**PyPI** (recommended)

```bash
pipx install rdc-cli
# build renderdoc Python module (one-time, ~3 min, needs cmake/ninja/python3)
curl -fsSL https://raw.githubusercontent.com/BANANASJIM/rdc-cli/master/scripts/build-renderdoc.sh | bash
rdc doctor   # verify installation
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

## Commands

Run `rdc --help` for the full command list, or `rdc <command> --help` for details.

| Category | Commands |
|----------|----------|
| Session | `open`, `close`, `status`, `goto` |
| Inspection | `info`, `stats`, `events`, `draws`, `event`, `draw`, `log` |
| GPU state | `pipeline`, `bindings`, `shader`, `shaders`, `shader-map` |
| Debug | `debug`, `pixel`, `pick-pixel`, `tex-stats` |
| Shader Edit | `shader-build`, `shader-replace`, `shader-restore`, `shader-restore-all`, `shader-encodings` |
| Resources | `resources`, `resource`, `passes`, `pass`, `usage` |
| Export | `texture`, `rt`, `buffer`, `mesh`, `snapshot` |
| Search | `search`, `counters` |
| Assertions | `assert-pixel`, `assert-state`, `assert-image`, `assert-count`, `assert-clean` |
| VFS | `ls`, `cat`, `tree` |
| Utility | `doctor`, `completion`, `capture`, `count`, `script`, `diff` |

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
pixi run check                # lint + typecheck + test (1729 tests, 95.51% coverage)
pixi run verify               # full packaging verification (19 checks)
```

GPU integration tests require a real renderdoc module:

```bash
export RENDERDOC_PYTHON_PATH=/path/to/renderdoc/build/lib
pixi run test-gpu
```

## License

[MIT](LICENSE)
