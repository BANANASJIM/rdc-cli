"""Shell completion script generation."""

from __future__ import annotations

import os
from pathlib import Path

import click

_SUPPORTED_SHELLS = ("bash", "zsh", "fish")


def _patch_bash_source(source: str) -> str:
    """Override Click bash handler to avoid filesystem fallback for typed dirs."""
    import re

    source = re.sub(r"_rdc_completion\(\)\s*\{.*?\n\}\s*", "", source, flags=re.DOTALL)
    source = re.sub(r"_rdc_completion_setup\(\)\s*\{.*?\n\}\s*", "", source, flags=re.DOTALL)
    source = re.sub(r"_rdc_completion_setup;\s*", "", source)

    override = """\
_rdc_completion() {
    local IFS=$'\\n'
    local response
    local has_dir=0
    COMPREPLY=()

    response=$(env COMP_WORDS="${COMP_WORDS[*]}" COMP_CWORD=$COMP_CWORD \
        _RDC_COMPLETE=bash_complete $1)

    for completion in $response; do
        IFS=',' read -r type value <<< "$completion"

        if [[ $type == 'dir' || ($type == 'plain' && $value == */) ]]; then
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


def _patch_zsh_source(source: str) -> str:
    """Override Zsh source to use VFS values instead of filesystem fallback."""
    old_type_block = """\
        if [[ "$type" == "plain" ]]; then
            if [[ "$descr" == "_" ]]; then
                completions+=("$key")
            else
                completions_with_descriptions+=("$key":"$descr")
            fi
        elif [[ "$type" == "dir" ]]; then
            _path_files -/
        elif [[ "$type" == "file" ]]; then
            _path_files -f
        fi"""

    new_type_block = """\
        if [[ "$type" == "plain" ]]; then
            if [[ "$key" == */ ]]; then
                if [[ "$descr" == "_" ]]; then
                    completions_nospace+=("$key")
                else
                    completions_nospace_with_descriptions+=("$key":"$descr")
                fi
            else
                if [[ "$descr" == "_" ]]; then
                    completions+=("$key")
                else
                    completions_with_descriptions+=("$key":"$descr")
                fi
            fi
        elif [[ "$type" == "dir" ]]; then
            if [[ "$descr" == "_" ]]; then
                completions_nospace+=("$key")
            else
                completions_nospace_with_descriptions+=("$key":"$descr")
            fi
        elif [[ "$type" == "file" ]]; then
            if [[ "$descr" == "_" ]]; then
                completions+=("$key")
            else
                completions_with_descriptions+=("$key":"$descr")
            fi
        fi"""
    source = source.replace(old_type_block, new_type_block)

    old_local = """\
    local -a completions_with_descriptions"""
    new_local = """\
    local -a completions_with_descriptions
    local -a completions_nospace
    local -a completions_nospace_with_descriptions"""
    source = source.replace(old_local, new_local)

    old_tail = """\
    if [ -n "$completions" ]; then
        compadd -U -V unsorted -a completions
    fi
}"""
    new_tail = """\
    if [ -n "$completions" ]; then
        compadd -U -V unsorted -a completions
    fi

    if [ -n "$completions_nospace_with_descriptions" ]; then
        _describe -V unsorted completions_nospace_with_descriptions -U -q -S ''
    fi

    if [ -n "$completions_nospace" ]; then
        compadd -U -V unsorted -q -S '' -a completions_nospace
    fi
}"""
    source = source.replace(old_tail, new_tail)
    return source


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
    elif shell == "zsh":
        return _patch_zsh_source(source)
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
