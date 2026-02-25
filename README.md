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

**Turn RenderDoc captures into Unix text streams.** rdc-cli does not replace RenderDoc — it makes `.rdc` file contents accessible to `grep`, `awk`, `sort`, `diff`, `jq`, and AI agents.

**[Full documentation →](https://bananasjim.github.io/rdc-cli/)**

```bash
rdc open scene.rdc
rdc draws | grep Shadow | sort -t$'\t' -k3 -rn | head -5   # top 5 shadow draws by tri count
rdc shader 142 ps | grep shadowMap                           # find shadow sampling in PS
rdc cat /draws/142/shader/ps/constants                       # inspect bound constants
rdc diff before.rdc after.rdc --draws | grep '~'             # what changed between two frames?
rdc close
```

## Install

**PyPI — Linux** (recommended)

```bash
pipx install rdc-cli                  # install the CLI
python scripts/build_renderdoc.py     # one-time build (needs cmake + ninja)
rdc doctor                            # verify everything works
```

**PyPI — Windows** (experimental)

```bash
pipx install rdc-cli
python scripts/build_renderdoc.py     # needs cmake + Visual Studio Build Tools
rdc doctor
```

**PyPI — macOS** (remote replay recommended)

```bash
pipx install rdc-cli
# Remote replay (no local renderdoc needed):
rdc remote connect linux-host:39920      # connect to a Linux/Windows target
rdc remote list                          # list capturable apps
rdc remote capture /path/to/app          # capture + pull .rdc file
# Optional: local replay — run inside repo for auto-managed deps
# pixi run setup-renderdoc  (installs cmake/ninja/autotools via pixi)
# or: python scripts/build_renderdoc.py
rdc doctor
```

**AUR** (Arch Linux — builds renderdoc automatically, no extra setup)

```bash
yay -S rdc-cli-git    # recommended: tracks latest master
# or
yay -S rdc-cli        # stable: tracks tagged releases
```

**From source**

```bash
git clone https://github.com/BANANASJIM/rdc-cli.git
cd rdc-cli
pixi install && pixi run sync
# Build renderdoc once (pixi installs toolchain on macOS automatically)
pixi run setup-renderdoc
```

### Platform Support Matrix

| Platform | Local capture/replay | Split client |
|----------|----------------------|--------------|
| Linux | ✅ | ✅ |
| macOS | ✅ (`pixi run setup-renderdoc`) | ✅ (no local RenderDoc needed) |
| Windows *(experimental, not tested in this PR)* | ⚠️ expected | ⚠️ expected |

### RenderDoc bootstrap (all platforms)

```bash
# Always run from the repo root
python scripts/build_renderdoc.py .local/renderdoc --build-dir .local/renderdoc-build

# or, if you're already using pixi:
pixi run setup-renderdoc
```

That single Python script is the canonical path; the pixi task wraps it for convenience (and installs cmake/ninja/autotools on macOS).

## Quickstart

**Explore a capture like a filesystem:**

```bash
rdc ls /                              # top-level: draws, passes, resources, shaders, ...
rdc ls /draws/142                     # what's inside this draw call?
rdc cat /draws/142/pipeline/om        # output merger state
rdc tree /passes --depth 2            # pass structure at a glance
```

**Shader debugging — no GUI needed:**

```bash
rdc shader 142 ps                     # pixel shader disassembly
rdc shader 142 ps --constants         # current constant buffer values
rdc debug pixel 142 400 300 --trace   # step-by-step PS execution trace
rdc search "shadowMap"                # grep across all shaders in the frame
```

**Export and scripting:**

```bash
rdc texture 5 -o albedo.png           # export a texture
rdc rt 142 -o render.png              # export render target
rdc buffer 88 -o verts.bin            # export raw buffer
rdc snapshot 142 -o ./snap/           # pipeline + shaders + render targets
rdc draws --json | jq '.[] | select(.tri_count > 10000)'  # filter with jq
```

**CI assertions:**

```bash
rdc open frame.rdc
rdc assert-pixel 142 400 300 --expect "0.5 0.0 0.0 1.0" --tolerance 0.01
rdc assert-state 142 topology --expect TriangleList
rdc assert-image golden.png actual.png --threshold 0.001
rdc assert-clean --min-severity HIGH
rdc close
```

**Two-frame diff:**

```bash
rdc diff before.rdc after.rdc --shortstat        # summary: draws ±N, resources ±N
rdc diff before.rdc after.rdc --draws             # per-draw changes
rdc diff before.rdc after.rdc --framebuffer       # pixel-level image diff
```

**Split mode (macOS or thin clients)**

```bash
# On Linux/Windows replay host
rdc capture --output /tmp/game.rdc -- /path/to/game
rdc open /tmp/game_frame0.rdc --listen 0.0.0.0:54321

# On macOS client (no local renderdoc required)
PYTHONPATH=src .venv/bin/rdc open --connect host:54321 --token TOKEN
PYTHONPATH=src .venv/bin/rdc capture --output /tmp/mac_capture.rdc -- /usr/bin/vkcube
PYTHONPATH=src .venv/bin/rdc remote capture /usr/bin/vkcube -o /tmp/mac_remote.rdc
rdc close --shutdown
```

## Why rdc-cli?

RenderDoc is excellent at capturing GPU frames and replaying them interactively. But its GUI doesn't compose — you can't pipe a draw call list into `sort`, diff two captures in CI, or let an AI agent inspect shader state.

rdc-cli bridges that gap:

- **TSV by default** — every command outputs tab-separated text that pipes directly into Unix tools. Raw numbers, not human-friendly formatting (use `--table` for that).
- **VFS path namespace** — GPU state is navigable like a filesystem: `/draws/142/shader/ps`, `/passes/GBuffer/draws`, `/resources/88`. Explore with `ls`, read with `cat`.
- **Daemon architecture** — load the capture once, then query as many times as you want. No per-command startup cost.
- **Built for CI** — `assert-pixel`, `assert-state`, `assert-image`, `assert-count`, `assert-clean` with `diff(1)`-compatible exit codes (0=pass, 1=fail, 2=error).
- **AI-agent friendly** — structured output (`--json`, `--jsonl`), deterministic VFS paths, and a [Claude Code skill](https://bananasjim.github.io/rdc-cli/) for automated GPU frame analysis.
- **Escape hatch** — `rdc script` runs arbitrary Python inside the daemon with full access to the renderdoc module, for anything the CLI doesn't cover yet.

## Commands

Run `rdc --help` for the full list, or `rdc <command> --help` for details.  See the [full command reference](https://bananasjim.github.io/rdc-cli/docs/cli-reference/rdc/) for every option.

| Category | Commands |
|----------|----------|
| Session | `open`, `close`, `status`, `goto` |
| Inspection | `info`, `stats`, `events`, `draws`, `event`, `draw`, `log` |
| GPU state | `pipeline`, `bindings`, `shader`, `shaders`, `shader-map` |
| Debug | `debug pixel`, `debug vertex`, `debug thread`, `pixel`, `pick-pixel`, `tex-stats` |
| Shader edit | `shader-build`, `shader-replace`, `shader-restore`, `shader-restore-all`, `shader-encodings` |
| Resources | `resources`, `resource`, `passes`, `pass`, `usage` |
| Export | `texture`, `rt`, `buffer`, `mesh`, `snapshot` |
| Search | `search`, `counters` |
| Assertions | `assert-pixel`, `assert-state`, `assert-image`, `assert-count`, `assert-clean` |
| Diff | `diff` (with `--draws`, `--stats`, `--framebuffer`, `--pipeline`, etc.) |
| VFS | `ls`, `cat`, `tree` |
| Remote | `remote connect`, `remote list`, `remote capture` |
| Utility | `doctor`, `completion`, `capture`, `count`, `script`, `install-skill` |

All list commands output TSV. All commands support `--json`. Footer/summary goes to stderr — stdout is always clean data.

### Common options

Options available on most list/query commands (not every command supports all):

```
--json           JSON output (all commands)
--jsonl          streaming JSON, one object per line (list commands)
--no-header      drop TSV header for awk/cut (list commands)
-q / --quiet     IDs only for xargs (list commands)
--sort <field>   sort by field (events, resources, shaders)
--limit <N>      truncate rows (events, search)
--filter <pat>   name glob filter (events)
-o <path>        output to file (export commands)
```

### Shell completions

```bash
rdc completion bash > ~/.local/share/bash-completion/completions/rdc
rdc completion zsh  > ~/.zfunc/_rdc
rdc completion fish > ~/.config/fish/completions/rdc.fish
```

## Development

```bash
pixi run sync                 # install deps + git hooks + renderdoc symlink
pixi run check                # lint + typecheck + test
pixi run verify               # full packaging verification
```

GPU integration tests require a real renderdoc module:

```bash
export RENDERDOC_PYTHON_PATH=/path/to/renderdoc/build/lib
pixi run test-gpu
```

## License

[MIT](LICENSE)
