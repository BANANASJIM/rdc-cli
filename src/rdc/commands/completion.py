"""Shell completion script generation."""

from __future__ import annotations

import os
from pathlib import Path

import click

_SUPPORTED_SHELLS = ("bash", "zsh", "fish")


def _patch_bash_source(source: str) -> str:
    """Override Click bash handler to avoid filesystem fallback for typed dirs."""
    override = """
_rdc_completion() {
    local IFS=$'\\n'
    local response
    local has_dir=0
    COMPREPLY=()

    response=$(env COMP_WORDS="${COMP_WORDS[*]}" COMP_CWORD=$COMP_CWORD \
        _RDC_COMPLETE=bash_complete $1)

    for completion in $response; do
        IFS=',' read -r type value <<< "$completion"

        if [[ $type == 'dir' ]]; then
            COMPREPLY+=("$value")
            has_dir=1
        elif [[ $type == 'file' || $type == 'plain' ]]; then
            COMPREPLY+=("$value")
        fi
    done

    if [[ $has_dir -eq 1 ]]; then
        compopt -o nospace 2>/dev/null || true
    fi

    return 0
}

_rdc_completion_setup() {
    complete -o nosort -F _rdc_completion rdc
}

_rdc_completion_setup;
"""
    return source + override


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
    source = comp.source()
    if shell == "bash":
        return _patch_bash_source(source)
    return source


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
