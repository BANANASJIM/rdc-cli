# Tasks: Dev Install Enhancement

## Implementation (Opus worktree agent)

- [ ] `scripts/dev_install.py` — create Python script that runs `uv tool install`, detects shell, generates completion via direct import of `rdc.commands.completion._generate`, writes to platform-standard path for bash/zsh/fish (PowerShell prints instructions only), and prints summary
- [ ] `pixi.toml` — change `install` task to `"uv run python scripts/dev_install.py"`; add `"win-64"` to platforms
- [ ] `tests/unit/test_dev_install.py` — unit tests covering shell detection, completion file writing per shell, parent dir creation, uv install subprocess call, error handling (non-fatal completion failure, PermissionError), and end-to-end flow

## Post-implementation

- [ ] Merge worktree output back to feature branch
- [ ] Run `pixi run lint && pixi run test` — zero failures allowed
- [ ] New Opus subagent code review
