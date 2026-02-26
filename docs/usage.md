# Usage

## Basic workflow

`rdc` uses a daemon-backed session model. Open a capture file once, then run
any number of inspection commands against it.

```bash
rdc open capture.rdc     # start a session (launches daemon)
rdc draws                # list draw calls
rdc pipeline 142         # inspect pipeline state at EID 142
rdc shader 142 ps        # view pixel shader disassembly
rdc shader ps            # view PS at current EID (after goto)
rdc close                # end session (stops daemon)
```

Render pass lookup accepts either a pass name or a 0-based pass index:

```bash
rdc pass 0               # first pass
rdc pass GBuffer         # pass by name
```

## Named sessions

Run multiple sessions in parallel with `--session`:

```bash
rdc --session before open before.rdc
rdc --session after  open after.rdc
rdc --session before draws
rdc --session after  draws
```

Or use the `RDC_SESSION` environment variable:

```bash
export RDC_SESSION=mytest
rdc open capture.rdc
rdc draws
```

## Daemon mode

The daemon starts automatically with `rdc open` and stops with `rdc close`.
Check session status:

```bash
rdc status               # show current session info
```

## Output formats

### TSV (default)

All commands produce tab-separated output by default, suitable for piping
into standard Unix tools:

```bash
rdc draws | head -5
rdc resources | sort -k2
```

### JSON

Use `--json` for machine-readable structured output:

```bash
rdc draws --json | jq '.[]'
rdc pipeline 142 --json > state.json
rdc info --json | jq '.api'
```

### JSONL

Some commands support `--jsonl` for newline-delimited JSON:

```bash
rdc events --jsonl | head -100
```

## Exporting resources

Export textures, render targets, and buffers:

```bash
rdc texture 5 -o tex.png          # export texture by resource ID
rdc rt 142 -o rt.png              # export render target at EID
rdc buffer 3 -o data.bin          # export buffer contents
```

## Shell completions

Generate completions for your shell:

```bash
rdc completion bash > ~/.local/share/bash-completion/completions/rdc
rdc completion zsh  > ~/.zfunc/_rdc
rdc completion fish > ~/.config/fish/completions/rdc.fish
```
