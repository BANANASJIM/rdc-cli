"""Diff module for draw call comparison between captures."""

from rdc.diff.alignment import DrawRecord, align_draws
from rdc.diff.draws import (
    DiffStatus,
    DrawDiffRow,
    diff_draws,
    render_json,
    render_shortstat,
    render_unified,
)

__all__ = [
    "DrawRecord",
    "DiffStatus",
    "DrawDiffRow",
    "align_draws",
    "diff_draws",
    "render_json",
    "render_shortstat",
    "render_unified",
]
