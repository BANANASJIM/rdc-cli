"""Install rdc-cli skill files for Claude Code global discovery."""

from __future__ import annotations

import shutil
from importlib.resources import files
from pathlib import Path
from typing import Any

import click


def _skill_target() -> Path:
    """Return the global skill install directory."""
    return Path.home() / ".claude" / "skills" / "rdc-cli"


def _bundled_files() -> list[tuple[Any, str]]:
    """Enumerate bundled .md files from the rdc._skills package.

    Returns:
        List of (traversable, relative_name) pairs for each .md file.
    """
    root = files("rdc._skills")
    result: list[tuple[Any, str]] = []

    def _walk(node: Any, prefix: str) -> None:
        for child in node.iterdir():
            rel = f"{prefix}{child.name}" if prefix else child.name
            if child.is_file() and child.name.endswith(".md"):
                result.append((child, rel))
            elif child.is_dir():
                _walk(child, f"{rel}/")

    _walk(root, "")
    return result


def _install(target: Path) -> list[str]:
    """Copy all bundled skill files to *target*.

    Args:
        target: Destination directory.

    Returns:
        List of installed relative paths.
    """
    installed: list[str] = []
    for trav, rel in _bundled_files():
        dest = target / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(trav.read_bytes())
        installed.append(rel)
    return installed


def _check(target: Path) -> bool:
    """Return True if all bundled files are installed and current."""
    for trav, rel in _bundled_files():
        dest = target / rel
        if not dest.exists() or dest.read_bytes() != trav.read_bytes():
            return False
    return True


def _remove(target: Path) -> bool:
    """Remove the installed skill directory.

    Returns:
        True if something was removed.
    """
    if target.exists():
        shutil.rmtree(target)
        return True
    return False


@click.command("install-skill")
@click.option("--check", "do_check", is_flag=True, help="Verify installed files are current.")
@click.option("--remove", "do_remove", is_flag=True, help="Remove installed skill files.")
def install_skill_cmd(do_check: bool, do_remove: bool) -> None:
    """Install rdc-cli skill files to ~/.claude/skills/rdc-cli/.

    Copies the bundled SKILL.md and command reference so Claude Code
    can discover rdc-cli globally.

    \b
    Examples:
        rdc install-skill            # install / update
        rdc install-skill --check    # verify freshness
        rdc install-skill --remove   # uninstall
    """
    if do_check and do_remove:
        raise click.UsageError("--check and --remove are mutually exclusive.")

    target = _skill_target()

    if do_check:
        if _check(target):
            click.echo("Skill files are installed and current.")
            raise SystemExit(0)
        click.echo("Skill files are missing or stale.", err=True)
        raise SystemExit(1)

    if do_remove:
        if _remove(target):
            click.echo(f"Removed {target}")
        else:
            click.echo("Nothing to remove.")
        return

    for rel in _install(target):
        click.echo(str(target / rel))
