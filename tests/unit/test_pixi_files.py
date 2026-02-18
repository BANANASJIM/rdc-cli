from __future__ import annotations

from pathlib import Path


def test_pixi_toml_exists_and_has_core_tasks() -> None:
    path = Path("pixi.toml")
    assert path.exists()
    text = path.read_text()
    assert "[tasks]" in text
    assert "check =" in text
    assert "lint =" in text
    assert "typecheck =" in text
    assert "test =" in text
    assert "python" in text
    assert "uv" in text
