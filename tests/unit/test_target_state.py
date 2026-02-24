"""Tests for target_state persistence module."""

from __future__ import annotations

from pathlib import Path

import pytest

from rdc.target_state import (
    TargetControlState,
    delete_target_state,
    load_latest_target_state,
    load_target_state,
    save_target_state,
)

_SAMPLE = TargetControlState(
    ident=12345,
    target_name="myapp",
    pid=9999,
    api="Vulkan",
    connected_at=1700000000.0,
)


@pytest.fixture(autouse=True)
def _isolate_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("rdc._platform.data_dir", lambda: tmp_path / ".rdc")


def test_save_load() -> None:
    save_target_state(_SAMPLE)
    loaded = load_target_state(12345)
    assert loaded is not None
    assert loaded.ident == 12345
    assert loaded.target_name == "myapp"
    assert loaded.pid == 9999
    assert loaded.api == "Vulkan"
    assert loaded.connected_at == 1700000000.0


def test_load_missing() -> None:
    assert load_target_state(99999) is None


def test_delete(tmp_path: Path) -> None:
    save_target_state(_SAMPLE)
    assert load_target_state(12345) is not None
    delete_target_state(12345)
    assert load_target_state(12345) is None
    state_file = tmp_path / ".rdc" / "target" / "12345.json"
    assert not state_file.exists()


def test_load_latest_picks_most_recent() -> None:
    older = TargetControlState(ident=1, target_name="a", pid=10, api="Vulkan", connected_at=100.0)
    newer = TargetControlState(ident=2, target_name="b", pid=20, api="D3D12", connected_at=200.0)
    save_target_state(older)
    save_target_state(newer)
    latest = load_latest_target_state()
    assert latest is not None
    assert latest.ident == 2
    assert latest.connected_at == 200.0


def test_load_latest_empty_dir() -> None:
    assert load_latest_target_state() is None


def test_corrupt_file(tmp_path: Path) -> None:
    state_dir = tmp_path / ".rdc" / "target"
    state_dir.mkdir(parents=True)
    state_file = state_dir / "12345.json"
    state_file.write_text("{invalid json garbage")
    assert load_target_state(12345) is None
    assert not state_file.exists()
