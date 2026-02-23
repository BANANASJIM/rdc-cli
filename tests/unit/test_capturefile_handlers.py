"""Tests for CaptureFile daemon handlers."""

from __future__ import annotations

import base64
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "mocks"))

import mock_renderdoc as mock_rd  # noqa: E402


def _make_state(tmp_path: Path) -> Any:
    """Build a minimal DaemonState with MockCaptureFile."""
    from types import SimpleNamespace

    cap = mock_rd.MockCaptureFile()
    cap.OpenFile(str(tmp_path / "test.rdc"), "", None)
    return SimpleNamespace(cap=cap, rd=mock_rd, temp_dir=tmp_path)


def _handle(method: str, params: dict[str, Any], state: Any) -> dict[str, Any]:
    """Call a handler by method name."""
    from rdc.handlers.capturefile import HANDLERS

    handler = HANDLERS[method]
    response, _ = handler(1, params, state)
    return response


# ---------------------------------------------------------------------------
# capture_thumbnail
# ---------------------------------------------------------------------------


def test_thumbnail_success(tmp_path: Path) -> None:
    state = _make_state(tmp_path)
    resp = _handle("capture_thumbnail", {}, state)
    r = resp["result"]
    assert len(r["data"]) > 0
    assert r["width"] == 4
    assert r["height"] == 4
    raw = base64.b64decode(r["data"])
    assert len(raw) == 16


def test_thumbnail_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    state = _make_state(tmp_path)
    monkeypatch.setattr(
        state.cap,
        "GetThumbnail",
        lambda ft=0, ms=0: mock_rd.Thumbnail(data=b"", width=0, height=0),
    )
    resp = _handle("capture_thumbnail", {}, state)
    r = resp["result"]
    assert r["data"] == ""
    assert r["width"] == 0
    assert r["height"] == 0


def test_thumbnail_maxsize(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[int, int]] = []

    def _spy(file_type: int = 0, maxsize: int = 0) -> mock_rd.Thumbnail:
        calls.append((file_type, maxsize))
        return mock_rd.Thumbnail(data=b"\x00", width=1, height=1)

    state = _make_state(tmp_path)
    monkeypatch.setattr(state.cap, "GetThumbnail", _spy)
    _handle("capture_thumbnail", {"maxsize": 128}, state)
    assert calls[0][1] == 128


def test_thumbnail_no_cap(tmp_path: Path) -> None:
    from types import SimpleNamespace

    state = SimpleNamespace(cap=None, rd=mock_rd, temp_dir=tmp_path)
    resp = _handle("capture_thumbnail", {}, state)
    assert resp["error"]["code"] == -32002


# ---------------------------------------------------------------------------
# capture_gpus
# ---------------------------------------------------------------------------


def test_gpus_success(tmp_path: Path) -> None:
    state = _make_state(tmp_path)
    resp = _handle("capture_gpus", {}, state)
    gpus = resp["result"]["gpus"]
    assert len(gpus) == 1
    assert "name" in gpus[0]
    assert "vendor" in gpus[0]
    assert "deviceID" in gpus[0]
    assert "driver" in gpus[0]
    assert gpus[0]["name"] == "Mock GPU"


def test_gpus_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    state = _make_state(tmp_path)
    monkeypatch.setattr(state.cap, "GetAvailableGPUs", lambda: [])
    resp = _handle("capture_gpus", {}, state)
    assert resp["result"]["gpus"] == []


# ---------------------------------------------------------------------------
# capture_sections
# ---------------------------------------------------------------------------


def test_sections_success(tmp_path: Path) -> None:
    state = _make_state(tmp_path)
    resp = _handle("capture_sections", {}, state)
    sections = resp["result"]["sections"]
    assert len(sections) == 1
    assert sections[0]["name"] == "FrameCapture"
    assert "type" in sections[0]
    assert "index" in sections[0]


# ---------------------------------------------------------------------------
# capture_section_content
# ---------------------------------------------------------------------------


def test_section_content_text(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    state = _make_state(tmp_path)
    monkeypatch.setattr(state.cap, "FindSectionByName", lambda name: 0 if name == "Notes" else -1)
    monkeypatch.setattr(state.cap, "GetSectionContents", lambda idx: b"hello")
    resp = _handle("capture_section_content", {"name": "Notes"}, state)
    r = resp["result"]
    assert r["contents"] == "hello"
    assert r["encoding"] == "utf-8"


def test_section_content_binary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    state = _make_state(tmp_path)
    monkeypatch.setattr(state.cap, "FindSectionByName", lambda name: 0)
    monkeypatch.setattr(state.cap, "GetSectionContents", lambda idx: b"\xff\xfe")
    resp = _handle("capture_section_content", {"name": "BinData"}, state)
    r = resp["result"]
    assert r["encoding"] == "base64"
    assert base64.b64decode(r["contents"]) == b"\xff\xfe"


def test_section_not_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    state = _make_state(tmp_path)
    monkeypatch.setattr(state.cap, "FindSectionByName", lambda name: -1)
    resp = _handle("capture_section_content", {"name": "NoSuch"}, state)
    assert resp["error"]["code"] == -32002
    assert "not found" in resp["error"]["message"]


def test_section_missing_name(tmp_path: Path) -> None:
    state = _make_state(tmp_path)
    resp = _handle("capture_section_content", {}, state)
    assert resp["error"]["code"] == -32602
