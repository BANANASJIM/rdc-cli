"""Tests for rdc serve command and helpers."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from rdc.commands.serve import _generate_config, serve_cmd
from rdc.discover import find_renderdoccmd

# ── _generate_config tests ────────────────────────────────────────────


class TestGenerateConfig:
    def test_defaults_four_whitelist_lines(self) -> None:
        cfg = _generate_config(None, no_exec=False)
        lines = cfg.strip().splitlines()
        assert len(lines) == 4
        assert all(line.startswith("whitelist ") for line in lines)
        assert "noexec" not in cfg

    def test_custom_ips(self) -> None:
        cfg = _generate_config(["10.1.0.0/16"], no_exec=False)
        assert "whitelist 10.1.0.0/16" in cfg
        assert cfg.count("whitelist") == 1

    def test_no_exec(self) -> None:
        cfg = _generate_config(None, no_exec=True)
        lines = cfg.strip().splitlines()
        assert lines[-1] == "noexec"

    def test_custom_and_no_exec(self) -> None:
        cfg = _generate_config(["10.1.0.0/16", "172.16.0.0/12"], no_exec=True)
        lines = cfg.strip().splitlines()
        assert lines[0] == "whitelist 10.1.0.0/16"
        assert lines[1] == "whitelist 172.16.0.0/12"
        assert lines[-1] == "noexec"

    def test_ends_with_newline(self) -> None:
        cfg = _generate_config(None, no_exec=False)
        assert cfg.endswith("\n")


# ── find_renderdoccmd tests ───────────────────────────────────────────


class TestFindRenderdoccmd:
    def test_via_which(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("rdc.discover.shutil.which", lambda name: "/usr/bin/renderdoccmd")
        result = find_renderdoccmd()
        assert result == Path("/usr/bin/renderdoccmd")

    def test_not_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("rdc.discover.shutil.which", lambda name: None)
        monkeypatch.setattr("rdc.discover._platform.renderdoccmd_search_paths", lambda: [])
        monkeypatch.delenv("RENDERDOC_PYTHON_PATH", raising=False)
        result = find_renderdoccmd()
        assert result is None

    def test_via_platform_paths(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setattr("rdc.discover.shutil.which", lambda name: None)
        candidate = tmp_path / "renderdoccmd"
        candidate.touch()
        monkeypatch.setattr("rdc.discover._platform.renderdoccmd_search_paths", lambda: [candidate])
        monkeypatch.delenv("RENDERDOC_PYTHON_PATH", raising=False)
        result = find_renderdoccmd()
        assert result == candidate

    def test_via_env_sibling(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setattr("rdc.discover.shutil.which", lambda name: None)
        monkeypatch.setattr("rdc.discover._platform.renderdoccmd_search_paths", lambda: [])
        name = "renderdoccmd.exe" if sys.platform == "win32" else "renderdoccmd"
        (tmp_path / name).touch()
        monkeypatch.setenv("RENDERDOC_PYTHON_PATH", str(tmp_path))
        result = find_renderdoccmd()
        assert result == tmp_path / name

    def test_prefers_which_over_platform(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr("rdc.discover.shutil.which", lambda name: "/usr/bin/renderdoccmd")
        candidate = tmp_path / "renderdoccmd"
        candidate.touch()
        monkeypatch.setattr("rdc.discover._platform.renderdoccmd_search_paths", lambda: [candidate])
        result = find_renderdoccmd()
        assert result == Path("/usr/bin/renderdoccmd")


# ── serve_cmd CLI tests ───────────────────────────────────────────────


def _patch_serve(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Provide standard mocks for serve_cmd tests."""
    monkeypatch.setattr(
        "rdc.commands.serve.find_renderdoccmd",
        lambda: Path("/usr/bin/renderdoccmd"),
    )
    mock_proc = MagicMock()
    mock_proc.pid = 42
    mock_proc.wait.return_value = 0
    mock_proc.returncode = 0
    monkeypatch.setattr("rdc.commands.serve.subprocess.Popen", lambda *a, **kw: mock_proc)
    return mock_proc


class TestServeCmd:
    def test_renderdoccmd_not_found_exits_1(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("rdc.commands.serve.find_renderdoccmd", lambda: None)
        result = CliRunner().invoke(serve_cmd, [])
        assert result.exit_code == 1
        assert "renderdoccmd not found" in result.output

    def test_foreground_waits_for_proc(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_proc = _patch_serve(monkeypatch)
        result = CliRunner().invoke(serve_cmd, [])
        assert result.exit_code == 0
        mock_proc.wait.assert_called_once()

    def test_foreground_nonzero_exit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_proc = _patch_serve(monkeypatch)
        mock_proc.returncode = 1
        result = CliRunner().invoke(serve_cmd, [])
        assert result.exit_code == 1

    def test_daemon_mode_prints_pid(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_proc = _patch_serve(monkeypatch)
        result = CliRunner().invoke(serve_cmd, ["--daemon"])
        assert result.exit_code == 0
        assert "pid: 42" in result.output
        mock_proc.wait.assert_not_called()

    def test_no_exec_in_config(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        _patch_serve(monkeypatch)
        monkeypatch.setattr(
            "rdc.commands.serve._remoteserver_conf_path",
            lambda: tmp_path / "remoteserver.conf",
        )
        CliRunner().invoke(serve_cmd, ["--no-exec", "--daemon"])
        cfg = (tmp_path / "remoteserver.conf").read_text()
        assert "noexec" in cfg

    def test_allow_ips_in_config(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        _patch_serve(monkeypatch)
        monkeypatch.setattr(
            "rdc.commands.serve._remoteserver_conf_path",
            lambda: tmp_path / "remoteserver.conf",
        )
        CliRunner().invoke(serve_cmd, ["--allow-ips", "10.0.0.0/8", "--daemon"])
        cfg = (tmp_path / "remoteserver.conf").read_text()
        assert "whitelist 10.0.0.0/8" in cfg
        assert cfg.count("whitelist") == 1

    def test_help_exits_0(self) -> None:
        result = CliRunner().invoke(serve_cmd, ["--help"])
        assert result.exit_code == 0
        for opt in ("--port", "--host", "--allow-ips", "--no-exec", "--daemon"):
            assert opt in result.output
