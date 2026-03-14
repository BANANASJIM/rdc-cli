from __future__ import annotations

from pathlib import Path

import click


@click.command("setup-renderdoc")
@click.argument("install_dir", required=False, default=None)
@click.option("--build-dir", default=None, help="Build cache directory.")
@click.option("--version", "rdoc_version", default=None, help="RenderDoc tag to build.")
@click.option("--jobs", type=int, default=None, help="Parallel build jobs.")
@click.option("--android", is_flag=True, default=False, help="Download Android APKs.")
@click.option("--arm", is_flag=True, default=False, help="Download ARM Performance Studio (Mali).")
@click.option(
    "--arm-studio",
    default=None,
    type=click.Path(exists=True, file_okay=False),
    help="ARM Performance Studio local install path.",
)
def setup_renderdoc_cmd(
    install_dir: str | None,
    build_dir: str | None,
    rdoc_version: str | None,
    jobs: int | None,
    android: bool,
    arm: bool,
    arm_studio: str | None,
) -> None:
    """Build and install the renderdoc Python module from source."""
    if (arm_studio or arm) and not android:
        raise click.UsageError("--arm / --arm-studio requires --android")

    if android:
        _handle_android(arm_studio, arm)
        return

    argv: list[str] = []
    if install_dir:
        argv.append(install_dir)
    if build_dir:
        argv.extend(["--build-dir", build_dir])
    if rdoc_version:
        argv.extend(["--version", rdoc_version])
    if jobs is not None:
        argv.extend(["--jobs", str(jobs)])
    from rdc._build_renderdoc import main

    main(argv)


def _resolve_lib_dir() -> Path:
    """Resolve the renderdoc lib directory from the loaded module or default."""
    from rdc.discover import find_renderdoc

    rd = find_renderdoc()
    if rd is not None and rd.__file__ is not None:
        return Path(rd.__file__).resolve().parent
    from rdc._build_renderdoc import default_install_dir

    return default_install_dir()


def _handle_android(arm_studio: str | None, arm: bool = False) -> None:
    """Handle --android flag logic."""
    from rdc._build_renderdoc import (
        RDOC_TAG,
        _android_apk_dir,
        download_android_apks,
        download_arm_studio,
        install_arm_studio,
    )

    lib_dir = _resolve_lib_dir()

    # --arm: auto-download ARM PS then install from it
    if arm:
        arm_path = download_arm_studio(Path(".local/arm-performance-studio"))
        install_arm_studio(arm_path, lib_dir)
        click.echo("ARM Performance Studio renderdoc + APKs installed.")
        return

    if arm_studio:
        install_arm_studio(Path(arm_studio), lib_dir)
        click.echo("ARM Performance Studio installed.")
        return

    apk_dir = _android_apk_dir(lib_dir)
    if apk_dir.is_dir() and list(apk_dir.glob("*.apk")):
        click.echo(f"Android APKs already present at {apk_dir}")
        return

    # Get version from loaded module or fallback to RDOC_TAG
    from rdc.discover import find_renderdoc

    rd = find_renderdoc()
    if rd is not None and hasattr(rd, "GetVersionString"):
        version = rd.GetVersionString().lstrip("v")
    else:
        version = RDOC_TAG.lstrip("v")

    download_android_apks(version, lib_dir)
    click.echo("Android APKs installed.")
