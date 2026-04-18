"""Unit tests for daemon capture handlers."""

from __future__ import annotations

from typing import Any

import pytest

from rdc.capture_core import CaptureResult
from rdc.handlers.capture import HANDLERS


def _run(handler: str, params: dict[str, Any]) -> dict[str, Any]:
    response, running = HANDLERS[handler](1, params, object())
    assert running is True
    assert "result" in response or "error" in response
    return response


class TestCaptureRun:
    def test_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("rdc.handlers.capture.find_renderdoc", lambda: object())
        called: dict[str, Any] = {}

        def fake_execute(*args: Any, **kwargs: Any) -> CaptureResult:
            called.update(kwargs)
            return CaptureResult(success=True, path="/tmp/out.rdc", pid=1234)

        monkeypatch.setattr("rdc.handlers.capture.build_capture_options", lambda _: object())
        monkeypatch.setattr("rdc.handlers.capture.execute_and_capture", fake_execute)
        terminated: list[int] = []
        monkeypatch.setattr(
            "rdc.handlers.capture.terminate_process",
            lambda pid: terminated.append(pid),
        )

        resp = _run(
            "capture_run",
            {
                "app": "/usr/bin/app",
                "args": "--foo",
                "output": "/tmp/out.rdc",
                "opts": {"api_validation": True},
            },
        )
        assert resp["result"]["path"] == "/tmp/out.rdc"
        assert terminated == [1234]
        assert called["args"] == "--foo"


class TestRemoteHandlers:
    def test_remote_capture_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("rdc.handlers.capture.find_renderdoc", lambda: object())

        class DummyRemote:
            def ShutdownConnection(self) -> None:  # noqa: D401,N802
                return None

        def fake_connect(rd: Any, url: str) -> DummyRemote:
            return DummyRemote()

        monkeypatch.setattr("rdc.handlers.capture.connect_remote_server", fake_connect)
        monkeypatch.setattr(
            "rdc.handlers.capture.remote_capture",
            lambda *a, **k: CaptureResult(success=True, path="/tmp/out.rdc"),
        )

        resp = _run(
            "remote_capture_run",
            {
                "host": "127.0.0.1",
                "port": 39920,
                "app": "demo",
                "output": "/tmp/out.rdc",
            },
        )
        assert resp["result"]["path"] == "/tmp/out.rdc"

    def test_remote_connect_missing_renderdoc(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("rdc.handlers.capture.find_renderdoc", lambda: None)
        resp = _run("remote_connect_run", {"host": "host", "port": 39920})
        assert resp["error"]["code"] == -32002

    def test_remote_capture_exception_returns_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("rdc.handlers.capture.find_renderdoc", lambda: object())

        class DummyRemote:
            def ShutdownConnection(self) -> None:  # noqa: D401,N802
                return None

        monkeypatch.setattr(
            "rdc.handlers.capture.connect_remote_server",
            lambda rd, url: DummyRemote(),
        )

        def boom(*args: Any, **kwargs: Any) -> CaptureResult:
            raise RuntimeError("capture failed")

        monkeypatch.setattr("rdc.handlers.capture.remote_capture", boom)
        resp = _run(
            "remote_capture_run",
            {
                "host": "127.0.0.1",
                "port": 39920,
                "app": "demo",
                "output": "/tmp/out.rdc",
            },
        )
        assert resp["error"]["code"] == -32002

    def test_remote_capture_forwards_hint_from_core(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """T24: hint strings produced by remote_capture propagate into the result payload."""
        monkeypatch.setattr("rdc.handlers.capture.find_renderdoc", lambda: object())

        class DummyRemote:
            def ShutdownConnection(self) -> None:  # noqa: D401,N802
                return None

        monkeypatch.setattr(
            "rdc.handlers.capture.connect_remote_server", lambda rd, url: DummyRemote()
        )
        monkeypatch.setattr(
            "rdc.handlers.capture.remote_capture",
            lambda *a, **k: CaptureResult(error="remote inject failed: x -- hint: try foo"),
        )

        resp = _run(
            "remote_capture_run",
            {
                "host": "127.0.0.1",
                "port": 39920,
                "app": "demo",
                "output": "/tmp/out.rdc",
            },
        )
        assert "hint:" in resp["result"]["error"]


class TestRemoteCaptureHandlerStepLabels:
    """T24 group D: exception paths wrap errors with step labels."""

    class _DummyRemote:
        def __init__(self) -> None:
            self.shutdown_count = 0

        def ShutdownConnection(self) -> None:  # noqa: N802
            self.shutdown_count += 1

    def _setup(self, monkeypatch: pytest.MonkeyPatch) -> _DummyRemote:
        monkeypatch.setattr("rdc.handlers.capture.find_renderdoc", lambda: object())
        remote = TestRemoteCaptureHandlerStepLabels._DummyRemote()
        monkeypatch.setattr("rdc.handlers.capture.connect_remote_server", lambda rd, url: remote)
        return remote

    def _params(self) -> dict[str, Any]:
        return {
            "host": "127.0.0.1",
            "port": 39920,
            "app": "demo",
            "output": "/tmp/out.rdc",
        }

    def test_inner_runtime_error_labeled_inject_transfer(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        remote = self._setup(monkeypatch)

        def boom(*a: Any, **k: Any) -> CaptureResult:
            raise RuntimeError("bang")

        monkeypatch.setattr("rdc.handlers.capture.remote_capture", boom)
        resp = _run("remote_capture_run", self._params())
        msg = resp["error"]["message"]
        assert "at step 'inject/transfer'" in msg
        assert "bang" in msg
        assert remote.shutdown_count == 1

    def test_inner_oserror_labeled_inject_transfer(self, monkeypatch: pytest.MonkeyPatch) -> None:
        remote = self._setup(monkeypatch)

        def boom(*a: Any, **k: Any) -> CaptureResult:
            raise OSError("io down")

        monkeypatch.setattr("rdc.handlers.capture.remote_capture", boom)
        resp = _run("remote_capture_run", self._params())
        assert "at step 'inject/transfer'" in resp["error"]["message"]
        assert remote.shutdown_count == 1

    def test_outer_catchall_labels_unknown_step(self, monkeypatch: pytest.MonkeyPatch) -> None:
        remote = self._setup(monkeypatch)

        def boom(*a: Any, **k: Any) -> CaptureResult:
            raise ValueError("unexpected")

        monkeypatch.setattr("rdc.handlers.capture.remote_capture", boom)
        resp = _run("remote_capture_run", self._params())
        msg = resp["error"]["message"]
        assert "at unknown step" in msg
        assert "ValueError" in msg
        assert remote.shutdown_count == 1
