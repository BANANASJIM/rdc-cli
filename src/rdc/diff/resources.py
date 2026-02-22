"""Resource comparison and output renderers."""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import asdict, dataclass

from rdc.diff.draws import DiffStatus


@dataclass
class ResourceRecord:
    id: int
    type: str
    name: str


@dataclass
class ResourceDiffRow:
    status: DiffStatus
    name: str
    type_a: str | None
    type_b: str | None
    confidence: str


def diff_resources(a: list[ResourceRecord], b: list[ResourceRecord]) -> list[ResourceDiffRow]:
    """Diff two resource lists by name (case-insensitive), unnamed by type-group position.

    Args:
        a: Resources from capture A.
        b: Resources from capture B.

    Returns:
        List of ResourceDiffRow with status for each matched pair.
    """
    rows: list[ResourceDiffRow] = []

    # Separate named vs unnamed
    named_a: dict[str, ResourceRecord] = {}
    named_b: dict[str, ResourceRecord] = {}
    unnamed_a: list[ResourceRecord] = []
    unnamed_b: list[ResourceRecord] = []

    for r in a:
        if r.name:
            key = r.name.lower()
            if key not in named_a:
                named_a[key] = r
            else:
                unnamed_a.append(r)
        else:
            unnamed_a.append(r)

    for r in b:
        if r.name:
            key = r.name.lower()
            if key not in named_b:
                named_b[key] = r
            else:
                unnamed_b.append(r)
        else:
            unnamed_b.append(r)

    # Match named resources
    all_keys = list(dict.fromkeys([*named_a, *named_b]))
    for key in all_keys:
        ra = named_a.get(key)
        rb = named_b.get(key)
        if ra and rb:
            status = DiffStatus.EQUAL if ra.type == rb.type else DiffStatus.MODIFIED
            rows.append(
                ResourceDiffRow(
                    status=status,
                    name=ra.name,
                    type_a=ra.type,
                    type_b=rb.type,
                    confidence="high",
                )
            )
        elif ra:
            rows.append(
                ResourceDiffRow(
                    status=DiffStatus.DELETED,
                    name=ra.name,
                    type_a=ra.type,
                    type_b=None,
                    confidence="high",
                )
            )
        else:
            assert rb is not None
            rows.append(
                ResourceDiffRow(
                    status=DiffStatus.ADDED,
                    name=rb.name,
                    type_a=None,
                    type_b=rb.type,
                    confidence="high",
                )
            )

    # Match unnamed resources by type-group position
    groups_a: dict[str, list[ResourceRecord]] = defaultdict(list)
    groups_b: dict[str, list[ResourceRecord]] = defaultdict(list)
    for r in unnamed_a:
        groups_a[r.type].append(r)
    for r in unnamed_b:
        groups_b[r.type].append(r)

    all_types = list(dict.fromkeys([*groups_a, *groups_b]))
    for t in all_types:
        la = groups_a.get(t, [])
        lb = groups_b.get(t, [])
        paired = min(len(la), len(lb))
        for i in range(paired):
            rows.append(
                ResourceDiffRow(
                    status=DiffStatus.EQUAL,
                    name="",
                    type_a=la[i].type,
                    type_b=lb[i].type,
                    confidence="low",
                )
            )
        for r in la[paired:]:
            rows.append(
                ResourceDiffRow(
                    status=DiffStatus.DELETED,
                    name="",
                    type_a=r.type,
                    type_b=None,
                    confidence="low",
                )
            )
        for r in lb[paired:]:
            rows.append(
                ResourceDiffRow(
                    status=DiffStatus.ADDED,
                    name="",
                    type_a=None,
                    type_b=r.type,
                    confidence="low",
                )
            )

    return rows


def render_tsv(rows: list[ResourceDiffRow], *, header: bool = True) -> str:
    """Render rows as tab-separated values.

    Args:
        rows: Diff rows to render.
        header: Include header line.

    Returns:
        TSV string.
    """
    lines: list[str] = []
    if header:
        lines.append("STATUS\tNAME\tTYPE_A\tTYPE_B")
    for r in rows:
        lines.append(f"{r.status.value}\t{r.name}\t{r.type_a or ''}\t{r.type_b or ''}")
    return "\n".join(lines)


def render_shortstat(rows: list[ResourceDiffRow]) -> str:
    """Render rows as a single summary line.

    Returns:
        String like "3 added, 1 deleted, 2 modified, 40 unchanged".
    """
    added = sum(1 for r in rows if r.status == DiffStatus.ADDED)
    deleted = sum(1 for r in rows if r.status == DiffStatus.DELETED)
    modified = sum(1 for r in rows if r.status == DiffStatus.MODIFIED)
    unchanged = sum(1 for r in rows if r.status == DiffStatus.EQUAL)
    return f"{added} added, {deleted} deleted, {modified} modified, {unchanged} unchanged"


def render_json(rows: list[ResourceDiffRow]) -> str:
    """Render rows as a JSON array.

    Returns:
        JSON string with all ResourceDiffRow fields.
    """
    data = []
    for row in rows:
        d = asdict(row)
        d["status"] = row.status.value
        data.append(d)
    return json.dumps(data, indent=2)


def render_unified(rows: list[ResourceDiffRow], capture_a: str, capture_b: str) -> str:
    """Render rows as unified diff text.

    Args:
        rows: Diff rows to render.
        capture_a: Name/path of capture A.
        capture_b: Name/path of capture B.

    Returns:
        Unified diff string.
    """
    lines: list[str] = [f"--- a/{capture_a}", f"+++ b/{capture_b}"]
    for r in rows:
        if r.status == DiffStatus.EQUAL:
            lines.append(f" {r.name} {r.type_a}")
        elif r.status == DiffStatus.DELETED:
            lines.append(f"-{r.name} {r.type_a}")
        elif r.status == DiffStatus.ADDED:
            lines.append(f"+{r.name} {r.type_b}")
        elif r.status == DiffStatus.MODIFIED:
            lines.append(f"-{r.name} {r.type_a}")
            lines.append(f"+{r.name} {r.type_b}")
    return "\n".join(lines)
