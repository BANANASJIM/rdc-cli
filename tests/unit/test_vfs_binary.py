"""Tests for CLI binary delivery: TTY protection, -o, pipe mode."""

from __future__ import annotations

import click.testing

import rdc.commands.vfs as vfs_mod
from rdc.commands.vfs import cat_cmd


def _mock_resolve(handler: str = "tex_export", args: dict | None = None):
    """Return a fake resolve_path function that yields a fixed PathMatch-like object."""
    _args = args or {"id": 42}

    class _Match:
        kind = "leaf_bin"

        def __init__(self):
            self.handler = handler
            self.args = _args

    return lambda _p: _Match()


class TestTTYProtection:
    def test_binary_on_tty_exits_with_hint(self, monkeypatch):
        def mock_call(method, params=None):
            if method == "vfs_ls":
                return {"kind": "leaf_bin", "path": "/textures/42/image.png"}
            return {"path": "/tmp/fake.png", "size": 1024}

        monkeypatch.setattr(vfs_mod, "_daemon_call", mock_call)
        monkeypatch.setattr(vfs_mod, "resolve_path", _mock_resolve())
        monkeypatch.setattr(vfs_mod, "_stdout_is_tty", lambda: True)

        runner = click.testing.CliRunner()
        result = runner.invoke(cat_cmd, ["/textures/42/image.png"])
        assert result.exit_code == 1
        assert "binary data" in result.output

    def test_binary_on_tty_with_raw_flag(self, monkeypatch, tmp_path):
        temp_file = tmp_path / "test.png"
        temp_file.write_bytes(b"\x89PNG_fake_data")

        def mock_call(method, params=None):
            if method == "vfs_ls":
                return {"kind": "leaf_bin", "path": "/textures/42/image.png"}
            return {"path": str(temp_file), "size": temp_file.stat().st_size}

        monkeypatch.setattr(vfs_mod, "_daemon_call", mock_call)
        monkeypatch.setattr(vfs_mod, "resolve_path", _mock_resolve())
        monkeypatch.setattr(vfs_mod, "_stdout_is_tty", lambda: True)

        runner = click.testing.CliRunner()
        result = runner.invoke(cat_cmd, ["/textures/42/image.png", "--raw"])
        assert result.exit_code == 0


class TestOutputDelivery:
    def test_output_option_moves_file(self, monkeypatch, tmp_path):
        temp_file = tmp_path / "temp.png"
        temp_file.write_bytes(b"\x89PNG_data")
        out_file = tmp_path / "output.png"

        def mock_call(method, params=None):
            if method == "vfs_ls":
                return {"kind": "leaf_bin", "path": "/textures/42/image.png"}
            return {"path": str(temp_file), "size": temp_file.stat().st_size}

        monkeypatch.setattr(vfs_mod, "_daemon_call", mock_call)
        monkeypatch.setattr(vfs_mod, "resolve_path", _mock_resolve())

        runner = click.testing.CliRunner()
        result = runner.invoke(cat_cmd, ["/textures/42/image.png", "-o", str(out_file)])
        assert result.exit_code == 0
        assert out_file.exists()
        assert out_file.read_bytes() == b"\x89PNG_data"
        assert not temp_file.exists()  # moved, not copied

    def test_pipe_delivery_writes_stdout(self, monkeypatch, tmp_path):
        temp_file = tmp_path / "temp.png"
        temp_file.write_bytes(b"\x89PNG_data")

        def mock_call(method, params=None):
            if method == "vfs_ls":
                return {"kind": "leaf_bin", "path": "/textures/42/image.png"}
            return {"path": str(temp_file), "size": temp_file.stat().st_size}

        monkeypatch.setattr(vfs_mod, "_daemon_call", mock_call)
        monkeypatch.setattr(vfs_mod, "resolve_path", _mock_resolve())

        runner = click.testing.CliRunner()
        # CliRunner isatty=False by default, so pipe mode works
        result = runner.invoke(cat_cmd, ["/textures/42/image.png"])
        assert result.exit_code == 0

    def test_pipe_delivery_deletes_temp(self, monkeypatch, tmp_path):
        temp_file = tmp_path / "temp.png"
        temp_file.write_bytes(b"\x89PNG_data")

        def mock_call(method, params=None):
            if method == "vfs_ls":
                return {"kind": "leaf_bin", "path": "/textures/42/image.png"}
            return {"path": str(temp_file), "size": temp_file.stat().st_size}

        monkeypatch.setattr(vfs_mod, "_daemon_call", mock_call)
        monkeypatch.setattr(vfs_mod, "resolve_path", _mock_resolve())

        runner = click.testing.CliRunner()
        result = runner.invoke(cat_cmd, ["/textures/42/image.png"])
        assert result.exit_code == 0
        assert not temp_file.exists()


class TestBinaryErrors:
    def test_handler_returns_no_path(self, monkeypatch):
        def mock_call(method, params=None):
            if method == "vfs_ls":
                return {"kind": "leaf_bin", "path": "/textures/42/image.png"}
            return {"size": 0}

        monkeypatch.setattr(vfs_mod, "_daemon_call", mock_call)
        monkeypatch.setattr(vfs_mod, "resolve_path", _mock_resolve())

        runner = click.testing.CliRunner()
        # CliRunner isatty=False, so no TTY block; but handler returns no path
        result = runner.invoke(cat_cmd, ["/textures/42/image.png"])
        assert result.exit_code == 1
        assert "handler did not return file path" in result.output

    def test_temp_file_missing(self, monkeypatch):
        def mock_call(method, params=None):
            if method == "vfs_ls":
                return {"kind": "leaf_bin", "path": "/textures/42/image.png"}
            return {"path": "/tmp/nonexistent_file_xyz.png", "size": 0}

        monkeypatch.setattr(vfs_mod, "_daemon_call", mock_call)
        monkeypatch.setattr(vfs_mod, "resolve_path", _mock_resolve())

        runner = click.testing.CliRunner()
        result = runner.invoke(cat_cmd, ["/textures/42/image.png"])
        assert result.exit_code == 1
        assert "temp file missing" in result.output
