# rdc-cli

**Unix-friendly CLI for RenderDoc `.rdc` captures.**

Pipe-friendly TSV output, JSON mode, 54 commands, and a daemon-backed session
for interactive exploration of [RenderDoc](https://renderdoc.org/) captures —
all from the terminal.

## Quick start

```bash
pipx install rdc-cli           # install
rdc open capture.rdc           # start a session
rdc draws                      # list draw calls (TSV)
rdc pipeline 142               # pipeline state at EID 142
rdc shader 142 ps              # pixel shader disassembly
rdc texture 5 -o out.png       # export texture
rdc draws --json | jq '...'    # machine-readable output
rdc close                      # end session
```

## Features

- **Pipe-friendly output** — TSV by default, `--json` for structured data
- **Daemon-backed sessions** — open once, query many times
- **VFS path namespace** — browse captures like a filesystem with `rdc ls`, `rdc cat`, `rdc tree`
- **54 commands** — inspection, GPU state, export, search, debug, assertions
- **Shell completions** — Bash, Zsh, Fish

## Documentation

- [Installation](install.md) — requirements, install methods
- [Usage](usage.md) — basic workflow, daemon mode, output formats
- [VFS](vfs.md) — virtual filesystem path namespace
- [CLI Reference](cli-reference.md) — full command documentation
