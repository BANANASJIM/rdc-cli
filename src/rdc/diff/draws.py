"""Draw call comparison and output renderers."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from enum import Enum

from rdc.diff.alignment import DrawRecord, align_draws, has_markers, make_fallback_keys


class DiffStatus(str, Enum):
    """Status for a draw call diff row."""

    EQUAL = "="
    MODIFIED = "~"
    ADDED = "+"
    DELETED = "-"


@dataclass
class DrawDiffRow:
    """One row of draw call diff output."""

    status: DiffStatus
    eid_a: int | None
    eid_b: int | None
    marker: str
    draw_type: str
    triangles_a: int | None
    triangles_b: int | None
    instances_a: int | None
    instances_b: int | None
    confidence: str


def compare_draw_pair(a: DrawRecord | None, b: DrawRecord | None) -> DrawDiffRow:
    """Compare a single aligned pair of draw records.

    Args:
        a: Left-side record (None if added).
        b: Right-side record (None if deleted).

    Returns:
        A DrawDiffRow with status, fields, and confidence.

    Raises:
        ValueError: If both a and b are None.
    """
    if a is None and b is None:
        raise ValueError("both a and b are None")

    if a is None:
        return DrawDiffRow(
            status=DiffStatus.ADDED,
            eid_a=None,
            eid_b=b.eid,  # type: ignore[union-attr]
            marker=b.marker_path,  # type: ignore[union-attr]
            draw_type=b.draw_type,  # type: ignore[union-attr]
            triangles_a=None,
            triangles_b=b.triangles,  # type: ignore[union-attr]
            instances_a=None,
            instances_b=b.instances,  # type: ignore[union-attr]
            confidence="high",
        )

    if b is None:
        return DrawDiffRow(
            status=DiffStatus.DELETED,
            eid_a=a.eid,
            eid_b=None,
            marker=a.marker_path,
            draw_type=a.draw_type,
            triangles_a=a.triangles,
            triangles_b=None,
            instances_a=a.instances,
            instances_b=None,
            confidence="high",
        )

    if a.draw_type == b.draw_type and a.triangles == b.triangles and a.instances == b.instances:
        status = DiffStatus.EQUAL
    else:
        status = DiffStatus.MODIFIED

    return DrawDiffRow(
        status=status,
        eid_a=a.eid,
        eid_b=b.eid,
        marker=a.marker_path,
        draw_type=a.draw_type,
        triangles_a=a.triangles,
        triangles_b=b.triangles,
        instances_a=a.instances,
        instances_b=b.instances,
        confidence="high",
    )


def _compute_confidence(records_a: list[DrawRecord], records_b: list[DrawRecord]) -> str:
    """Determine confidence level for fallback-aligned rows."""
    keys_a = make_fallback_keys(records_a)
    keys_b = make_fallback_keys(records_b)
    unique_a = len(set(keys_a)) == len(keys_a)
    unique_b = len(set(keys_b)) == len(keys_b)
    if unique_a and unique_b:
        return "medium"
    return "low"


def diff_draws(a: list[DrawRecord], b: list[DrawRecord]) -> list[DrawDiffRow]:
    """Diff two draw call sequences.

    Args:
        a: Draw records from capture A.
        b: Draw records from capture B.

    Returns:
        List of DrawDiffRow with status for each aligned pair.
    """
    aligned = align_draws(a, b)
    use_markers = has_markers(a) or has_markers(b)

    rows: list[DrawDiffRow] = []
    for ra, rb in aligned:
        row = compare_draw_pair(ra, rb)
        if not use_markers and row.status in (DiffStatus.EQUAL, DiffStatus.MODIFIED):
            row.confidence = _compute_confidence(a, b)
        rows.append(row)

    return rows


def _format_draw_line(eid: int, marker: str, draw_type: str, tri: int, inst: int) -> str:
    """Format a single draw call line."""
    marker_part = f"{marker}/" if marker != "-" else ""
    return f"EID={eid} {marker_part}{draw_type} tri={tri} inst={inst}"


def render_unified(rows: list[DrawDiffRow], capture_a: str, capture_b: str) -> str:
    """Render rows as unified diff text.

    Args:
        rows: Diff rows to render.
        capture_a: Name/path of capture A.
        capture_b: Name/path of capture B.

    Returns:
        Unified diff string.
    """
    lines: list[str] = [f"--- a/{capture_a}", f"+++ b/{capture_b}"]

    for row in rows:
        la = _format_draw_line(
            row.eid_a,
            row.marker,
            row.draw_type,  # type: ignore[arg-type]
            row.triangles_a,
            row.instances_a,  # type: ignore[arg-type]
        )
        lb = _format_draw_line(
            row.eid_b,
            row.marker,
            row.draw_type,  # type: ignore[arg-type]
            row.triangles_b,
            row.instances_b,  # type: ignore[arg-type]
        )
        if row.status == DiffStatus.EQUAL:
            lines.append(f" {la}")
        elif row.status == DiffStatus.DELETED:
            lines.append(f"-{la}")
        elif row.status == DiffStatus.ADDED:
            lines.append(f"+{lb}")
        elif row.status == DiffStatus.MODIFIED:
            lines.append(f"-{la}")
            lines.append(f"+{lb}")

    return "\n".join(lines)


def render_shortstat(rows: list[DrawDiffRow]) -> str:
    """Render rows as a single summary line.

    Returns:
        String like "3 added, 1 deleted, 5 modified, 42 unchanged".
    """
    added = sum(1 for r in rows if r.status == DiffStatus.ADDED)
    deleted = sum(1 for r in rows if r.status == DiffStatus.DELETED)
    modified = sum(1 for r in rows if r.status == DiffStatus.MODIFIED)
    unchanged = sum(1 for r in rows if r.status == DiffStatus.EQUAL)
    return f"{added} added, {deleted} deleted, {modified} modified, {unchanged} unchanged"


def render_json(rows: list[DrawDiffRow]) -> str:
    """Render rows as a JSON array.

    Returns:
        JSON string with all DrawDiffRow fields.
    """
    data = []
    for row in rows:
        d = asdict(row)
        d["status"] = row.status.value
        data.append(d)
    return json.dumps(data, indent=2)
