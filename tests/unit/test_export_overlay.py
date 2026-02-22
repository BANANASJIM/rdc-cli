"""Tests for rdc rt --overlay CLI extension."""

from __future__ import annotations

from typing import Any

import click.testing

from rdc.commands.export import rt_cmd

_OVERLAY_RESPONSE: dict[str, Any] = {
    "path": "/tmp/overlay_wireframe_10.png",
    "size": 19748,
    "overlay": "wireframe",
    "eid": 10,
}


class TestRtOverlay:
    def test_rt_overlay_wireframe(self, monkeypatch: Any) -> None:
        """--overlay wireframe calls rt_overlay daemon method and prints path."""
        calls: list[tuple[str, dict[str, Any]]] = []

        def mock_call(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
            calls.append((method, dict(params) if params else {}))
            return dict(_OVERLAY_RESPONSE)

        monkeypatch.setattr("rdc.commands.export._daemon_call", mock_call)
        runner = click.testing.CliRunner()
        result = runner.invoke(rt_cmd, ["10", "--overlay", "wireframe"])
        assert result.exit_code == 0
        assert len(calls) == 1
        assert calls[0][0] == "rt_overlay"
        assert calls[0][1]["overlay"] == "wireframe"
        assert _OVERLAY_RESPONSE["path"] in result.output

    def test_rt_overlay_with_output(self, monkeypatch: Any) -> None:
        """--overlay with -o copies file and prints summary."""
        copy_calls: list[tuple[str, str]] = []

        def mock_call(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
            return dict(_OVERLAY_RESPONSE)

        def mock_copy2(src: str, dst: str) -> None:
            copy_calls.append((src, dst))

        monkeypatch.setattr("rdc.commands.export._daemon_call", mock_call)
        monkeypatch.setattr("rdc.commands.export.shutil.copy2", mock_copy2)
        runner = click.testing.CliRunner()
        result = runner.invoke(rt_cmd, ["10", "--overlay", "wireframe", "-o", "out.png"])
        assert result.exit_code == 0
        assert len(copy_calls) == 1
        assert copy_calls[0] == (_OVERLAY_RESPONSE["path"], "out.png")
        assert "overlay: wireframe" in result.output
        assert "19748 bytes" in result.output
        assert "out.png" in result.output

    def test_rt_overlay_dimensions(self, monkeypatch: Any) -> None:
        """--width and --height are forwarded to daemon params."""
        calls: list[tuple[str, dict[str, Any]]] = []

        def mock_call(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
            calls.append((method, dict(params) if params else {}))
            return dict(_OVERLAY_RESPONSE)

        monkeypatch.setattr("rdc.commands.export._daemon_call", mock_call)
        runner = click.testing.CliRunner()
        result = runner.invoke(
            rt_cmd, ["--overlay", "wireframe", "--width", "512", "--height", "512"]
        )
        assert result.exit_code == 0
        assert calls[0][1]["width"] == 512
        assert calls[0][1]["height"] == 512

    def test_rt_no_overlay_existing_behavior(self, monkeypatch: Any, tmp_path: Any) -> None:
        """Without --overlay, existing VFS path is used; rt_overlay is never called."""
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
        assert not any(c[0] == "rt_overlay" for c in calls)
        assert any(c[0] == "vfs_ls" for c in calls)

    def test_rt_overlay_help(self) -> None:
        """--help shows --overlay, --width, --height options."""
        runner = click.testing.CliRunner()
        result = runner.invoke(rt_cmd, ["--help"])
        assert result.exit_code == 0
        assert "--overlay" in result.output
        assert "wireframe" in result.output
        assert "--width" in result.output
        assert "--height" in result.output

    def test_rt_overlay_invalid_choice(self) -> None:
        """Invalid overlay name is rejected by Click."""
        runner = click.testing.CliRunner()
        result = runner.invoke(rt_cmd, ["--overlay", "invalid"])
        assert result.exit_code != 0
        assert "Invalid value" in result.output or "invalid choice" in result.output
