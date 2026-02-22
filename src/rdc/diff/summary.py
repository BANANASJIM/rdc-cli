"""Capture-level summary diff: compact delta view across categories."""

from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass
class SummaryRow:
    """One category in the summary diff."""

    category: str
    value_a: int
    value_b: int
    delta: int


def diff_summary(
    stats_a: dict[str, object],
    stats_b: dict[str, object],
    resource_count_a: int,
    resource_count_b: int,
) -> list[SummaryRow]:
    """Compute top-level deltas between two captures.

    Args:
        stats_a: Stats RPC result for capture A (contains per_pass list).
        stats_b: Stats RPC result for capture B (contains per_pass list).
        resource_count_a: Number of resources in capture A.
        resource_count_b: Number of resources in capture B.

    Returns:
        List of SummaryRow for draws, passes, resources, events.
    """
    per_pass_a: list[dict[str, object]] = stats_a.get("per_pass", [])  # type: ignore[assignment]
    per_pass_b: list[dict[str, object]] = stats_b.get("per_pass", [])  # type: ignore[assignment]

    draws_a = sum(int(p.get("draws", 0)) for p in per_pass_a)  # type: ignore[call-overload]
    draws_b = sum(int(p.get("draws", 0)) for p in per_pass_b)  # type: ignore[call-overload]
    passes_a = len(per_pass_a)
    passes_b = len(per_pass_b)

    events_a = int(stats_a.get("event_count", 0))  # type: ignore[call-overload]
    events_b = int(stats_b.get("event_count", 0))  # type: ignore[call-overload]

    return [
        SummaryRow("draws", draws_a, draws_b, draws_b - draws_a),
        SummaryRow("passes", passes_a, passes_b, passes_b - passes_a),
        SummaryRow(
            "resources",
            resource_count_a,
            resource_count_b,
            resource_count_b - resource_count_a,
        ),
        SummaryRow("events", events_a, events_b, events_b - events_a),
    ]


def render_text(rows: list[SummaryRow]) -> str:
    """Render summary as compact text.

    Returns:
        ``"identical"`` if all deltas are zero, otherwise one line per category.
    """
    if all(r.delta == 0 for r in rows):
        return "identical"

    def _fmt_delta(d: int) -> str:
        if d > 0:
            return f"(+{d})"
        if d < 0:
            return f"({d})"
        return "(=)"

    # Align columns for readability
    max_cat = max(len(r.category) for r in rows)
    max_a = max(len(str(r.value_a)) for r in rows)
    max_b = max(len(str(r.value_b)) for r in rows)

    lines: list[str] = []
    for r in rows:
        cat = f"{r.category}:".ljust(max_cat + 1)
        va = str(r.value_a).rjust(max_a)
        vb = str(r.value_b).rjust(max_b)
        lines.append(f"{cat} {va} -> {vb}  {_fmt_delta(r.delta)}")
    return "\n".join(lines)


def render_json(rows: list[SummaryRow]) -> str:
    """Render summary as JSON object.

    Returns:
        JSON string with each category as a key containing a/b/delta.
    """
    data: dict[str, dict[str, int]] = {}
    for r in rows:
        data[r.category] = {"a": r.value_a, "b": r.value_b, "delta": r.delta}
    return json.dumps(data, indent=2)
