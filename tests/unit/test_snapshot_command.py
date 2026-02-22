"""Tests for rdc snapshot CLI command."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from rdc.cli import main
from rdc.commands import snapshot as snap_mod

_PIPELINE_RESPONSE = {"eid": 142, "row": {"stages": []}}

_SHADER_ALL_RESPONSE = {
    "eid": 142,
    "stages": [
        {"stage": "vs", "shader": 10, "entry": "main", "ro": 0, "rw": 0, "cbuffers": 1},
        {"stage": "ps", "shader": 20, "entry": "main", "ro": 1, "rw": 0, "cbuffers": 0},
    ],
}

_SHADER_DISASM_VS = {"eid": 142, "stage": "vs", "disasm": "; VS disassembly\nmov r0, r1"}
_SHADER_DISASM_PS = {"eid": 142, "stage": "ps", "disasm": "; PS disassembly\ntex r0, s0"}


def _make_temp_png(tmp_path: Path, name: str) -> str:
    """Create a fake PNG file and return its path string."""
    p = tmp_path / name
    p.write_bytes(b"\x89PNG_fake_" + name.encode())
    return str(p)


def _build_daemon_mock(
    tmp_path: Path,
    *,
    shader_stages: list[dict[str, Any]] | None = None,
    color_targets: int = 1,
    has_depth: bool = True,
) -> Any:
    """Build a mock _daemon_call function with configurable behavior."""
    color_paths = [_make_temp_png(tmp_path, f"tmp_color{i}.png") for i in range(color_targets)]
    depth_path = _make_temp_png(tmp_path, "tmp_depth.png") if has_depth else None

    stages = shader_stages if shader_stages is not None else _SHADER_ALL_RESPONSE["stages"]
    color_call_count = 0

    def fake_daemon_call(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        nonlocal color_call_count
        if method == "pipeline":
            return _PIPELINE_RESPONSE
        if method == "shader_all":
            return {"eid": 142, "stages": stages}
        if method == "shader_disasm":
            stage = params["stage"] if params else "vs"
            if stage == "vs":
                return _SHADER_DISASM_VS
            return _SHADER_DISASM_PS
        if method == "rt_export":
            idx = params["target"] if params else 0
            if idx < color_targets:
                color_call_count += 1
                return {"path": color_paths[idx], "size": 100}
            raise SystemExit(1)
        if method == "rt_depth":
            if has_depth and depth_path:
                return {"path": depth_path, "size": 100}
            raise SystemExit(1)
        return {}

    return fake_daemon_call


class TestSnapshotHappyPath:
    def test_all_files_written(self, tmp_path: Path) -> None:
        out_dir = tmp_path / "snap"
        mock = _build_daemon_mock(tmp_path, color_targets=1, has_depth=True)

        with patch.object(snap_mod, "_daemon_call", mock):
            result = CliRunner().invoke(main, ["snapshot", "142", "-o", str(out_dir)])

        assert result.exit_code == 0
        assert (out_dir / "pipeline.json").exists()
        assert json.loads((out_dir / "pipeline.json").read_text()) == _PIPELINE_RESPONSE
        assert (out_dir / "shader_vs.txt").exists()
        assert (out_dir / "shader_ps.txt").exists()
        assert "VS disassembly" in (out_dir / "shader_vs.txt").read_text()
        assert (out_dir / "color0.png").exists()
        assert (out_dir / "depth.png").exists()

        manifest = json.loads((out_dir / "manifest.json").read_text())
        assert manifest["eid"] == 142
        assert len(manifest["files"]) == 5
        assert "pipeline.json" in manifest["files"]
        assert "timestamp" in manifest

    def test_output_dir_created(self, tmp_path: Path) -> None:
        out_dir = tmp_path / "a" / "b" / "c"
        mock = _build_daemon_mock(tmp_path, color_targets=0, has_depth=False, shader_stages=[])

        with patch.object(snap_mod, "_daemon_call", mock):
            result = CliRunner().invoke(main, ["snapshot", "142", "-o", str(out_dir)])

        assert result.exit_code == 0
        assert out_dir.is_dir()
        assert (out_dir / "pipeline.json").exists()

    def test_json_output(self, tmp_path: Path) -> None:
        out_dir = tmp_path / "snap"
        mock = _build_daemon_mock(tmp_path, color_targets=1, has_depth=True)

        with patch.object(snap_mod, "_daemon_call", mock):
            result = CliRunner().invoke(main, ["snapshot", "142", "-o", str(out_dir), "--json"])

        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["eid"] == 142
        assert "files" in parsed
        assert "timestamp" in parsed


class TestSnapshotPartialFailures:
    def test_no_shaders(self, tmp_path: Path) -> None:
        out_dir = tmp_path / "snap"
        mock = _build_daemon_mock(tmp_path, shader_stages=[], color_targets=1, has_depth=True)

        with patch.object(snap_mod, "_daemon_call", mock):
            result = CliRunner().invoke(main, ["snapshot", "142", "-o", str(out_dir)])

        assert result.exit_code == 0
        assert not list(out_dir.glob("shader_*.txt"))
        manifest = json.loads((out_dir / "manifest.json").read_text())
        assert not any(f.startswith("shader_") for f in manifest["files"])

    def test_no_color_targets(self, tmp_path: Path) -> None:
        out_dir = tmp_path / "snap"
        mock = _build_daemon_mock(tmp_path, color_targets=0, has_depth=True)

        with patch.object(snap_mod, "_daemon_call", mock):
            result = CliRunner().invoke(main, ["snapshot", "142", "-o", str(out_dir)])

        assert result.exit_code == 0
        assert not list(out_dir.glob("color*.png"))
        manifest = json.loads((out_dir / "manifest.json").read_text())
        assert not any(f.startswith("color") for f in manifest["files"])

    def test_no_depth(self, tmp_path: Path) -> None:
        out_dir = tmp_path / "snap"
        mock = _build_daemon_mock(tmp_path, color_targets=1, has_depth=False)

        with patch.object(snap_mod, "_daemon_call", mock):
            result = CliRunner().invoke(main, ["snapshot", "142", "-o", str(out_dir)])

        assert result.exit_code == 0
        assert not (out_dir / "depth.png").exists()
        manifest = json.loads((out_dir / "manifest.json").read_text())
        assert "depth.png" not in manifest["files"]

    def test_multiple_color_targets(self, tmp_path: Path) -> None:
        out_dir = tmp_path / "snap"
        mock = _build_daemon_mock(tmp_path, color_targets=3, has_depth=True)

        with patch.object(snap_mod, "_daemon_call", mock):
            result = CliRunner().invoke(main, ["snapshot", "142", "-o", str(out_dir)])

        assert result.exit_code == 0
        assert (out_dir / "color0.png").exists()
        assert (out_dir / "color1.png").exists()
        assert (out_dir / "color2.png").exists()
        assert not (out_dir / "color3.png").exists()
        manifest = json.loads((out_dir / "manifest.json").read_text())
        color_files = [f for f in manifest["files"] if f.startswith("color")]
        assert len(color_files) == 3


class TestSnapshotFatalFailures:
    def test_pipeline_fails(self, tmp_path: Path) -> None:
        out_dir = tmp_path / "snap"

        def fail_pipeline(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
            raise SystemExit(1)

        with patch.object(snap_mod, "_daemon_call", fail_pipeline):
            result = CliRunner().invoke(main, ["snapshot", "142", "-o", str(out_dir)])

        assert result.exit_code == 1

    def test_no_session(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        out_dir = tmp_path / "snap"
        monkeypatch.setattr("rdc.commands._helpers.load_session", lambda: None)

        result = CliRunner().invoke(main, ["snapshot", "142", "-o", str(out_dir)])

        assert result.exit_code == 1
        assert "no active session" in result.output


class TestSnapshotCLI:
    def test_help_shows_snapshot(self) -> None:
        result = CliRunner().invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "snapshot" in result.output
