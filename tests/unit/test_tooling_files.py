from __future__ import annotations

import subprocess
from pathlib import Path


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
