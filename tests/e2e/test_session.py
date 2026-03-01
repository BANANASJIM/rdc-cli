"""E2E tests for session lifecycle commands.

These are black-box tests that invoke the CLI via subprocess and require
a working renderdoc installation for capture open/replay.
Each test function manages its own session with a unique name.
"""

from __future__ import annotations

import uuid

import pytest
from conftest import HELLO_TRIANGLE, VKCUBE, rdc, rdc_fail, rdc_ok

pytestmark = pytest.mark.gpu


def _uid() -> str:
    """Generate a short unique suffix for session names."""
    return uuid.uuid4().hex[:8]


class TestOpenAndStatus:
    """2.1-2.2: Open a capture and verify status."""

    def test_open_prints_session_path(self) -> None:
        """``rdc open vkcube.rdc`` opens the capture and prints session path."""
        name = f"e2e_open_{_uid()}"
        try:
            out = rdc_ok("open", str(VKCUBE), session=name)
            assert "session:" in out.lower()
        finally:
            rdc("close", session=name)

    def test_status_shows_session_info(self) -> None:
        """``rdc status`` shows session, capture, eid, and daemon info."""
        name = f"e2e_status_{_uid()}"
        try:
            rdc_ok("open", str(VKCUBE), session=name)
            out = rdc_ok("status", session=name)
            assert "session:" in out
            assert "capture:" in out
            assert "current_eid:" in out
            assert "daemon:" in out
        finally:
            rdc("close", session=name)


class TestGoto:
    """2.3-2.7: Navigate to event IDs."""

    def test_goto_eid_1(self) -> None:
        """``rdc goto 1`` sets current_eid to 1."""
        name = f"e2e_goto1_{_uid()}"
        try:
            rdc_ok("open", str(VKCUBE), session=name)
            out = rdc_ok("goto", "1", session=name)
            assert "current_eid set to 1" in out
        finally:
            rdc("close", session=name)

    def test_goto_eid_5(self) -> None:
        """``rdc goto 5`` sets current_eid to 5."""
        name = f"e2e_goto5_{_uid()}"
        try:
            rdc_ok("open", str(VKCUBE), session=name)
            out = rdc_ok("goto", "5", session=name)
            assert "current_eid set to 5" in out
        finally:
            rdc("close", session=name)

    def test_goto_out_of_range(self) -> None:
        """``rdc goto 999`` errors with eid out of range."""
        name = f"e2e_goto999_{_uid()}"
        try:
            rdc_ok("open", str(VKCUBE), session=name)
            out = rdc_fail("goto", "999", session=name, exit_code=1)
            assert "out of range" in out.lower()
        finally:
            rdc("close", session=name)

    def test_goto_negative_with_separator(self) -> None:
        """``rdc goto -- -1`` errors with eid must be >= 0."""
        name = f"e2e_gotoneg_{_uid()}"
        try:
            rdc_ok("open", str(VKCUBE), session=name)
            out = rdc_fail("goto", "--", "-1", session=name, exit_code=1)
            assert "eid must be >= 0" in out.lower()
        finally:
            rdc("close", session=name)

    def test_goto_negative_no_separator(self) -> None:
        """``rdc goto -1`` triggers Click option parsing error (exit 2)."""
        name = f"e2e_gotoclk_{_uid()}"
        try:
            rdc_ok("open", str(VKCUBE), session=name)
            rdc_fail("goto", "-1", session=name, exit_code=2)
        finally:
            rdc("close", session=name)


class TestNamedSessions:
    """2.8-2.10: Named sessions with independent isolation."""

    def test_named_session_lifecycle(self) -> None:
        """Named sessions (--session) provide independent isolation.

        Opens hello_triangle.rdc in a named session, verifies its status
        is independent, then closes only that session.
        """
        primary = f"e2e_primary_{_uid()}"
        secondary = f"e2e_secondary_{_uid()}"
        try:
            # Open vkcube in primary session
            rdc_ok("open", str(VKCUBE), session=primary)

            # Open hello_triangle in secondary session (2.8)
            out = rdc_ok("open", str(HELLO_TRIANGLE), session=secondary)
            assert "session:" in out.lower()

            # Verify secondary status is independent (2.9)
            status = rdc_ok("status", session=secondary)
            assert "hello_triangle" in status.lower()

            # Close secondary only (2.10)
            close_out = rdc_ok("close", session=secondary)
            assert "closed" in close_out.lower()

            # Primary should still be alive
            primary_status = rdc_ok("status", session=primary)
            assert "vkcube" in primary_status.lower()
        finally:
            rdc("close", session=secondary)
            rdc("close", session=primary)


class TestListenMode:
    """2.11: rdc open --listen :0."""

    def test_listen_random_port(self) -> None:
        """``rdc open --listen :0`` prints host, port, and token."""
        name = f"e2e_listen_{_uid()}"
        try:
            out = rdc_ok("open", str(VKCUBE), "--listen", ":0", session=name)
            assert "port:" in out.lower()
            assert "token:" in out.lower()
            assert "connect with:" in out.lower()
        finally:
            rdc("close", session=name)


class TestClose:
    """2.12: rdc close."""

    def test_close_session(self) -> None:
        """``rdc close`` closes the session and reports success."""
        name = f"e2e_close_{_uid()}"
        rdc_ok("open", str(VKCUBE), session=name)
        try:
            out = rdc_ok("close", session=name)
            assert "closed" in out.lower()
            rdc_fail("status", session=name, exit_code=1)
        finally:
            rdc("close", session=name)
