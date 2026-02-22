"""Tests for rdc mesh CLI command and OBJ formatter."""

from __future__ import annotations

import json
from typing import Any

from click.testing import CliRunner

from rdc.cli import main
from rdc.commands.mesh import _format_obj, _generate_faces, mesh_cmd

_MESH_RESPONSE: dict[str, Any] = {
    "eid": 142,
    "stage": "vs-out",
    "topology": "TriangleList",
    "vertex_count": 3,
    "comp_count": 4,
    "stride": 16,
    "vertices": [[0.0, 0.5, 0.0, 1.0], [-0.5, -0.5, 0.0, 1.0], [0.5, -0.5, 0.0, 1.0]],
    "index_count": 0,
    "indices": [],
}


class TestMeshCmd:
    def test_mesh_default_obj(self, monkeypatch: Any) -> None:
        monkeypatch.setattr("rdc.commands.mesh._daemon_call", lambda m, p: _MESH_RESPONSE)
        runner = CliRunner()
        result = runner.invoke(mesh_cmd, [])
        assert result.exit_code == 0
        lines = result.output.strip().split("\n")
        assert lines[0].startswith("# rdc mesh export:")
        v_lines = [ln for ln in lines if ln.startswith("v ")]
        f_lines = [ln for ln in lines if ln.startswith("f ")]
        assert len(v_lines) == 3
        assert len(f_lines) == 1
        assert "f 1 2 3" in result.output

    def test_mesh_json_output(self, monkeypatch: Any) -> None:
        monkeypatch.setattr("rdc.commands.mesh._daemon_call", lambda m, p: dict(_MESH_RESPONSE))
        runner = CliRunner()
        result = runner.invoke(mesh_cmd, ["--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["vertices"] == _MESH_RESPONSE["vertices"]
        assert data["faces"] == [[0, 1, 2]]
        assert data["face_count"] == 1

    def test_mesh_file_output(self, monkeypatch: Any, tmp_path: Any) -> None:
        monkeypatch.setattr("rdc.commands.mesh._daemon_call", lambda m, p: _MESH_RESPONSE)
        out = tmp_path / "mesh.obj"
        runner = CliRunner()
        result = runner.invoke(mesh_cmd, ["-o", str(out)])
        assert result.exit_code == 0
        assert out.exists()
        content = out.read_text()
        assert "v 0.000000 0.500000 0.000000" in content
        assert "f 1 2 3" in content
        assert "3 vertices" in result.output  # stderr summary

    def test_mesh_no_header(self, monkeypatch: Any) -> None:
        monkeypatch.setattr("rdc.commands.mesh._daemon_call", lambda m, p: _MESH_RESPONSE)
        runner = CliRunner()
        result = runner.invoke(mesh_cmd, ["--no-header"])
        assert result.exit_code == 0
        lines = result.output.strip().split("\n")
        assert not any(ln.startswith("#") for ln in lines)
        assert lines[0].startswith("v ")

    def test_mesh_stage_forwarded(self, monkeypatch: Any) -> None:
        calls: list[tuple[str, dict[str, Any]]] = []

        def mock_call(method: str, params: dict[str, Any]) -> dict[str, Any]:
            calls.append((method, params))
            return _MESH_RESPONSE

        monkeypatch.setattr("rdc.commands.mesh._daemon_call", mock_call)
        runner = CliRunner()
        result = runner.invoke(mesh_cmd, ["--stage", "gs-out"])
        assert result.exit_code == 0
        assert calls[0][1]["stage"] == "gs-out"

    def test_mesh_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(mesh_cmd, ["--help"])
        assert result.exit_code == 0
        assert "EID" in result.output
        assert "--stage" in result.output
        assert "-o" in result.output

    def test_mesh_in_main_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert "mesh" in result.output


class TestObjFormatter:
    def test_obj_triangle_list_faces(self) -> None:
        faces = _generate_faces(6, [], "TriangleList")
        assert len(faces) == 2
        assert faces[0] == [0, 1, 2]
        assert faces[1] == [3, 4, 5]

    def test_obj_triangle_strip_faces(self) -> None:
        faces = _generate_faces(4, [], "TriangleStrip")
        assert len(faces) == 2
        # even: [0,1,2], odd: [2,1,3] (swapped winding)
        assert faces[0] == [0, 1, 2]
        assert faces[1] == [2, 1, 3]

    def test_obj_triangle_fan_faces(self) -> None:
        faces = _generate_faces(4, [], "TriangleFan")
        assert len(faces) == 2
        assert all(f[0] == 0 for f in faces)
        assert faces[0] == [0, 1, 2]
        assert faces[1] == [0, 2, 3]

    def test_obj_point_list_no_faces(self) -> None:
        faces = _generate_faces(5, [], "PointList")
        assert faces == []
        obj = _format_obj(
            [(0.0, 0.0, 0.0)] * 5,
            faces,
            eid=1,
            stage="vs-out",
            topology="PointList",
        )
        assert "f " not in obj

    def test_obj_1_indexed(self) -> None:
        positions = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]
        faces = [[0, 1, 2]]
        obj = _format_obj(
            positions,
            faces,
            eid=1,
            stage="vs-out",
            topology="TriangleList",
        )
        assert "f 1 2 3" in obj
        assert "f 0" not in obj

    def test_obj_indexed_mesh(self) -> None:
        # 4 vertices, 6 indices forming 2 triangles (shared vertices)
        faces = _generate_faces(4, [0, 1, 2, 0, 2, 3], "TriangleList")
        assert len(faces) == 2
        assert faces[0] == [0, 1, 2]
        assert faces[1] == [0, 2, 3]
