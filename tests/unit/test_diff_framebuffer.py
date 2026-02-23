"""Tests for diff framebuffer: library + CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

from rdc.commands import diff as diff_mod
from rdc.commands.diff import diff_cmd
from rdc.diff import framebuffer as fb_mod
from rdc.diff.framebuffer import FramebufferDiffResult, compare_framebuffers
from rdc.image_compare import CompareResult
from rdc.services.diff_service import DiffContext


def _make_ctx() -> DiffContext:
    return DiffContext(
        session_id="aabbccddeeff",
        host="127.0.0.1",
        port_a=5000,
        port_b=5001,
        token_a="ta",
        token_b="tb",
        pid_a=100,
        pid_b=200,
        capture_a="a.rdc",
        capture_b="b.rdc",
    )


def _draws_resp(*eids: int) -> dict[str, Any]:
    return {"result": {"draws": [{"eid": e} for e in eids]}}


def _mock_query_both(
    resp_a: dict[str, Any] | None,
    resp_b: dict[str, Any] | None,
    err: str = "",
    *,
    draws_a: dict[str, Any] | None = None,
    draws_b: dict[str, Any] | None = None,
    draws_err: str = "",
) -> Any:
    """Return a mock for query_both that dispatches by method.

    For ``"draws"`` method returns draws_a/draws_b; for everything else
    returns resp_a/resp_b.
    """
    calls: list[tuple[Any, ...]] = []

    def _fn(
        ctx: DiffContext,
        method: str,
        params: dict[str, Any],
        *,
        timeout_s: float = 30.0,
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None, str]:
        calls.append((method, params, timeout_s))
        if method == "draws":
            return draws_a, draws_b, draws_err
        return resp_a, resp_b, err

    _fn.calls = calls  # type: ignore[attr-defined]
    return _fn


def _mock_query_each_sync(
    resp_a: dict[str, Any] | None,
    resp_b: dict[str, Any] | None,
    err: str = "",
) -> Any:
    """Return a mock for query_each_sync that captures call args."""
    calls: list[tuple[Any, ...]] = []

    def _fn(
        ctx: DiffContext,
        calls_a: list[tuple[str, dict[str, Any]]],
        calls_b: list[tuple[str, dict[str, Any]]],
        *,
        timeout_s: float = 30.0,
    ) -> tuple[list[dict[str, Any] | None], list[dict[str, Any] | None], str]:
        calls.append((calls_a, calls_b, timeout_s))
        return [resp_a], [resp_b], err

    _fn.calls = calls  # type: ignore[attr-defined]
    return _fn


def _export_resp(path: str, size: int = 1024) -> dict[str, Any]:
    return {"result": {"path": path, "size": size}}


def _compare_result(
    *,
    identical: bool = True,
    diff_pixels: int = 0,
    total_pixels: int = 16,
    diff_ratio: float = 0.0,
    diff_image: Path | None = None,
) -> CompareResult:
    return CompareResult(
        identical=identical,
        diff_pixels=diff_pixels,
        total_pixels=total_pixels,
        diff_ratio=diff_ratio,
        diff_image=diff_image,
    )


# ============================================================================
# Library tests: compare_framebuffers()
# ============================================================================


def _setup_eid_none_mocks(
    monkeypatch: pytest.MonkeyPatch,
    *,
    draws_a: dict[str, Any] | None = None,
    draws_b: dict[str, Any] | None = None,
    resp_a: dict[str, Any] | None = None,
    resp_b: dict[str, Any] | None = None,
    each_err: str = "",
) -> tuple[Any, Any]:
    """Wire up query_both (draws) + query_each_sync (rt_export) for eid=None tests."""
    if draws_a is None:
        draws_a = _draws_resp(10, 20, 30)
    if draws_b is None:
        draws_b = _draws_resp(10, 20, 30)
    if resp_a is None:
        resp_a = _export_resp("/tmp/a.png")
    if resp_b is None:
        resp_b = _export_resp("/tmp/b.png")

    mock_qb = _mock_query_both(None, None, draws_a=draws_a, draws_b=draws_b)
    mock_qes = _mock_query_each_sync(resp_a, resp_b, each_err)
    monkeypatch.setattr(fb_mod, "query_both", mock_qb)
    monkeypatch.setattr(fb_mod, "query_each_sync", mock_qes)
    return mock_qb, mock_qes


class TestCompareFramebuffersHappy:
    def test_identical_renders(self, monkeypatch: pytest.MonkeyPatch) -> None:
        ctx = _make_ctx()
        _setup_eid_none_mocks(monkeypatch)
        monkeypatch.setattr(fb_mod, "compare_images", lambda *a, **kw: _compare_result())

        result, err = compare_framebuffers(ctx)
        assert err == ""
        assert result is not None
        assert result.identical is True
        assert result.diff_pixels == 0

    def test_different_renders(self, monkeypatch: pytest.MonkeyPatch) -> None:
        ctx = _make_ctx()
        _setup_eid_none_mocks(monkeypatch)
        monkeypatch.setattr(
            fb_mod,
            "compare_images",
            lambda *a, **kw: _compare_result(identical=False, diff_pixels=100, diff_ratio=0.4),
        )

        result, err = compare_framebuffers(ctx)
        assert err == ""
        assert result is not None
        assert result.identical is False
        assert result.diff_pixels == 100

    def test_no_eid_resolves_last_draw(self, monkeypatch: pytest.MonkeyPatch) -> None:
        ctx = _make_ctx()
        mock_qb, mock_qes = _setup_eid_none_mocks(
            monkeypatch,
            draws_a=_draws_resp(10, 50, 30),
            draws_b=_draws_resp(5, 40),
        )
        monkeypatch.setattr(fb_mod, "compare_images", lambda *a, **kw: _compare_result())

        result, err = compare_framebuffers(ctx, eid=None)
        assert err == ""
        assert result is not None
        # Resolved EID = max from daemon A draws = 50
        assert result.eid == 50
        # query_both was called with "draws"
        assert mock_qb.calls[0][0] == "draws"
        # query_each_sync got per-daemon EIDs
        calls_a, calls_b, _ = mock_qes.calls[0]
        assert calls_a[0][1]["eid"] == 50
        assert calls_b[0][1]["eid"] == 40

    def test_explicit_eid(self, monkeypatch: pytest.MonkeyPatch) -> None:
        ctx = _make_ctx()
        mock_qb = _mock_query_both(_export_resp("/tmp/a.png"), _export_resp("/tmp/b.png"))
        monkeypatch.setattr(fb_mod, "query_both", mock_qb)
        monkeypatch.setattr(fb_mod, "compare_images", lambda *a, **kw: _compare_result())

        compare_framebuffers(ctx, eid=50)
        assert mock_qb.calls[0][1]["eid"] == 50

    def test_explicit_eid_skips_draws_query(self, monkeypatch: pytest.MonkeyPatch) -> None:
        ctx = _make_ctx()
        mock_qb = _mock_query_both(_export_resp("/tmp/a.png"), _export_resp("/tmp/b.png"))
        monkeypatch.setattr(fb_mod, "query_both", mock_qb)
        monkeypatch.setattr(fb_mod, "compare_images", lambda *a, **kw: _compare_result())

        compare_framebuffers(ctx, eid=50)
        # Only one call to query_both: rt_export with eid=50, no draws query
        assert len(mock_qb.calls) == 1
        assert mock_qb.calls[0][0] == "rt_export"

    def test_target_forwarded(self, monkeypatch: pytest.MonkeyPatch) -> None:
        ctx = _make_ctx()
        # Use explicit eid to test target forwarding in the simple path
        mock_qb = _mock_query_both(_export_resp("/tmp/a.png"), _export_resp("/tmp/b.png"))
        monkeypatch.setattr(fb_mod, "query_both", mock_qb)
        monkeypatch.setattr(fb_mod, "compare_images", lambda *a, **kw: _compare_result())

        compare_framebuffers(ctx, target=1, eid=1)
        assert mock_qb.calls[0][1]["target"] == 1

    def test_threshold_forwarded(self, monkeypatch: pytest.MonkeyPatch) -> None:
        ctx = _make_ctx()
        mock_qb = _mock_query_both(_export_resp("/tmp/a.png"), _export_resp("/tmp/b.png"))
        monkeypatch.setattr(fb_mod, "query_both", mock_qb)

        captured: list[tuple[Any, ...]] = []

        def mock_compare(
            path_a: Path,
            path_b: Path,
            threshold: float = 0.0,
            diff_output: Path | None = None,
        ) -> CompareResult:
            captured.append((path_a, path_b, threshold, diff_output))
            return _compare_result()

        monkeypatch.setattr(fb_mod, "compare_images", mock_compare)
        compare_framebuffers(ctx, threshold=0.5, eid=1)
        assert captured[0][2] == 0.5

    def test_diff_output_forwarded(self, monkeypatch: pytest.MonkeyPatch) -> None:
        ctx = _make_ctx()
        mock_qb = _mock_query_both(_export_resp("/tmp/a.png"), _export_resp("/tmp/b.png"))
        monkeypatch.setattr(fb_mod, "query_both", mock_qb)

        captured: list[tuple[Any, ...]] = []

        def mock_compare(
            path_a: Path,
            path_b: Path,
            threshold: float = 0.0,
            diff_output: Path | None = None,
        ) -> CompareResult:
            captured.append((path_a, path_b, threshold, diff_output))
            return _compare_result(
                identical=False,
                diff_pixels=5,
                diff_ratio=1.0,
                diff_image=diff_output,
            )

        monkeypatch.setattr(fb_mod, "compare_images", mock_compare)
        result, _ = compare_framebuffers(ctx, diff_output=Path("/tmp/d.png"), eid=1)
        assert captured[0][3] == Path("/tmp/d.png")
        assert result is not None
        assert result.diff_image == Path("/tmp/d.png")

    def test_diff_image_none_when_identical(self, monkeypatch: pytest.MonkeyPatch) -> None:
        ctx = _make_ctx()
        mock_qb = _mock_query_both(_export_resp("/tmp/a.png"), _export_resp("/tmp/b.png"))
        monkeypatch.setattr(fb_mod, "query_both", mock_qb)
        monkeypatch.setattr(
            fb_mod,
            "compare_images",
            lambda *a, **kw: _compare_result(diff_image=None),
        )

        result, _ = compare_framebuffers(ctx, diff_output=Path("/tmp/d.png"), eid=1)
        assert result is not None
        assert result.diff_image is None

    def test_all_fields_populated(self, monkeypatch: pytest.MonkeyPatch) -> None:
        ctx = _make_ctx()
        mock_qb = _mock_query_both(_export_resp("/tmp/a.png"), _export_resp("/tmp/b.png"))
        monkeypatch.setattr(fb_mod, "query_both", mock_qb)
        monkeypatch.setattr(
            fb_mod,
            "compare_images",
            lambda *a, **kw: _compare_result(
                identical=False,
                diff_pixels=100,
                total_pixels=1000,
                diff_ratio=10.0,
            ),
        )

        result, err = compare_framebuffers(ctx, target=2, eid=50)
        assert err == ""
        assert result is not None
        assert result.eid == 50
        assert result.target == 2
        assert result.total_pixels == 1000
        assert result.diff_ratio == 10.0

    def test_only_one_daemon_has_draws(self, monkeypatch: pytest.MonkeyPatch) -> None:
        ctx = _make_ctx()
        mock_qb, mock_qes = _setup_eid_none_mocks(
            monkeypatch,
            draws_a=_draws_resp(10, 50),
            draws_b={"result": {"draws": []}},
        )
        monkeypatch.setattr(fb_mod, "compare_images", lambda *a, **kw: _compare_result())

        result, err = compare_framebuffers(ctx, eid=None)
        assert err == ""
        assert result is not None
        # Both should use daemon A's last draw EID as fallback
        calls_a, calls_b, _ = mock_qes.calls[0]
        assert calls_a[0][1]["eid"] == 50
        assert calls_b[0][1]["eid"] == 50

    def test_no_draws_returns_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        ctx = _make_ctx()
        _setup_eid_none_mocks(
            monkeypatch,
            draws_a={"result": {"draws": []}},
            draws_b={"result": {"draws": []}},
        )

        result, err = compare_framebuffers(ctx, eid=None)
        assert result is None
        assert "cannot resolve default EID" in err


class TestCompareFramebuffersErrors:
    def test_daemon_a_fails(self, monkeypatch: pytest.MonkeyPatch) -> None:
        ctx = _make_ctx()
        mock_qb = _mock_query_both(None, _export_resp("/tmp/b.png"))
        monkeypatch.setattr(fb_mod, "query_both", mock_qb)

        result, err = compare_framebuffers(ctx, eid=1)
        assert result is None
        assert "rt_export failed" in err
        assert "daemon A" in err

    def test_daemon_b_fails(self, monkeypatch: pytest.MonkeyPatch) -> None:
        ctx = _make_ctx()
        mock_qb = _mock_query_both(_export_resp("/tmp/a.png"), None)
        monkeypatch.setattr(fb_mod, "query_both", mock_qb)

        result, err = compare_framebuffers(ctx, eid=1)
        assert result is None
        assert "rt_export failed" in err
        assert "daemon B" in err

    def test_both_daemons_fail(self, monkeypatch: pytest.MonkeyPatch) -> None:
        ctx = _make_ctx()
        mock_qb = _mock_query_both(None, None, err="both daemons failed")
        monkeypatch.setattr(fb_mod, "query_both", mock_qb)

        result, err = compare_framebuffers(ctx, eid=1)
        assert result is None
        assert "rt_export failed" in err
        assert "both daemons failed" in err

    def test_size_mismatch(self, monkeypatch: pytest.MonkeyPatch) -> None:
        ctx = _make_ctx()
        mock_qb = _mock_query_both(_export_resp("/tmp/a.png"), _export_resp("/tmp/b.png"))
        monkeypatch.setattr(fb_mod, "query_both", mock_qb)

        def bad_compare(*_a: Any, **_kw: Any) -> CompareResult:
            raise ValueError("size mismatch: (640, 480) vs (320, 240)")

        monkeypatch.setattr(fb_mod, "compare_images", bad_compare)
        result, err = compare_framebuffers(ctx, eid=1)
        assert result is None
        assert "size mismatch" in err

    def test_file_not_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        ctx = _make_ctx()
        mock_qb = _mock_query_both(_export_resp("/tmp/a.png"), _export_resp("/tmp/b.png"))
        monkeypatch.setattr(fb_mod, "query_both", mock_qb)

        def bad_compare(*_a: Any, **_kw: Any) -> CompareResult:
            raise FileNotFoundError("/tmp/a.png")

        monkeypatch.setattr(fb_mod, "compare_images", bad_compare)
        result, err = compare_framebuffers(ctx, eid=1)
        assert result is None
        assert "export file not found" in err

    def test_invalid_image(self, monkeypatch: pytest.MonkeyPatch) -> None:
        ctx = _make_ctx()
        mock_qb = _mock_query_both(_export_resp("/tmp/a.png"), _export_resp("/tmp/b.png"))
        monkeypatch.setattr(fb_mod, "query_both", mock_qb)

        from PIL import UnidentifiedImageError

        def bad_compare(*_a: Any, **_kw: Any) -> CompareResult:
            raise UnidentifiedImageError("/tmp/a.png")

        monkeypatch.setattr(fb_mod, "compare_images", bad_compare)
        result, err = compare_framebuffers(ctx, eid=1)
        assert result is None
        assert "invalid image" in err


# ============================================================================
# CLI tests: diff --framebuffer
# ============================================================================


def _setup_cli(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    fb_result: FramebufferDiffResult | None = None,
    fb_err: str = "",
) -> tuple[Path, Path]:
    """Set up CLI mocks and return (capture_a, capture_b) paths."""
    a = tmp_path / "a.rdc"
    b = tmp_path / "b.rdc"
    a.touch()
    b.touch()

    ctx = _make_ctx()
    monkeypatch.setattr(diff_mod, "start_diff_session", lambda *a, **kw: (ctx, ""))
    monkeypatch.setattr(diff_mod, "stop_diff_session", lambda c: None)
    monkeypatch.setattr(
        diff_mod,
        "compare_framebuffers",
        lambda *a, **kw: (fb_result, fb_err),
    )
    return a, b


class TestCliFramebufferOutput:
    def test_identical_text(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        fb = FramebufferDiffResult(
            identical=True,
            diff_pixels=0,
            total_pixels=16,
            diff_ratio=0.0,
            diff_image=None,
            eid=None,
            target=0,
        )
        a, b = _setup_cli(monkeypatch, tmp_path, fb_result=fb)
        result = CliRunner().invoke(diff_cmd, [str(a), str(b), "--framebuffer"])
        assert result.exit_code == 0
        assert "identical" in result.output

    def test_different_text(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        fb = FramebufferDiffResult(
            identical=False,
            diff_pixels=1234,
            total_pixels=307200,
            diff_ratio=0.40,
            diff_image=None,
            eid=247,
            target=0,
        )
        a, b = _setup_cli(monkeypatch, tmp_path, fb_result=fb)
        result = CliRunner().invoke(diff_cmd, [str(a), str(b), "--framebuffer"])
        assert result.exit_code == 1
        assert "diff: 1234/307200 pixels (0.40%)" in result.output

    def test_eid_info_printed(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        fb = FramebufferDiffResult(
            identical=True,
            diff_pixels=0,
            total_pixels=16,
            diff_ratio=0.0,
            diff_image=None,
            eid=50,
            target=0,
        )
        a, b = _setup_cli(monkeypatch, tmp_path, fb_result=fb)
        result = CliRunner().invoke(diff_cmd, [str(a), str(b), "--framebuffer"])
        assert "eid=50" in result.output

    def test_diff_output_shown(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        fb = FramebufferDiffResult(
            identical=False,
            diff_pixels=10,
            total_pixels=100,
            diff_ratio=10.0,
            diff_image=Path("/tmp/d.png"),
            eid=None,
            target=0,
        )
        a, b = _setup_cli(monkeypatch, tmp_path, fb_result=fb)
        result = CliRunner().invoke(diff_cmd, [str(a), str(b), "--framebuffer"])
        assert "diff image: /tmp/d.png" in result.output

    def test_no_diff_output_line(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        fb = FramebufferDiffResult(
            identical=True,
            diff_pixels=0,
            total_pixels=16,
            diff_ratio=0.0,
            diff_image=None,
            eid=None,
            target=0,
        )
        a, b = _setup_cli(monkeypatch, tmp_path, fb_result=fb)
        result = CliRunner().invoke(diff_cmd, [str(a), str(b), "--framebuffer"])
        assert "diff image:" not in result.output

    def test_json_identical(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        import json

        fb = FramebufferDiffResult(
            identical=True,
            diff_pixels=0,
            total_pixels=16,
            diff_ratio=0.0,
            diff_image=None,
            eid=None,
            target=0,
        )
        a, b = _setup_cli(monkeypatch, tmp_path, fb_result=fb)
        result = CliRunner().invoke(diff_cmd, [str(a), str(b), "--framebuffer", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["identical"] is True

    def test_json_different(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        import json

        fb = FramebufferDiffResult(
            identical=False,
            diff_pixels=100,
            total_pixels=1000,
            diff_ratio=10.0,
            diff_image=Path("/tmp/d.png"),
            eid=50,
            target=2,
        )
        a, b = _setup_cli(monkeypatch, tmp_path, fb_result=fb)
        result = CliRunner().invoke(diff_cmd, [str(a), str(b), "--framebuffer", "--json"])
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["diff_pixels"] == 100
        assert data["diff_ratio"] == 10.0
        assert data["eid"] == 50
        assert data["target"] == 2
        assert "threshold" in data

    def test_json_diff_image_null(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        import json

        fb = FramebufferDiffResult(
            identical=True,
            diff_pixels=0,
            total_pixels=16,
            diff_ratio=0.0,
            diff_image=None,
            eid=None,
            target=0,
        )
        a, b = _setup_cli(monkeypatch, tmp_path, fb_result=fb)
        result = CliRunner().invoke(diff_cmd, [str(a), str(b), "--framebuffer", "--json"])
        data = json.loads(result.output)
        assert data["diff_image"] is None

    def test_error_exit_2(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        a, b = _setup_cli(monkeypatch, tmp_path, fb_result=None, fb_err="size mismatch: bad")
        result = CliRunner().invoke(diff_cmd, [str(a), str(b), "--framebuffer"])
        assert result.exit_code == 2
        assert "size mismatch" in result.output

    def test_framebuffer_not_stub(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        fb = FramebufferDiffResult(
            identical=True,
            diff_pixels=0,
            total_pixels=16,
            diff_ratio=0.0,
            diff_image=None,
            eid=None,
            target=0,
        )
        a, b = _setup_cli(monkeypatch, tmp_path, fb_result=fb)
        result = CliRunner().invoke(diff_cmd, [str(a), str(b), "--framebuffer"])
        assert "not yet implemented" not in result.output


class TestCliOptionForwarding:
    def test_target_forwarded(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        a = tmp_path / "a.rdc"
        b = tmp_path / "b.rdc"
        a.touch()
        b.touch()

        ctx = _make_ctx()
        monkeypatch.setattr(diff_mod, "start_diff_session", lambda *a, **kw: (ctx, ""))
        monkeypatch.setattr(diff_mod, "stop_diff_session", lambda c: None)

        captured: list[dict[str, Any]] = []

        def mock_compare(
            ctx: Any,
            *,
            target: int = 0,
            threshold: float = 0.0,
            eid: int | None = None,
            diff_output: Path | None = None,
            timeout_s: float = 30.0,
        ) -> tuple[FramebufferDiffResult | None, str]:
            captured.append(
                {
                    "target": target,
                    "threshold": threshold,
                    "eid": eid,
                    "diff_output": diff_output,
                }
            )
            fb = FramebufferDiffResult(
                identical=True,
                diff_pixels=0,
                total_pixels=16,
                diff_ratio=0.0,
                diff_image=None,
                eid=eid,
                target=target,
            )
            return fb, ""

        monkeypatch.setattr(diff_mod, "compare_framebuffers", mock_compare)

        CliRunner().invoke(diff_cmd, [str(a), str(b), "--framebuffer", "--target", "2"])
        assert captured[0]["target"] == 2

    def test_threshold_forwarded(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        a = tmp_path / "a.rdc"
        b = tmp_path / "b.rdc"
        a.touch()
        b.touch()

        ctx = _make_ctx()
        monkeypatch.setattr(diff_mod, "start_diff_session", lambda *a, **kw: (ctx, ""))
        monkeypatch.setattr(diff_mod, "stop_diff_session", lambda c: None)

        captured: list[dict[str, Any]] = []

        def mock_compare(
            ctx: Any,
            *,
            target: int = 0,
            threshold: float = 0.0,
            eid: int | None = None,
            diff_output: Path | None = None,
            timeout_s: float = 30.0,
        ) -> tuple[FramebufferDiffResult | None, str]:
            captured.append({"threshold": threshold})
            return FramebufferDiffResult(
                identical=True,
                diff_pixels=0,
                total_pixels=16,
                diff_ratio=0.0,
                diff_image=None,
                eid=None,
                target=0,
            ), ""

        monkeypatch.setattr(diff_mod, "compare_framebuffers", mock_compare)

        CliRunner().invoke(diff_cmd, [str(a), str(b), "--framebuffer", "--threshold", "1.5"])
        assert captured[0]["threshold"] == 1.5

    def test_eid_forwarded(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        a = tmp_path / "a.rdc"
        b = tmp_path / "b.rdc"
        a.touch()
        b.touch()

        ctx = _make_ctx()
        monkeypatch.setattr(diff_mod, "start_diff_session", lambda *a, **kw: (ctx, ""))
        monkeypatch.setattr(diff_mod, "stop_diff_session", lambda c: None)

        captured: list[dict[str, Any]] = []

        def mock_compare(
            ctx: Any,
            *,
            target: int = 0,
            threshold: float = 0.0,
            eid: int | None = None,
            diff_output: Path | None = None,
            timeout_s: float = 30.0,
        ) -> tuple[FramebufferDiffResult | None, str]:
            captured.append({"eid": eid})
            return FramebufferDiffResult(
                identical=True,
                diff_pixels=0,
                total_pixels=16,
                diff_ratio=0.0,
                diff_image=None,
                eid=eid,
                target=0,
            ), ""

        monkeypatch.setattr(diff_mod, "compare_framebuffers", mock_compare)

        CliRunner().invoke(diff_cmd, [str(a), str(b), "--framebuffer", "--eid", "100"])
        assert captured[0]["eid"] == 100

    def test_diff_output_forwarded(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        a = tmp_path / "a.rdc"
        b = tmp_path / "b.rdc"
        a.touch()
        b.touch()

        ctx = _make_ctx()
        monkeypatch.setattr(diff_mod, "start_diff_session", lambda *a, **kw: (ctx, ""))
        monkeypatch.setattr(diff_mod, "stop_diff_session", lambda c: None)

        captured: list[dict[str, Any]] = []

        def mock_compare(
            ctx: Any,
            *,
            target: int = 0,
            threshold: float = 0.0,
            eid: int | None = None,
            diff_output: Path | None = None,
            timeout_s: float = 30.0,
        ) -> tuple[FramebufferDiffResult | None, str]:
            captured.append({"diff_output": diff_output})
            return FramebufferDiffResult(
                identical=True,
                diff_pixels=0,
                total_pixels=16,
                diff_ratio=0.0,
                diff_image=None,
                eid=None,
                target=0,
            ), ""

        monkeypatch.setattr(diff_mod, "compare_framebuffers", mock_compare)

        CliRunner().invoke(
            diff_cmd,
            [str(a), str(b), "--framebuffer", "--diff-output", "/tmp/d.png"],
        )
        assert captured[0]["diff_output"] == Path("/tmp/d.png")

    def test_no_eid_forwards_none(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        a = tmp_path / "a.rdc"
        b = tmp_path / "b.rdc"
        a.touch()
        b.touch()

        ctx = _make_ctx()
        monkeypatch.setattr(diff_mod, "start_diff_session", lambda *a, **kw: (ctx, ""))
        monkeypatch.setattr(diff_mod, "stop_diff_session", lambda c: None)

        captured: list[dict[str, Any]] = []

        def mock_compare(
            ctx: Any,
            *,
            target: int = 0,
            threshold: float = 0.0,
            eid: int | None = None,
            diff_output: Path | None = None,
            timeout_s: float = 30.0,
        ) -> tuple[FramebufferDiffResult | None, str]:
            captured.append({"eid": eid})
            return FramebufferDiffResult(
                identical=True,
                diff_pixels=0,
                total_pixels=16,
                diff_ratio=0.0,
                diff_image=None,
                eid=None,
                target=0,
            ), ""

        monkeypatch.setattr(diff_mod, "compare_framebuffers", mock_compare)

        CliRunner().invoke(diff_cmd, [str(a), str(b), "--framebuffer"])
        assert captured[0]["eid"] is None
