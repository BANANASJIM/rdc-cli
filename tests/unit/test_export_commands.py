"""Tests for export convenience commands: texture, rt, buffer."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import click.testing

from rdc.commands.export import buffer_cmd, rt_cmd, texture_cmd


def _make_mock_daemon_call(tmp_path: Path):
    """Create a mock _daemon_call that returns leaf_bin for VFS paths."""
    temp_file = tmp_path / "export.bin"
    temp_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

    def mock_call(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if method == "vfs_ls":
            return {"kind": "leaf_bin", "path": params.get("path", "/") if params else "/"}
        return {"path": str(temp_file), "size": temp_file.stat().st_size}

    return mock_call


class TestTextureCmd:
    def test_texture_mip0_output(self, monkeypatch: Any, tmp_path: Path) -> None:
        mock = _make_mock_daemon_call(tmp_path)
        monkeypatch.setattr("rdc.commands.export._daemon_call", mock)
        monkeypatch.setattr("rdc.commands.vfs._daemon_call", mock)
        monkeypatch.setattr("rdc.commands.vfs._stdout_is_tty", lambda: False)
        out_file = tmp_path / "out.png"
        runner = click.testing.CliRunner()
        result = runner.invoke(texture_cmd, ["42", "-o", str(out_file)])
        assert result.exit_code == 0
        assert out_file.exists()

    def test_texture_mip2_path(self, monkeypatch: Any, tmp_path: Path) -> None:
        """--mip 2 should construct path /textures/<id>/mips/2.png."""
        calls: list[tuple[str, dict[str, Any]]] = []

        def mock_call(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
            calls.append((method, dict(params) if params else {}))
            if method == "vfs_ls":
                return {"kind": "leaf_bin", "path": params.get("path", "/") if params else "/"}
            temp = tmp_path / "export.bin"
            temp.write_bytes(b"\x89PNG" + b"\x00" * 50)
            return {"path": str(temp), "size": 54}

        monkeypatch.setattr("rdc.commands.export._daemon_call", mock_call)
        monkeypatch.setattr("rdc.commands.vfs._daemon_call", mock_call)
        monkeypatch.setattr("rdc.commands.vfs._stdout_is_tty", lambda: False)
        out_file = tmp_path / "out.png"
        runner = click.testing.CliRunner()
        result = runner.invoke(texture_cmd, ["42", "--mip", "2", "-o", str(out_file)])
        assert result.exit_code == 0
        vfs_calls = [c for c in calls if c[0] == "vfs_ls"]
        assert any("/textures/42/mips/2.png" in str(c) for c in vfs_calls)

    def test_texture_tty_protection(self, monkeypatch: Any, tmp_path: Path) -> None:
        mock = _make_mock_daemon_call(tmp_path)
        monkeypatch.setattr("rdc.commands.export._daemon_call", mock)
        monkeypatch.setattr("rdc.commands.vfs._daemon_call", mock)
        monkeypatch.setattr("rdc.commands.vfs._stdout_is_tty", lambda: True)
        runner = click.testing.CliRunner()
        result = runner.invoke(texture_cmd, ["42"])
        assert result.exit_code == 1
        assert "binary data" in result.output


class TestRtCmd:
    def test_rt_default_target(self, monkeypatch: Any, tmp_path: Path) -> None:
        calls: list[tuple[str, dict[str, Any]]] = []

        def mock_call(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
            calls.append((method, dict(params) if params else {}))
            if method == "vfs_ls":
                return {"kind": "leaf_bin", "path": params.get("path", "/") if params else "/"}
            temp = tmp_path / "export.bin"
            temp.write_bytes(b"\x89PNG" + b"\x00" * 50)
            return {"path": str(temp), "size": 54}

        monkeypatch.setattr("rdc.commands.export._daemon_call", mock_call)
        monkeypatch.setattr("rdc.commands.vfs._daemon_call", mock_call)
        monkeypatch.setattr("rdc.commands.vfs._stdout_is_tty", lambda: False)
        out_file = tmp_path / "rt.png"
        runner = click.testing.CliRunner()
        result = runner.invoke(rt_cmd, ["100", "-o", str(out_file)])
        assert result.exit_code == 0
        vfs_calls = [c for c in calls if c[0] == "vfs_ls"]
        assert any("/draws/100/targets/color0.png" in str(c) for c in vfs_calls)

    def test_rt_custom_target(self, monkeypatch: Any, tmp_path: Path) -> None:
        calls: list[tuple[str, dict[str, Any]]] = []

        def mock_call(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
            calls.append((method, dict(params) if params else {}))
            if method == "vfs_ls":
                return {"kind": "leaf_bin", "path": params.get("path", "/") if params else "/"}
            temp = tmp_path / "export.bin"
            temp.write_bytes(b"\x89PNG" + b"\x00" * 50)
            return {"path": str(temp), "size": 54}

        monkeypatch.setattr("rdc.commands.export._daemon_call", mock_call)
        monkeypatch.setattr("rdc.commands.vfs._daemon_call", mock_call)
        monkeypatch.setattr("rdc.commands.vfs._stdout_is_tty", lambda: False)
        out_file = tmp_path / "rt.png"
        runner = click.testing.CliRunner()
        result = runner.invoke(rt_cmd, ["100", "--target", "2", "-o", str(out_file)])
        assert result.exit_code == 0
        vfs_calls = [c for c in calls if c[0] == "vfs_ls"]
        assert any("/draws/100/targets/color2.png" in str(c) for c in vfs_calls)


class TestBufferCmd:
    def test_buffer_output(self, monkeypatch: Any, tmp_path: Path) -> None:
        calls: list[tuple[str, dict[str, Any]]] = []

        def mock_call(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
            calls.append((method, dict(params) if params else {}))
            if method == "vfs_ls":
                return {"kind": "leaf_bin", "path": params.get("path", "/") if params else "/"}
            temp = tmp_path / "export.bin"
            temp.write_bytes(b"\xab\xcd" * 50)
            return {"path": str(temp), "size": 100}

        monkeypatch.setattr("rdc.commands.export._daemon_call", mock_call)
        monkeypatch.setattr("rdc.commands.vfs._daemon_call", mock_call)
        monkeypatch.setattr("rdc.commands.vfs._stdout_is_tty", lambda: False)
        out_file = tmp_path / "buf.bin"
        runner = click.testing.CliRunner()
        result = runner.invoke(buffer_cmd, ["7", "-o", str(out_file)])
        assert result.exit_code == 0
        vfs_calls = [c for c in calls if c[0] == "vfs_ls"]
        assert any("/buffers/7/data" in str(c) for c in vfs_calls)

    def test_buffer_pipe_mode(self, monkeypatch: Any, tmp_path: Path) -> None:
        mock = _make_mock_daemon_call(tmp_path)
        monkeypatch.setattr("rdc.commands.export._daemon_call", mock)
        monkeypatch.setattr("rdc.commands.vfs._daemon_call", mock)
        monkeypatch.setattr("rdc.commands.vfs._stdout_is_tty", lambda: False)
        runner = click.testing.CliRunner()
        result = runner.invoke(buffer_cmd, ["7", "--raw"])
        assert result.exit_code == 0


class TestExportErrors:
    def test_daemon_error_propagated(self, monkeypatch: Any) -> None:
        def mock_call(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
            if method == "vfs_ls":
                raise SystemExit(1)
            return {}

        monkeypatch.setattr("rdc.commands.export._daemon_call", mock_call)
        runner = click.testing.CliRunner()
        result = runner.invoke(texture_cmd, ["42", "--raw"])
        assert result.exit_code == 1

    def test_non_binary_node_rejected(self, monkeypatch: Any) -> None:
        def mock_call(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
            if method == "vfs_ls":
                return {"kind": "leaf", "path": "/textures/42/info"}
            return {}

        monkeypatch.setattr("rdc.commands.export._daemon_call", mock_call)
        runner = click.testing.CliRunner()
        result = runner.invoke(texture_cmd, ["42", "--raw"])
        assert result.exit_code == 1
        assert "not a binary node" in result.output
