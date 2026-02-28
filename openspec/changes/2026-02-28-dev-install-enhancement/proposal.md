# Dev Install Enhancement

**Date**: 2026-02-28
**Priority**: P3

## Motivation

`pixi run install` currently executes a single `uv tool install -e . --force`, placing the `rdc` binary at `~/.local/bin/rdc`. Shell tab-completion — one of the primary developer ergonomics features — is entirely absent from this flow. After installing, users must discover the `rdc completion` subcommand, know their shell's completion drop-in directory, redirect output manually, and reload their shell.

The project's `pixi.toml` also omits `win-64` from its platform list. Windows developers cannot create a pixi environment at all, even though the Python code and `uv` itself are cross-platform. Adding `win-64` unblocks Windows contributors.

Both gaps can be resolved in a single changeset: replace the one-liner `install` task with a Python script `scripts/dev_install.py` that orchestrates the full install sequence (binary + completions).

## Scope

| ID | Component | Kind | Priority |
|----|-----------|------|----------|
| DI-1 | `scripts/dev_install.py` (new) | Feature | P3 |
| DI-2 | `pixi.toml` — `install` task + `win-64` platform | Config change | P3 |

## Design

### DI-1: scripts/dev_install.py

The script runs via `uv run python scripts/dev_install.py`, giving it full access to the project's Python environment. It directly imports completion generation from `rdc.commands.completion` instead of shelling out to `rdc completion`, eliminating the PATH dependency.

**Step 1 — binary install**

```python
subprocess.run(["uv", "tool", "install", "-e", ".", "--force"], check=True)
```

Exits with a non-zero code if `uv` fails, propagating the error naturally.

**Step 2 — shell detection**

Reuse and extend `rdc.commands.completion._detect_shell()` to handle Windows:

```python
def _detect_shell() -> str:
    if sys.platform == "win32":
        return "powershell"
    name = Path(os.environ.get("SHELL", "bash")).name
    return name if name in {"bash", "zsh", "fish"} else "bash"
```

This aligns with the existing `_detect_shell()` in `completion.py` which falls back to `"bash"` when `$SHELL` is unset or unrecognized.

**Step 3 — completion generation (direct import)**

```python
from rdc.commands.completion import _generate

completion_text = _generate(shell)
```

This reuses the existing tested code, including bash/zsh patches. No subprocess call to `rdc` is needed.

**Step 4 — write to platform-standard location**

| Shell | Target path |
|-------|-------------|
| bash | `~/.local/share/bash-completion/completions/rdc` |
| zsh | `~/.zfunc/_rdc` |
| fish | `~/.config/fish/completions/rdc.fish` |
| powershell | instructions printed to stdout only |

Parent directories are created via `Path.mkdir(parents=True, exist_ok=True)`.

**Step 5 — summary**

```
[ok] rdc installed via uv tool install
[ok] zsh completion written to ~/.zfunc/_rdc
     hint: add 'fpath=(~/.zfunc $fpath)' and 'autoload -Uz compinit && compinit' to ~/.zshrc
```

For zsh, the script always prints the fpath hint (harmless if already configured, avoids unreliable detection of zsh's `$fpath` array which is not exported as an environment variable).

For PowerShell, the script prints a note directing users to `rdc completion --help`.

**Full script skeleton**:

```python
#!/usr/bin/env python3
"""Developer install: uv tool install + shell completion setup."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

_COMPLETION_PATHS: dict[str, Path] = {
    "bash": Path.home() / ".local/share/bash-completion/completions/rdc",
    "zsh": Path.home() / ".zfunc/_rdc",
    "fish": Path.home() / ".config/fish/completions/rdc.fish",
}

def _detect_shell() -> str: ...
def _install_binary() -> None: ...
def _install_completion(shell: str) -> None: ...

if __name__ == "__main__":
    _install_binary()
    shell = _detect_shell()
    _install_completion(shell)
```

### DI-2: pixi.toml changes

**Platform list** — add `win-64`:

```toml
platforms = ["linux-64", "osx-arm64", "osx-64", "win-64"]
```

**Install task**:

```toml
install = "uv run python scripts/dev_install.py"
```

Note: `pixi.lock` will be regenerated to include `win-64` packages. The main dependencies (`python`, `uv`) are available on `win-64` via conda-forge. The `osx-*` target-specific deps (`cmake`, `autoconf`, etc.) do not affect `win-64`.

## Risks

**Completion generation failure**: If `_generate()` raises (e.g., due to a Click version incompatibility), the error is caught and reported as a warning. The binary install is already complete, so the user has a working `rdc` — just without completions. Non-fatal.

**zsh `fpath` not configured**: Writing `~/.zfunc/_rdc` only takes effect if the user's `.zshrc` loads `~/.zfunc` via `fpath`. The script always prints the required snippet. Subsequent installs are silent about this.

**File write permissions**: On some systems, completion directories may have restricted permissions. The script catches `PermissionError` and prints a warning with the manual command, then continues.

**Windows pixi lock growth**: Adding `win-64` causes pixi to resolve packages for a new platform. The lock file grows. Existing CI on Linux/macOS is unaffected. `pixi.lock` changes must be verified on all platforms.
