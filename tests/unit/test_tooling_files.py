from __future__ import annotations

from pathlib import Path


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
