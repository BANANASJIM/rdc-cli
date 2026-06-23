from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from rdc._build_renderdoc import RDOC_TAG, SWIG_SHA256

# Build files that pin the renderdoc git tag.
_RENDERDOC_TAG_FILES = (
    "src/rdc/_build_renderdoc.py",
    "docker/Dockerfile",
    "aur/PKGBUILD",
    "aur/stable/PKGBUILD",
    "scripts/build-renderdoc.sh",
    "scripts/setup-renderdoc.sh",
)

# Build files that fetch and sha256-verify the SWIG fork archive.
# Excludes docker/Dockerfile (does not fetch the SWIG fork) and
# scripts/setup-renderdoc.sh (fetches but does not verify a sha256).
_SWIG_SHA_FILES = (
    "src/rdc/_build_renderdoc.py",
    "aur/PKGBUILD",
    "aur/stable/PKGBUILD",
    "scripts/build-renderdoc.sh",
)


@pytest.mark.skipif(sys.platform == "win32", reason="bash not available on Windows CI")
def test_build_renderdoc_script_syntax() -> None:
    subprocess.run(["bash", "-n", "scripts/build-renderdoc.sh"], check=True)


def test_build_renderdoc_script_constants() -> None:
    text = Path("scripts/build-renderdoc.sh").read_text()
    assert "set -euo pipefail" in text
    assert "v1.41" in text
    assert "9d7e5013" in text
    assert "RENDERDOC_PYTHON_PATH" in text
    assert "DRENDERDOC_SWIG_PACKAGE" in text


def test_capture_fixture_script_exists() -> None:
    path = Path("scripts/capture_fixture.sh")
    assert path.exists()
    text = path.read_text()
    assert "renderdoccmd capture -c" in text


def test_dockerfile_exists() -> None:
    path = Path("docker/Dockerfile")
    assert path.exists()
    text = path.read_text()
    assert "uv/install.sh" in text


def test_renderdoc_pin_consistency() -> None:
    """Lock the renderdoc tag and SWIG sha to a single source of truth.

    ``_build_renderdoc.py`` is the canonical pin. Every build file that
    references renderdoc must use the same ``RDOC_TAG``, and every file that
    fetches the SWIG fork archive must use the same ``SWIG_SHA256``.
    """
    for rel in _RENDERDOC_TAG_FILES:
        text = Path(rel).read_text()
        assert RDOC_TAG in text, f"{rel} does not pin renderdoc tag {RDOC_TAG}"

    for rel in _SWIG_SHA_FILES:
        text = Path(rel).read_text()
        assert SWIG_SHA256 in text, f"{rel} does not pin SWIG sha256 {SWIG_SHA256}"
