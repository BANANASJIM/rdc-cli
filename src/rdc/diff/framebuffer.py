"""Framebuffer pixel-level comparison between two captures."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import UnidentifiedImageError

from rdc.image_compare import compare_images
from rdc.services.diff_service import DiffContext, query_both, query_each_sync


@dataclass(frozen=True)
class FramebufferDiffResult:
    """Result of comparing framebuffer exports from two captures."""

    identical: bool
    diff_pixels: int
    total_pixels: int
    diff_ratio: float
    diff_image: Path | None
    eid: int | None
    target: int


def _extract_path(resp: dict[str, Any] | None, label: str) -> tuple[str | None, str]:
    """Extract export path from daemon response.

    Returns:
        (path, error). path is None on failure.
    """
    if resp is None:
        return None, f"rt_export failed: daemon {label} returned no response"
    result = resp.get("result")
    if not isinstance(result, dict) or "path" not in result:
        return None, f"rt_export failed: daemon {label} missing path in response"
    return result["path"], ""


def _extract_last_draw_eid(resp: dict[str, Any] | None) -> int | None:
    """Return the highest EID from a draws response, or None."""
    if resp is None:
        return None
    draws = resp.get("result", {}).get("draws", [])
    if not draws:
        return None
    eids = [d["eid"] for d in draws if "eid" in d]
    return int(max(eids)) if eids else None


def compare_framebuffers(
    ctx: DiffContext,
    *,
    target: int = 0,
    threshold: float = 0.0,
    eid: int | None = None,
    diff_output: Path | None = None,
    timeout_s: float = 30.0,
) -> tuple[FramebufferDiffResult | None, str]:
    """Compare framebuffer exports from two captures.

    Args:
        ctx: Active diff session context.
        target: Color target index.
        threshold: Max diff ratio (%) to still count as identical.
        eid: EID to compare at (None = daemon default = last event).
        diff_output: If set, write diff visualization PNG here.
        timeout_s: RPC timeout in seconds.

    Returns:
        (FramebufferDiffResult, "") on success, (None, error_message) on failure.
    """
    params: dict[str, Any] = {"target": target}
    if eid is not None:
        params["eid"] = eid
        resp_a, resp_b, qb_err = query_both(ctx, "rt_export", params, timeout_s=timeout_s)
    else:
        # Resolve per-daemon last-draw EIDs
        draws_a, draws_b, draws_err = query_both(ctx, "draws", {}, timeout_s=timeout_s)
        if draws_err:
            return None, f"cannot resolve default EID: {draws_err}"

        last_a = _extract_last_draw_eid(draws_a)
        last_b = _extract_last_draw_eid(draws_b)

        if last_a is None and last_b is None:
            return None, "cannot resolve default EID: no draws found"

        eid_a = last_a if last_a is not None else last_b
        eid_b = last_b if last_b is not None else last_a
        eid = eid_a  # for result reporting

        params_a = {"target": target, "eid": eid_a}
        params_b = {"target": target, "eid": eid_b}
        out_a, out_b, qb_err = query_each_sync(
            ctx,
            [("rt_export", params_a)],
            [("rt_export", params_b)],
            timeout_s=timeout_s,
        )
        resp_a, resp_b = out_a[0], out_b[0]

    if qb_err:
        return None, f"rt_export failed: {qb_err}"

    path_a, err_a = _extract_path(resp_a, "A")
    if path_a is None:
        return None, err_a

    path_b, err_b = _extract_path(resp_b, "B")
    if path_b is None:
        return None, err_b

    try:
        cmp = compare_images(Path(path_a), Path(path_b), threshold, diff_output)
    except ValueError as exc:
        return None, str(exc)
    except FileNotFoundError as exc:
        return None, f"export file not found: {exc}"
    except UnidentifiedImageError as exc:
        return None, f"invalid image: {exc}"

    return FramebufferDiffResult(
        identical=cmp.identical,
        diff_pixels=cmp.diff_pixels,
        total_pixels=cmp.total_pixels,
        diff_ratio=cmp.diff_ratio,
        diff_image=cmp.diff_image,
        eid=eid,
        target=target,
    ), ""
