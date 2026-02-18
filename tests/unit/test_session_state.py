from __future__ import annotations

import os

from rdc.session_state import is_pid_alive


def test_is_pid_alive_for_current_process() -> None:
    assert is_pid_alive(os.getpid()) is True


def test_is_pid_alive_for_invalid_pid() -> None:
    assert is_pid_alive(-1) is False
