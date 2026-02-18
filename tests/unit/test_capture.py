from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from rdc.commands.capture import capture_cmd


class DummyResult:
    def __init__(self, code: int) -> None:
        self.returncode = code


def test_capture_missing_binary(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr("rdc.commands.capture._find_renderdoccmd", lambda: None)

    result = CliRunner().invoke(capture_cmd, ["--", "./app"])
    assert result.exit_code == 1
    assert "not found" in result.output


def test_capture_passthrough_args(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    captured: dict[str, list[str]] = {}

    def fake_run(argv, check=False):  # type: ignore[no-untyped-def]
        captured["argv"] = argv
        return DummyResult(0)

    monkeypatch.setattr("rdc.commands.capture._find_renderdoccmd", lambda: "/usr/bin/renderdoccmd")
    monkeypatch.setattr("subprocess.run", fake_run)

    result = CliRunner().invoke(capture_cmd, ["--api", "vulkan", "-o", "out.rdc", "--", "./app", "--foo"])
    assert result.exit_code == 0
    assert captured["argv"] == [
        "/usr/bin/renderdoccmd",
        "capture",
        "--opt-api",
        "vulkan",
        "--capture-file",
        str(Path("out.rdc")),
        "./app",
        "--foo",
    ]


def test_capture_propagates_subprocess_error(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr("rdc.commands.capture._find_renderdoccmd", lambda: "/usr/bin/renderdoccmd")
    monkeypatch.setattr("subprocess.run", lambda argv, check=False: DummyResult(42))

    result = CliRunner().invoke(capture_cmd, ["--", "./app"])
    assert result.exit_code == 42
