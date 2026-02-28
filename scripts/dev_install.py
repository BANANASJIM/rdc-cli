"""Dev install script: installs rdc binary + shell completions."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_SHELLS_WITH_FILE = {"bash", "zsh", "fish"}


def detect_shell() -> str:
    """Detect the current shell environment."""
    if sys.platform == "win32":
        return "powershell"
    name = Path(os.environ.get("SHELL", "bash")).name
    return name if name in _SHELLS_WITH_FILE else "bash"


def _completion_path(shell: str, home: Path) -> Path:
    """Return platform-standard completion file path for *shell*."""
    if shell == "bash":
        return home / ".local/share/bash-completion/completions/rdc"
    if shell == "zsh":
        return home / ".zfunc/_rdc"
    # fish
    return home / ".config/fish/completions/rdc.fish"


def install_binary() -> None:
    """Run ``uv tool install -e . --force`` (fatal on failure)."""
    subprocess.run(["uv", "tool", "install", "-e", ".", "--force"], check=True)


def install_completion(shell: str, home: Path | None = None) -> bool:
    """Generate and write shell completion to the standard path.

    Returns True on success, False on failure (non-fatal).
    """
    from rdc.commands.completion import _generate

    if home is None:
        home = Path.home()

    if shell == "powershell":
        print("PowerShell: add to your $PROFILE:")
        print("  rdc --shell-completion powershell | Out-String | Invoke-Expression")
        return True

    try:
        source = _generate(shell)
    except Exception as exc:
        print(f"WARNING: completion generation failed for {shell}: {exc}")
        return False

    path = _completion_path(shell, home)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source)
    except PermissionError:
        print(f"WARNING: cannot write {path} — permission denied")
        return False

    print(f"Completion written: {path}")
    if shell == "zsh":
        print("  Hint: ensure ~/.zfunc is in fpath:")
        print("  fpath=(~/.zfunc $fpath); autoload -Uz compinit && compinit")
    return True


def main() -> None:
    """Entry point: install binary, then shell completions."""
    print("==> Installing rdc binary ...")
    install_binary()
    print("==> Binary installed.\n")

    shell = detect_shell()
    print(f"==> Detected shell: {shell}")
    ok = install_completion(shell)

    print("\n--- Summary ---")
    print(f"  Binary:     installed")
    print(f"  Shell:      {shell}")
    print(f"  Completion: {'installed' if ok else 'SKIPPED (see warnings above)'}")


if __name__ == "__main__":
    main()
