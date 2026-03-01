"""E2E tests for capturefile commands (callstacks, section write).

These are black-box tests that invoke the CLI via subprocess and require
a working renderdoc installation for capture open/replay.
"""

from __future__ import annotations

import base64
import uuid

import pytest
from e2e_helpers import VKCUBE, rdc, rdc_fail, rdc_json, rdc_ok

pytestmark = pytest.mark.gpu


def _uid() -> str:
    return uuid.uuid4().hex[:8]


class TestCallstacks:
    """T-5C-36/37: callstacks on capture without callstack data."""

    def test_callstacks_no_callstacks(self) -> None:
        """``rdc callstacks`` exits 1 on fixture without callstack data."""
        name = f"e2e_cs_{_uid()}"
        try:
            rdc_ok("open", str(VKCUBE), session=name)
            out = rdc_fail("callstacks", session=name, exit_code=1)
            assert "no callstacks" in out.lower()
        finally:
            rdc("close", session=name)

    def test_callstacks_json_no_callstacks(self) -> None:
        """``rdc callstacks --json`` exits 1, no partial JSON."""
        name = f"e2e_csj_{_uid()}"
        try:
            rdc_ok("open", str(VKCUBE), session=name)
            out = rdc_fail("callstacks", "--json", session=name, exit_code=1)
            assert "no callstacks" in out.lower()
        finally:
            rdc("close", session=name)


class TestSectionWrite:
    """T-5C-33/34/35: section write and read-back."""

    def test_write_and_readback(self, tmp_path) -> None:
        """Write a custom section, then read it back."""
        name = f"e2e_sw_{_uid()}"
        note = tmp_path / "notes.txt"
        note.write_text("e2e-round-trip")
        try:
            rdc_ok("open", str(VKCUBE), session=name)
            rdc_ok("section", "MyNotes", "--write", str(note), session=name)
            out = rdc_ok("section", "MyNotes", session=name)
            assert "e2e-round-trip" in out
        finally:
            rdc("close", session=name)

    def test_refuse_system_section(self, tmp_path) -> None:
        """Refuse to overwrite real system section by internal name."""
        name = f"e2e_sws_{_uid()}"
        note = tmp_path / "bad.txt"
        note.write_bytes(b"bad")
        try:
            rdc_ok("open", str(VKCUBE), session=name)
            out = rdc_fail(
                "section",
                "renderdoc/internal/framecapture",
                "--write",
                str(note),
                session=name,
                exit_code=1,
            )
            assert "built-in" in out.lower()
        finally:
            rdc("close", session=name)

    def test_binary_roundtrip(self, tmp_path) -> None:
        """Write binary section and verify base64 round-trip."""
        name = f"e2e_swb_{_uid()}"
        binfile = tmp_path / "data.bin"
        binfile.write_bytes(b"\xde\xad\xbe\xef")
        try:
            rdc_ok("open", str(VKCUBE), session=name)
            rdc_ok("section", "BinSection", "--write", str(binfile), session=name)
            data = rdc_json("section", "BinSection", session=name)
            assert data["encoding"] == "base64"
            assert base64.b64decode(data["contents"]) == b"\xde\xad\xbe\xef"
        finally:
            rdc("close", session=name)
