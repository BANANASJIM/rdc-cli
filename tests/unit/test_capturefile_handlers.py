"""Tests for CaptureFile daemon handlers."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

import mock_renderdoc as mock_rd
import pytest
from conftest import make_daemon_state


def _make_state(tmp_path: Path) -> Any:
    cap = mock_rd.MockCaptureFile()
    cap.OpenFile(str(tmp_path / "test.rdc"), "", None)
    return make_daemon_state(tmp_path=tmp_path, rd=mock_rd, cap=cap)


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
    state = make_daemon_state(tmp_path=tmp_path, rd=mock_rd)
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


# ---------------------------------------------------------------------------
# callstack_resolve
# ---------------------------------------------------------------------------


def _make_callstack_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    has_callstacks: bool = True,
    callstack_addrs: list[int] | None = None,
    resolve_strings: list[str] | None = None,
) -> Any:
    """Build a state with callstack support configured."""
    state = _make_state(tmp_path)
    state.cap._has_callstacks = has_callstacks
    if callstack_addrs is not None:
        assert state.adapter is not None
        state.adapter.controller.GetCallstack = lambda eid: callstack_addrs  # type: ignore[union-attr]
    if resolve_strings is not None:
        monkeypatch.setattr(
            state.cap,
            "GetResolve",
            lambda cs: resolve_strings,
        )
    return state


def test_callstack_resolve_no_cap(tmp_path: Path) -> None:
    """T-5C-07: no capture open."""
    state = make_daemon_state(tmp_path=tmp_path, rd=mock_rd)
    resp = _handle("callstack_resolve", {}, state)
    assert resp["error"]["code"] == -32002


def test_callstack_resolve_no_callstacks(tmp_path: Path) -> None:
    """T-5C-03: capture has no callstacks."""
    state = _make_state(tmp_path)
    resp = _handle("callstack_resolve", {}, state)
    assert resp["error"]["code"] == -32002
    assert "no callstacks" in resp["error"]["message"].lower()


def test_callstack_resolve_init_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T-5C-04: InitResolver returns falsy."""
    state = _make_state(tmp_path)
    state.cap._has_callstacks = True
    monkeypatch.setattr(state.cap, "InitResolver", lambda **_kw: False)
    resp = _handle("callstack_resolve", {}, state)
    assert resp["error"]["code"] == -32002
    assert "symbols" in resp["error"]["message"].lower()


def test_callstack_resolve_init_raises(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T-5C-04 variant: InitResolver raises."""
    state = _make_state(tmp_path)
    state.cap._has_callstacks = True

    def _raise(**_kw: Any) -> bool:
        raise RuntimeError("no PDB")

    monkeypatch.setattr(state.cap, "InitResolver", _raise)
    resp = _handle("callstack_resolve", {}, state)
    assert resp["error"]["code"] == -32002
    assert "symbols" in resp["error"]["message"].lower()


def test_callstack_resolve_default_eid(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T-5C-01: defaults to current_eid, resolve with mock frames."""
    state = _make_callstack_state(
        tmp_path,
        monkeypatch,
        callstack_addrs=[0x1000],
        resolve_strings=["main app.c:10"],
    )
    resp = _handle("callstack_resolve", {}, state)
    r = resp["result"]
    assert r["eid"] == 0
    assert len(r["frames"]) == 1
    assert r["frames"][0]["function"] == "main"
    assert r["frames"][0]["file"] == "app.c"
    assert r["frames"][0]["line"] == 10


def test_callstack_resolve_specific_eid(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T-5C-02: specific EID with two frames."""
    state = _make_callstack_state(
        tmp_path,
        monkeypatch,
        callstack_addrs=[0x1000, 0x2000],
        resolve_strings=["draw render.c:55", "main app.c:10"],
    )
    resp = _handle("callstack_resolve", {"eid": 42}, state)
    r = resp["result"]
    assert r["eid"] == 42
    assert len(r["frames"]) == 2
    assert r["frames"][0]["function"] == "draw"


def test_callstack_resolve_eid_out_of_range(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T-5C-05: EID exceeds max_eid."""
    state = _make_callstack_state(tmp_path, monkeypatch)
    resp = _handle("callstack_resolve", {"eid": 9999}, state)
    assert resp["error"]["code"] == -32602


def test_callstack_resolve_eid_negative(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T-5C-06: negative EID."""
    state = _make_callstack_state(tmp_path, monkeypatch)
    resp = _handle("callstack_resolve", {"eid": -1}, state)
    assert resp["error"]["code"] == -32602


def test_callstack_resolve_empty_frames(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T-5C-08: GetResolve returns empty list."""
    state = _make_callstack_state(
        tmp_path,
        monkeypatch,
        callstack_addrs=[],
    )
    resp = _handle("callstack_resolve", {}, state)
    r = resp["result"]
    assert r["frames"] == []


def test_callstack_resolve_multi_frame(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T-5C-09: five-frame callstack order preserved."""
    resolve = [f"func{i} file{i}.c:{i * 10}" for i in range(5)]
    state = _make_callstack_state(
        tmp_path,
        monkeypatch,
        callstack_addrs=[i for i in range(5)],
        resolve_strings=resolve,
    )
    resp = _handle("callstack_resolve", {}, state)
    frames = resp["result"]["frames"]
    assert len(frames) == 5
    for i, f in enumerate(frames):
        assert f["function"] == f"func{i}"
        assert f["file"] == f"file{i}.c"
        assert f["line"] == i * 10


def test_callstack_resolve_eid_0(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T-5C-38: EID 0 boundary."""
    state = _make_callstack_state(
        tmp_path,
        monkeypatch,
        callstack_addrs=[0x1],
        resolve_strings=["f file.c:1"],
    )
    resp = _handle("callstack_resolve", {"eid": 0}, state)
    assert resp["result"]["eid"] == 0


def test_callstack_resolve_max_eid(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T-5C-39: max_eid boundary (valid)."""
    state = _make_callstack_state(
        tmp_path,
        monkeypatch,
        callstack_addrs=[0x1],
        resolve_strings=["f file.c:1"],
    )
    resp = _handle("callstack_resolve", {"eid": 100}, state)
    assert "result" in resp


def test_callstack_resolve_max_eid_plus_one(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T-5C-40: max_eid + 1 boundary (invalid)."""
    state = _make_callstack_state(tmp_path, monkeypatch)
    resp = _handle("callstack_resolve", {"eid": 101}, state)
    assert resp["error"]["code"] == -32602


# ---------------------------------------------------------------------------
# section_write
# ---------------------------------------------------------------------------


def test_section_write_new(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T-5C-10: write a new custom section."""
    state = _make_state(tmp_path)
    monkeypatch.setattr(state.cap, "FindSectionByName", lambda n: -1)
    data_b64 = base64.b64encode(b"hello").decode()
    resp = _handle("section_write", {"name": "MyNotes", "data": data_b64}, state)
    r = resp["result"]
    assert r["name"] == "MyNotes"
    assert r["bytes"] == 5
    assert len(state.cap._written_sections) == 1
    assert state.cap._written_sections[0][1] == b"hello"


def test_section_write_binary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T-5C-11: write binary content."""
    state = _make_state(tmp_path)
    monkeypatch.setattr(state.cap, "FindSectionByName", lambda n: -1)
    data_b64 = base64.b64encode(b"\xff\xfe").decode()
    resp = _handle("section_write", {"name": "BinData", "data": data_b64}, state)
    assert resp["result"]["bytes"] == 2
    assert state.cap._written_sections[0][1] == b"\xff\xfe"


def test_section_write_overwrite_user(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T-5C-12: overwrite non-system section."""
    state = _make_state(tmp_path)
    monkeypatch.setattr(state.cap, "FindSectionByName", lambda n: 0)
    monkeypatch.setattr(
        state.cap,
        "GetSectionProperties",
        lambda idx: mock_rd.SectionProperties(name="Notes", type=mock_rd.SectionType.Notes),
    )
    data_b64 = base64.b64encode(b"updated").decode()
    resp = _handle("section_write", {"name": "Notes", "data": data_b64}, state)
    assert resp["result"]["name"] == "Notes"


def test_section_write_reject_system(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T-5C-13: refuse to overwrite FrameCapture."""
    state = _make_state(tmp_path)
    monkeypatch.setattr(state.cap, "FindSectionByName", lambda n: 0)
    monkeypatch.setattr(
        state.cap,
        "GetSectionProperties",
        lambda idx: mock_rd.SectionProperties(
            name="FrameCapture",
            type=mock_rd.SectionType.FrameCapture,
        ),
    )
    data_b64 = base64.b64encode(b"bad").decode()
    resp = _handle("section_write", {"name": "FrameCapture", "data": data_b64}, state)
    assert resp["error"]["code"] == -32602
    assert "built-in" in resp["error"]["message"].lower()
    assert len(state.cap._written_sections) == 0


def test_section_write_missing_name(tmp_path: Path) -> None:
    """T-5C-14: missing name parameter."""
    state = _make_state(tmp_path)
    data_b64 = base64.b64encode(b"x").decode()
    resp = _handle("section_write", {"data": data_b64}, state)
    assert resp["error"]["code"] == -32602


def test_section_write_missing_data(tmp_path: Path) -> None:
    """T-5C-15: missing data parameter."""
    state = _make_state(tmp_path)
    resp = _handle("section_write", {"name": "Notes"}, state)
    assert resp["error"]["code"] == -32602


def test_section_write_invalid_base64(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """T-5C-16: invalid base64 data."""
    state = _make_state(tmp_path)
    monkeypatch.setattr(state.cap, "FindSectionByName", lambda n: -1)
    resp = _handle("section_write", {"name": "Notes", "data": "!!!notbase64!!!"}, state)
    assert resp["error"]["code"] == -32602
    assert "base64" in resp["error"]["message"].lower()


def test_section_write_empty_name(tmp_path: Path) -> None:
    """T-5C-17: empty section name."""
    state = _make_state(tmp_path)
    data_b64 = base64.b64encode(b"x").decode()
    resp = _handle("section_write", {"name": "", "data": data_b64}, state)
    assert resp["error"]["code"] == -32602


def test_section_write_no_cap(tmp_path: Path) -> None:
    """T-5C-18: no capture open."""
    state = make_daemon_state(tmp_path=tmp_path, rd=mock_rd)
    data_b64 = base64.b64encode(b"x").decode()
    resp = _handle("section_write", {"name": "Notes", "data": data_b64}, state)
    assert resp["error"]["code"] == -32002


def test_section_write_api_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T-5C-19: WriteSection raises."""
    state = _make_state(tmp_path)
    monkeypatch.setattr(state.cap, "FindSectionByName", lambda n: -1)

    def _raise(props: Any, data: bytes) -> None:
        raise RuntimeError("disk full")

    monkeypatch.setattr(state.cap, "WriteSection", _raise)
    data_b64 = base64.b64encode(b"x").decode()
    # WriteSection raising should propagate through _process_request
    from rdc.handlers.capturefile import HANDLERS

    with pytest.raises(RuntimeError, match="disk full"):
        HANDLERS["section_write"](1, {"name": "Notes", "data": data_b64}, state)


def test_section_write_empty_data(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T-5C-41: empty data (base64 of empty bytes)."""
    state = _make_state(tmp_path)
    monkeypatch.setattr(state.cap, "FindSectionByName", lambda n: -1)
    resp = _handle("section_write", {"name": "Notes", "data": ""}, state)
    assert resp["result"]["bytes"] == 0
