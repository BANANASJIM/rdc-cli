"""Tests for remote_state persistence module."""

from __future__ import annotations

from pathlib import Path

import pytest

from rdc.remote_state import (
    RemoteServerState,
    delete_remote_state,
    load_latest_remote_state,
    load_remote_state,
    save_remote_state,
)

_SAMPLE = RemoteServerState(host="192.168.1.10", port=39920, connected_at=1700000000.0)


@pytest.fixture(autouse=True)
def _isolate_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("rdc._platform.data_dir", lambda: tmp_path / ".rdc")


def test_save_and_load_round_trip() -> None:
    save_remote_state(_SAMPLE)
    loaded = load_remote_state("192.168.1.10", 39920)
    assert loaded is not None
    assert loaded.host == "192.168.1.10"
    assert loaded.port == 39920
    assert loaded.connected_at == 1700000000.0


def test_load_missing_returns_none() -> None:
    assert load_remote_state("unknownhost", 39920) is None


def test_load_corrupt_returns_none(tmp_path: Path) -> None:
    state_dir = tmp_path / ".rdc" / "remote"
    state_dir.mkdir(parents=True)
    state_file = state_dir / "badhost_39920.json"
    state_file.write_text("{invalid json garbage")
    assert load_remote_state("badhost", 39920) is None
    assert not state_file.exists()


def test_delete_removes_file() -> None:
    save_remote_state(_SAMPLE)
    assert load_remote_state("192.168.1.10", 39920) is not None
    delete_remote_state("192.168.1.10", 39920)
    assert load_remote_state("192.168.1.10", 39920) is None
    # Double-delete is no-op
    delete_remote_state("192.168.1.10", 39920)


def test_load_latest_picks_most_recent() -> None:
    older = RemoteServerState(host="host1", port=39920, connected_at=100.0)
    newer = RemoteServerState(host="host2", port=39920, connected_at=200.0)
    save_remote_state(older)
    save_remote_state(newer)
    latest = load_latest_remote_state()
    assert latest is not None
    assert latest.host == "host2"
    assert latest.connected_at == 200.0


def test_load_latest_empty_dir() -> None:
    assert load_latest_remote_state() is None


def test_ipv6_host_sanitized_in_filename(tmp_path: Path) -> None:
    state = RemoteServerState(host="::1", port=39920, connected_at=1700000000.0)
    save_remote_state(state)
    state_dir = tmp_path / ".rdc" / "remote"
    assert (state_dir / "--1_39920.json").exists()
    loaded = load_remote_state("::1", 39920)
    assert loaded is not None
    assert loaded.host == "::1"


def test_save_creates_restricted_permissions(tmp_path: Path) -> None:
    save_remote_state(_SAMPLE)
    state_dir = tmp_path / ".rdc" / "remote"
    state_file = state_dir / "192.168.1.10_39920.json"
    assert state_file.exists()
    assert state_dir.stat().st_mode & 0o777 == 0o700
    assert state_file.stat().st_mode & 0o777 == 0o600
