"""Shell completion script generation."""

from __future__ import annotations

import os
from pathlib import Path

import click

_SUPPORTED_SHELLS = ("bash", "zsh", "fish")


def _detect_shell() -> str:
    """Detect current shell from $SHELL."""
    name = Path(os.environ.get("SHELL", "bash")).name
    return name if name in _SUPPORTED_SHELLS else "bash"


def _generate(shell: str) -> str:
    """Generate completion script via Click's built-in mechanism."""
    from click.shell_completion import get_completion_class

    from rdc.cli import main  # deferred: rdc.cli imports this module

    cls = get_completion_class(shell)
    if cls is None:
        raise click.ClickException(f"Unsupported shell: {shell}")
    comp = cls(cli=main, ctx_args={}, prog_name="rdc", complete_var="_RDC_COMPLETE")
    return comp.source()


@click.command("completion")
@click.argument("shell", required=False, type=click.Choice(_SUPPORTED_SHELLS))
def completion_cmd(shell: str | None) -> None:
    """Generate shell completion script.

    Prints the completion script to stdout. Redirect or eval as needed.

    \b
    Examples:
        rdc completion bash > ~/.local/share/bash-completion/completions/rdc
        rdc completion zsh > ~/.zfunc/_rdc
        eval "$(rdc completion bash)"
    """
    if shell is None:
        shell = _detect_shell()
        click.echo(f"# Detected shell: {shell}", err=True)

    click.echo(_generate(shell))
