from __future__ import annotations

import click


@click.command("setup-renderdoc")
@click.argument("install_dir", required=False, default=None)
@click.option("--build-dir", default=None, help="Build cache directory.")
@click.option("--version", "rdoc_version", default=None, help="RenderDoc tag to build.")
@click.option("--jobs", type=int, default=None, help="Parallel build jobs.")
def setup_renderdoc_cmd(
    install_dir: str | None,
    build_dir: str | None,
    rdoc_version: str | None,
    jobs: int | None,
) -> None:
    """Build and install the renderdoc Python module from source."""
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
