"""Per-pass stats comparison and output renderers."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from rdc.diff.draws import DiffStatus


@dataclass
class PassDiffRow:
    """One row of per-pass stats diff output."""

    status: DiffStatus
    name: str
    draws_a: int | None
    draws_b: int | None
    draws_delta: str
    triangles_a: int | None
    triangles_b: int | None
    triangles_delta: str
    dispatches_a: int | None
    dispatches_b: int | None
    dispatches_delta: str


def _delta(a: int | None, b: int | None) -> str:
    """Format delta between two values.

    Returns:
        "+N", "-N", "0", or "-" if either side is missing.
    """
    if a is None or b is None:
        return "-"
    d = b - a
    if d > 0:
        return f"+{d}"
    if d < 0:
        return str(d)
    return "0"


def _int(d: dict[str, object], key: str) -> int:
    """Extract int from a dict with object values."""
    return int(d.get(key, 0))  # type: ignore[call-overload,no-any-return]


def diff_stats(
    passes_a: list[dict[str, object]],
    passes_b: list[dict[str, object]],
) -> list[PassDiffRow]:
    """Compare per-pass stats from two captures.

    Matches passes by name (case-insensitive, stripped). Same name compares
    draws, dispatches, triangles. Only-in-A is DELETED, only-in-B is ADDED.

    Args:
        passes_a: per_pass list from capture A.
        passes_b: per_pass list from capture B.

    Returns:
        List of PassDiffRow sorted by: DELETED first, then MODIFIED/EQUAL
        in A order, then ADDED in B order.
    """
    norm_a = {str(p.get("name", "")).strip().lower(): p for p in passes_a}
    norm_b = {str(p.get("name", "")).strip().lower(): p for p in passes_b}

    all_keys_a = [str(p.get("name", "")).strip().lower() for p in passes_a]
    all_keys_b = [str(p.get("name", "")).strip().lower() for p in passes_b]

    seen: set[str] = set()
    rows: list[PassDiffRow] = []

    # Walk A-side order: matched + deleted
    for key in all_keys_a:
        if key in seen:
            continue
        seen.add(key)
        pa = norm_a[key]
        name = str(pa.get("name", ""))

        if key in norm_b:
            pb = norm_b[key]
            da, db = _int(pa, "draws"), _int(pb, "draws")
            ta, tb = _int(pa, "triangles"), _int(pb, "triangles")
            dsa, dsb = _int(pa, "dispatches"), _int(pb, "dispatches")

            all_eq = da == db and ta == tb and dsa == dsb
            status = DiffStatus.EQUAL if all_eq else DiffStatus.MODIFIED
            rows.append(
                PassDiffRow(
                    status=status,
                    name=name,
                    draws_a=da,
                    draws_b=db,
                    draws_delta=_delta(da, db),
                    triangles_a=ta,
                    triangles_b=tb,
                    triangles_delta=_delta(ta, tb),
                    dispatches_a=dsa,
                    dispatches_b=dsb,
                    dispatches_delta=_delta(dsa, dsb),
                )
            )
        else:
            da = _int(pa, "draws")
            ta = _int(pa, "triangles")
            dsa = _int(pa, "dispatches")
            rows.append(
                PassDiffRow(
                    status=DiffStatus.DELETED,
                    name=name,
                    draws_a=da,
                    draws_b=None,
                    draws_delta="-",
                    triangles_a=ta,
                    triangles_b=None,
                    triangles_delta="-",
                    dispatches_a=dsa,
                    dispatches_b=None,
                    dispatches_delta="-",
                )
            )

    # Walk B-side: added only
    for key in all_keys_b:
        if key in seen:
            continue
        seen.add(key)
        pb = norm_b[key]
        name = str(pb.get("name", ""))
        db = _int(pb, "draws")
        tb = _int(pb, "triangles")
        dsb = _int(pb, "dispatches")
        rows.append(
            PassDiffRow(
                status=DiffStatus.ADDED,
                name=name,
                draws_a=None,
                draws_b=db,
                draws_delta="-",
                triangles_a=None,
                triangles_b=tb,
                triangles_delta="-",
                dispatches_a=None,
                dispatches_b=dsb,
                dispatches_delta="-",
            )
        )

    return rows


# -- Renderers ---------------------------------------------------------------


def render_tsv(rows: list[PassDiffRow], *, header: bool = True) -> str:
    """Render rows as TSV table.

    Args:
        rows: Diff rows to render.
        header: Whether to include the header line.

    Returns:
        TSV-formatted string.
    """
    lines: list[str] = []
    if header:
        lines.append(
            "STATUS\tPASS\tDRAWS_A\tDRAWS_B\tDRAWS_DELTA"
            "\tTRI_A\tTRI_B\tTRI_DELTA"
            "\tDISP_A\tDISP_B\tDISP_DELTA"
        )

    def _v(x: int | None) -> str:
        return str(x) if x is not None else "-"

    for r in rows:
        lines.append(
            f"{r.status.value}\t{r.name}\t{_v(r.draws_a)}\t{_v(r.draws_b)}\t{r.draws_delta}"
            f"\t{_v(r.triangles_a)}\t{_v(r.triangles_b)}\t{r.triangles_delta}"
            f"\t{_v(r.dispatches_a)}\t{_v(r.dispatches_b)}\t{r.dispatches_delta}"
        )
    return "\n".join(lines)


def render_shortstat(rows: list[PassDiffRow]) -> str:
    """Render a single summary line.

    Returns:
        String like "2 passes changed, 1 added, 1 deleted; +3 draws, +150 triangles, +2 dispatches".
    """
    changed = sum(1 for r in rows if r.status != DiffStatus.EQUAL)
    added = sum(1 for r in rows if r.status == DiffStatus.ADDED)
    deleted = sum(1 for r in rows if r.status == DiffStatus.DELETED)
    tri_delta = 0
    draw_delta = 0
    disp_delta = 0

    def _accum(a: int | None, b: int | None) -> int:
        if a is not None and b is not None:
            return b - a
        if b is not None:
            return b
        if a is not None:
            return -a
        return 0

    for r in rows:
        draw_delta += _accum(r.draws_a, r.draws_b)
        tri_delta += _accum(r.triangles_a, r.triangles_b)
        disp_delta += _accum(r.dispatches_a, r.dispatches_b)

    def _fmt(n: int) -> str:
        return f"+{n}" if n > 0 else str(n)

    parts = [f"{changed} passes changed"]
    if added:
        parts.append(f"{added} added")
    if deleted:
        parts.append(f"{deleted} deleted")
    lhs = ", ".join(parts)
    rhs = f"{_fmt(draw_delta)} draws, {_fmt(tri_delta)} triangles, {_fmt(disp_delta)} dispatches"
    return f"{lhs}; {rhs}"


def render_json(rows: list[PassDiffRow]) -> str:
    """Render rows as a JSON array.

    Returns:
        JSON string with all PassDiffRow fields.
    """
    data = []
    for row in rows:
        d = asdict(row)
        d["status"] = row.status.value
        data.append(d)
    return json.dumps(data, indent=2)


def render_unified(
    rows: list[PassDiffRow],
    capture_a: str,
    capture_b: str,
) -> str:
    """Render rows as unified diff text.

    Args:
        rows: Diff rows to render.
        capture_a: Name/path of capture A.
        capture_b: Name/path of capture B.

    Returns:
        Unified diff string.
    """
    lines: list[str] = [f"--- a/{capture_a}", f"+++ b/{capture_b}"]

    def _pass_line(name: str, draws: int, tri: int, disp: int) -> str:
        return f"{name} draws={draws} tri={tri} disp={disp}"

    def _a_line(r: PassDiffRow, prefix: str) -> str:
        assert r.draws_a is not None
        assert r.triangles_a is not None
        assert r.dispatches_a is not None
        return f"{prefix}{_pass_line(r.name, r.draws_a, r.triangles_a, r.dispatches_a)}"

    def _b_line(r: PassDiffRow, prefix: str) -> str:
        assert r.draws_b is not None
        assert r.triangles_b is not None
        assert r.dispatches_b is not None
        return f"{prefix}{_pass_line(r.name, r.draws_b, r.triangles_b, r.dispatches_b)}"

    for r in rows:
        if r.status == DiffStatus.EQUAL:
            lines.append(_a_line(r, " "))
        elif r.status == DiffStatus.DELETED:
            lines.append(_a_line(r, "-"))
        elif r.status == DiffStatus.ADDED:
            lines.append(_b_line(r, "+"))
        elif r.status == DiffStatus.MODIFIED:
            lines.append(_a_line(r, "-"))
            lines.append(_b_line(r, "+"))

    return "\n".join(lines)
