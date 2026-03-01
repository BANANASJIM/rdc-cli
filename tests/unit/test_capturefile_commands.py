"""Tests for CaptureFile CLI commands."""

from __future__ import annotations

import base64
from pathlib import Path

from click.testing import CliRunner
from conftest import assert_json_output, patch_cli_session

from rdc.commands.capturefile import (
    callstacks_cmd,
    gpus_cmd,
    section_cmd,
    sections_cmd,
    thumbnail_cmd,
)

# ---------------------------------------------------------------------------
# thumbnail
# ---------------------------------------------------------------------------


def test_thumbnail_cmd(monkeypatch) -> None:
    patch_cli_session(monkeypatch, {"data": "AQID", "width": 4, "height": 4})
    result = CliRunner().invoke(thumbnail_cmd, [])
    assert result.exit_code == 0
    assert "4x4" in result.output


def test_thumbnail_cmd_output(monkeypatch, tmp_path) -> None:
    patch_cli_session(monkeypatch, {"data": "AQID", "width": 4, "height": 4})
    out = tmp_path / "thumb.png"
    result = CliRunner().invoke(thumbnail_cmd, ["-o", str(out)])
    assert result.exit_code == 0
    assert out.read_bytes() == b"\x01\x02\x03"
    assert "thumbnail saved:" in result.output


def test_thumbnail_cmd_json(monkeypatch) -> None:
    patch_cli_session(monkeypatch, {"data": "AQID", "width": 4, "height": 4})
    result = CliRunner().invoke(thumbnail_cmd, ["--json"])
    data = assert_json_output(result)
    assert data["width"] == 4


# ---------------------------------------------------------------------------
# gpus
# ---------------------------------------------------------------------------


def _gpu_entry() -> dict:
    return {"name": "RTX 4090", "vendor": 0x10DE, "deviceID": 0, "driver": "535"}


def test_gpus_cmd(monkeypatch) -> None:
    patch_cli_session(monkeypatch, {"gpus": [_gpu_entry()]})
    result = CliRunner().invoke(gpus_cmd, [])
    assert result.exit_code == 0
    assert "RTX 4090" in result.output


def test_gpus_cmd_json(monkeypatch) -> None:
    patch_cli_session(monkeypatch, {"gpus": [_gpu_entry()]})
    result = CliRunner().invoke(gpus_cmd, ["--json"])
    data = assert_json_output(result)
    assert len(data["gpus"]) == 1


def test_gpus_cmd_empty(monkeypatch) -> None:
    patch_cli_session(monkeypatch, {"gpus": []})
    result = CliRunner().invoke(gpus_cmd, [])
    assert result.exit_code == 0
    assert "no GPUs found" in result.output


# ---------------------------------------------------------------------------
# sections
# ---------------------------------------------------------------------------


def test_sections_cmd(monkeypatch) -> None:
    section = {
        "index": 0,
        "name": "FrameCapture",
        "type": 1,
        "version": "",
        "compressedSize": 0,
        "uncompressedSize": 1024,
    }
    patch_cli_session(monkeypatch, {"sections": [section]})
    result = CliRunner().invoke(sections_cmd, [])
    assert result.exit_code == 0
    assert "FrameCapture" in result.output


def test_sections_cmd_empty(monkeypatch) -> None:
    patch_cli_session(monkeypatch, {"sections": []})
    result = CliRunner().invoke(sections_cmd, [])
    assert result.exit_code == 0
    assert "no sections" in result.output


# ---------------------------------------------------------------------------
# section
# ---------------------------------------------------------------------------


def test_section_cmd(monkeypatch) -> None:
    resp = {"name": "Notes", "contents": "hello world", "encoding": "utf-8"}
    patch_cli_session(monkeypatch, resp)
    result = CliRunner().invoke(section_cmd, ["Notes"])
    assert result.exit_code == 0
    assert "hello world" in result.output


def test_section_cmd_json(monkeypatch) -> None:
    resp = {"name": "Notes", "contents": "hello world", "encoding": "utf-8"}
    patch_cli_session(monkeypatch, resp)
    result = CliRunner().invoke(section_cmd, ["Notes", "--json"])
    data = assert_json_output(result)
    assert data["encoding"] == "utf-8"


# ---------------------------------------------------------------------------
# section --write
# ---------------------------------------------------------------------------


def test_section_write_file(monkeypatch, tmp_path: Path) -> None:
    """T-5C-26: write a text file to a section."""
    f = tmp_path / "notes.txt"
    f.write_bytes(b"hello world")
    patch_cli_session(monkeypatch, {"name": "MyNotes", "bytes": 11})
    result = CliRunner().invoke(section_cmd, ["MyNotes", "--write", str(f)])
    assert result.exit_code == 0
    assert "written" in result.output


def test_section_write_binary(monkeypatch, tmp_path: Path) -> None:
    """T-5C-27: write binary file."""
    f = tmp_path / "data.bin"
    f.write_bytes(b"\xff\xfe\x00\x01")
    # Capture send_request args
    calls: list[dict] = []
    import rdc.commands._helpers as mod

    session = type("S", (), {"host": "127.0.0.1", "port": 1, "token": "tok"})()
    monkeypatch.setattr(mod, "load_session", lambda: session)

    def _spy(_h, _p, payload, **kw):
        calls.append(payload)
        return {"result": {"name": "BinData", "bytes": 4}}

    monkeypatch.setattr(mod, "send_request", _spy)
    result = CliRunner().invoke(section_cmd, ["BinData", "--write", str(f)])
    assert result.exit_code == 0
    sent_data = calls[0]["params"]["data"]
    assert base64.b64decode(sent_data) == b"\xff\xfe\x00\x01"


def test_section_write_json(monkeypatch, tmp_path: Path) -> None:
    """T-5C-28: --json on write emits JSON."""
    import json as _json

    f = tmp_path / "notes.txt"
    f.write_bytes(b"hello")
    patch_cli_session(monkeypatch, {"name": "MyNotes", "bytes": 5})
    result = CliRunner().invoke(section_cmd, ["MyNotes", "--write", str(f), "--json"])
    assert result.exit_code == 0
    # stdout has confirmation on stderr + JSON; extract JSON line
    json_lines = [ln for ln in result.output.splitlines() if ln.startswith("{")]
    assert json_lines, "no JSON line in output"
    data = _json.loads(json_lines[0])
    assert data["name"] == "MyNotes"
    assert data["bytes"] == 5


def test_section_write_file_not_found(monkeypatch) -> None:
    """T-5C-29: write file does not exist."""
    patch_cli_session(monkeypatch, {"name": "X", "bytes": 0})
    result = CliRunner().invoke(section_cmd, ["MyNotes", "--write", "/nonexistent/path.txt"])
    assert result.exit_code != 0


def test_section_write_no_session(monkeypatch, tmp_path: Path) -> None:
    """T-5C-30: no active session."""
    f = tmp_path / "x.txt"
    f.write_bytes(b"x")
    patch_cli_session(monkeypatch, None)
    result = CliRunner().invoke(
        section_cmd,
        ["MyNotes", "--write", str(f)],
        catch_exceptions=False,
    )
    assert result.exit_code == 1
    assert "no active session" in result.output


def test_section_write_daemon_error(monkeypatch, tmp_path: Path) -> None:
    """T-5C-31: daemon refuses write."""
    f = tmp_path / "x.txt"
    f.write_bytes(b"x")
    import rdc.commands._helpers as mod

    session = type("S", (), {"host": "127.0.0.1", "port": 1, "token": "tok"})()
    monkeypatch.setattr(mod, "load_session", lambda: session)
    monkeypatch.setattr(
        mod,
        "send_request",
        lambda _h, _p, _payload, **kw: {
            "error": {"code": -32602, "message": "cannot overwrite built-in section 'FrameCapture'"}
        },
    )
    result = CliRunner().invoke(
        section_cmd,
        ["FrameCapture", "--write", str(f)],
        catch_exceptions=False,
    )
    assert result.exit_code == 1


def test_section_read_unchanged(monkeypatch) -> None:
    """T-5C-32: read path unchanged without --write."""
    resp = {"name": "Notes", "contents": "hi", "encoding": "utf-8"}
    patch_cli_session(monkeypatch, resp)
    result = CliRunner().invoke(section_cmd, ["Notes"])
    assert result.exit_code == 0
    assert "hi" in result.output


def test_section_write_zero_byte(monkeypatch, tmp_path: Path) -> None:
    """T-5C-46: zero-byte file."""
    f = tmp_path / "empty.txt"
    f.write_bytes(b"")
    calls: list[dict] = []
    import rdc.commands._helpers as mod

    session = type("S", (), {"host": "127.0.0.1", "port": 1, "token": "tok"})()
    monkeypatch.setattr(mod, "load_session", lambda: session)

    def _spy(_h, _p, payload, **kw):
        calls.append(payload)
        return {"result": {"name": "EmptySection", "bytes": 0}}

    monkeypatch.setattr(mod, "send_request", _spy)
    result = CliRunner().invoke(section_cmd, ["EmptySection", "--write", str(f)])
    assert result.exit_code == 0
    assert calls[0]["params"]["data"] == ""


# ---------------------------------------------------------------------------
# callstacks
# ---------------------------------------------------------------------------


def test_callstacks_tsv(monkeypatch) -> None:
    """T-5C-20: default TSV output."""
    resp = {
        "eid": 0,
        "frames": [
            {"function": "main", "file": "app.c", "line": 10},
            {"function": "draw", "file": "render.c", "line": 55},
        ],
    }
    patch_cli_session(monkeypatch, resp)
    result = CliRunner().invoke(callstacks_cmd, [])
    assert result.exit_code == 0
    assert "main" in result.output
    assert "app.c" in result.output
    assert "10" in result.output
    assert "function\tfile\tline" in result.output


def test_callstacks_json(monkeypatch) -> None:
    """T-5C-21: --json flag."""
    resp = {
        "eid": 0,
        "frames": [{"function": "main", "file": "app.c", "line": 10}],
    }
    patch_cli_session(monkeypatch, resp)
    result = CliRunner().invoke(callstacks_cmd, ["--json"])
    data = assert_json_output(result)
    assert data["frames"][0]["function"] == "main"


def test_callstacks_eid(monkeypatch) -> None:
    """T-5C-22: --eid flag passes eid to daemon."""
    calls: list[dict] = []
    import rdc.commands._helpers as mod

    session = type("S", (), {"host": "127.0.0.1", "port": 1, "token": "tok"})()
    monkeypatch.setattr(mod, "load_session", lambda: session)

    def _spy(_h, _p, payload, **kw):
        calls.append(payload)
        return {"result": {"eid": 42, "frames": []}}

    monkeypatch.setattr(mod, "send_request", _spy)
    result = CliRunner().invoke(callstacks_cmd, ["--eid", "42"])
    assert result.exit_code == 0
    assert calls[0]["params"]["eid"] == 42


def test_callstacks_empty(monkeypatch) -> None:
    """T-5C-23: empty frames list."""
    patch_cli_session(monkeypatch, {"eid": 0, "frames": []})
    result = CliRunner().invoke(callstacks_cmd, [])
    assert result.exit_code == 0
    assert "no frames" in result.output


def test_callstacks_no_session(monkeypatch) -> None:
    """T-5C-24: no active session."""
    patch_cli_session(monkeypatch, None)
    result = CliRunner().invoke(callstacks_cmd, [], catch_exceptions=False)
    assert result.exit_code == 1
    assert "no active session" in result.output


def test_callstacks_daemon_error(monkeypatch) -> None:
    """T-5C-25: daemon returns error."""
    import rdc.commands._helpers as mod

    session = type("S", (), {"host": "127.0.0.1", "port": 1, "token": "tok"})()
    monkeypatch.setattr(mod, "load_session", lambda: session)
    monkeypatch.setattr(
        mod,
        "send_request",
        lambda _h, _p, _payload, **kw: {
            "error": {"code": -32002, "message": "no callstacks in capture"}
        },
    )
    result = CliRunner().invoke(callstacks_cmd, [], catch_exceptions=False)
    assert result.exit_code == 1


def test_callstacks_eid_non_integer(monkeypatch) -> None:
    """T-5C-44: non-integer eid value."""
    patch_cli_session(monkeypatch, {"eid": 0, "frames": []})
    result = CliRunner().invoke(callstacks_cmd, ["--eid", "abc"])
    assert result.exit_code == 2
