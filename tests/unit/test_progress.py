"""Unit tests for rdc._progress.make_progress_cb."""

from __future__ import annotations

import io
import math
from unittest.mock import patch

from rdc._progress import make_progress_cb


def _run_cb(values: list[float], *, tty: bool, now_seq: list[float] | None = None) -> str:
    """Run callback for each value in values; return stderr output."""
    buf = io.StringIO()
    buf.isatty = lambda: tty  # type: ignore[method-assign]

    idx = [0]

    def _monotonic() -> float:
        v = now_seq[idx[0]] if now_seq else 0.0
        idx[0] = min(idx[0] + 1, len(now_seq) - 1) if now_seq else idx[0]
        return v

    def _echo(msg: object = "", *, nl: bool = True, **kw: object) -> None:
        buf.write(str(msg))
        if nl:
            buf.write("\n")

    with (
        patch("rdc._progress.click.get_text_stream", return_value=buf),
        patch("rdc._progress.click.echo", side_effect=_echo),
        patch("rdc._progress.time.monotonic", side_effect=_monotonic),
    ):
        cb = make_progress_cb("test", min_interval=1.0)
        for v in values:
            cb(v)

    return buf.getvalue()


class TestTtyBranch:
    def test_first_call_emits(self) -> None:
        out = _run_cb([0.0001], tty=True)
        assert "test: 0%" in out

    def test_final_call_emits_newline(self) -> None:
        out = _run_cb([0.0001, 1.0], tty=True)
        assert "test: 100%" in out
        assert "\n" in out

    def test_intermediate_uses_carriage_return(self) -> None:
        out = _run_cb([0.0001, 0.5, 1.0], tty=True)
        assert "\r" in out

    def test_completion_appends_newline_not_cr(self) -> None:
        buf = io.StringIO()
        buf.isatty = lambda: True  # type: ignore[method-assign]
        written: list[str] = []

        def _echo(msg: object = "", **kw: object) -> None:
            written.append(str(msg))

        with (
            patch("rdc._progress.click.get_text_stream", return_value=buf),
            patch("rdc._progress.click.echo", side_effect=_echo),
        ):
            cb = make_progress_cb("x")
            cb(1.0)

        assert "\n" in written
        assert "\r" not in written


class TestNonTtyBranch:
    def test_first_call_always_emits(self) -> None:
        now_seq = [0.0] * 10
        out = _run_cb([0.0001], tty=False, now_seq=now_seq)
        assert "test: 0%" in out

    def test_final_call_always_emits(self) -> None:
        # Use a now_seq that would throttle intermediate calls but still emit final
        now_seq = [0.0, 0.0, 0.0, 0.0]
        out = _run_cb([0.0001, 0.5, 1.0], tty=False, now_seq=now_seq)
        assert "test: 100%" in out

    def test_throttled_by_min_interval(self) -> None:
        # All calls at t=0, so only first call should emit (interval not elapsed)
        now_seq = [0.0] * 20
        out = _run_cb([0.0001, 0.25, 0.5, 0.75], tty=False, now_seq=now_seq)
        # Only first call emits; 0.25/0.5/0.75 are throttled
        count = out.count("test:")
        assert count == 1

    def test_emits_after_interval_elapsed(self) -> None:
        # t advances past min_interval between calls
        now_seq = [0.0, 0.0, 1.5, 1.5, 3.5, 3.5]
        out = _run_cb([0.0001, 0.25, 0.5, 0.75], tty=False, now_seq=now_seq)
        # First call at t=0, next at t=1.5 (elapsed>=1.0), next at t=3.5 (elapsed>=1.0)
        count = out.count("test:")
        assert count >= 2

    def test_uses_newline_not_cr(self) -> None:
        now_seq = [0.0] * 10
        out = _run_cb([0.0001, 1.0], tty=False, now_seq=now_seq)
        assert "\r" not in out
        assert "\n" in out


class TestClamping:
    def _single(self, v: float) -> str:
        return _run_cb([v], tty=False, now_seq=[0.0] * 5)

    def test_nan_clamped_to_zero(self) -> None:
        out = self._single(math.nan)
        assert "0%" in out

    def test_negative_clamped_to_zero(self) -> None:
        out = self._single(-0.5)
        assert "0%" in out

    def test_inf_clamped_to_100(self) -> None:
        out = self._single(math.inf)
        assert "100%" in out

    def test_value_above_1_clamped(self) -> None:
        out = self._single(2.0)
        assert "100%" in out


class TestRepeatedCalls:
    def test_safe_across_multiple_intervals(self) -> None:
        # Ensure callback doesn't crash or break state across many calls
        now_seq = list(range(20))
        out = _run_cb([i / 19 for i in range(20)], tty=False, now_seq=now_seq)
        assert "test:" in out
        assert "100%" in out
