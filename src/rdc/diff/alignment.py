"""Draw call alignment using LCS for diff comparison."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass


@dataclass(frozen=True)
class DrawRecord:
    """Single draw call record for diff alignment."""

    eid: int
    draw_type: str
    marker_path: str
    triangles: int
    instances: int
    pass_name: str
    shader_hash: str
    topology: str


def has_markers(records: list[DrawRecord]) -> bool:
    """Return True if any record has a non-trivial marker_path."""
    return any(r.marker_path != "-" for r in records)


def make_match_keys(records: list[DrawRecord]) -> list[tuple[str, str, int]]:
    """Build primary match keys with sequential index for repeated markers.

    Returns:
        List of (marker_path, draw_type, sequential_index) tuples.
    """
    counts: dict[tuple[str, str], int] = defaultdict(int)
    keys: list[tuple[str, str, int]] = []
    for r in records:
        pair = (r.marker_path, r.draw_type)
        idx = counts[pair]
        counts[pair] += 1
        keys.append((r.marker_path, r.draw_type, idx))
    return keys


def make_fallback_keys(records: list[DrawRecord]) -> list[tuple[str, str, str]]:
    """Build fallback keys for captures without debug markers.

    Returns:
        List of (draw_type, shader_hash, topology) tuples.
    """
    return [(r.draw_type, r.shader_hash, r.topology) for r in records]


def lcs_align(keys_a: list[tuple], keys_b: list[tuple]) -> list[tuple[int | None, int | None]]:
    """Align two key sequences using LCS dynamic programming.

    Returns:
        List of (index_a | None, index_b | None) pairs.
    """
    n, m = len(keys_a), len(keys_b)
    if n == 0:
        return [(None, j) for j in range(m)]
    if m == 0:
        return [(i, None) for i in range(n)]

    # Build LCS table
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if keys_a[i - 1] == keys_b[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])

    # Backtrack to build alignment
    result: list[tuple[int | None, int | None]] = []
    i, j = n, m
    matched: list[tuple[int, int]] = []
    while i > 0 and j > 0:
        if keys_a[i - 1] == keys_b[j - 1]:
            matched.append((i - 1, j - 1))
            i -= 1
            j -= 1
        elif dp[i - 1][j] >= dp[i][j - 1]:
            i -= 1
        else:
            j -= 1
    matched.reverse()

    # Merge matched pairs with unmatched items
    prev_a, prev_b = 0, 0
    for ai, bi in matched:
        # Deletions from a before this match
        for x in range(prev_a, ai):
            result.append((x, None))
        # Additions from b before this match
        for y in range(prev_b, bi):
            result.append((None, y))
        result.append((ai, bi))
        prev_a = ai + 1
        prev_b = bi + 1
    # Remaining deletions/additions
    for x in range(prev_a, n):
        result.append((x, None))
    for y in range(prev_b, m):
        result.append((None, y))

    return result


def _top_level_marker(path: str) -> str:
    """Extract top-level marker group (before first '/')."""
    idx = path.find("/")
    return path[:idx] if idx >= 0 else path


def _group_by_marker(
    records: list[DrawRecord],
) -> dict[str, list[int]]:
    """Group record indices by top-level marker."""
    groups: dict[str, list[int]] = defaultdict(list)
    for i, r in enumerate(records):
        groups[_top_level_marker(r.marker_path)].append(i)
    return groups


def align_draws(
    a: list[DrawRecord], b: list[DrawRecord]
) -> list[tuple[DrawRecord | None, DrawRecord | None]]:
    """Align two draw call sequences for diff comparison.

    Uses marker-based keys when markers are present, otherwise falls back
    to signature-based keys. Groups by top-level marker when combined
    length exceeds 500 for performance.

    Returns:
        List of (record_a | None, record_b | None) aligned pairs.
    """
    use_markers = has_markers(a) or has_markers(b)

    if use_markers and len(a) + len(b) > 500:
        return _grouped_align(a, b)

    if use_markers:
        keys_a = make_match_keys(a)
        keys_b = make_match_keys(b)
    else:
        keys_a = make_fallback_keys(a)
        keys_b = make_fallback_keys(b)

    pairs = lcs_align(keys_a, keys_b)
    return [
        (a[ia] if ia is not None else None, b[ib] if ib is not None else None) for ia, ib in pairs
    ]


def _grouped_align(
    a: list[DrawRecord], b: list[DrawRecord]
) -> list[tuple[DrawRecord | None, DrawRecord | None]]:
    """Align with grouping by top-level marker for large sequences."""
    groups_a = _group_by_marker(a)
    groups_b = _group_by_marker(b)

    all_groups = list(dict.fromkeys([*groups_a.keys(), *groups_b.keys()]))
    result: list[tuple[DrawRecord | None, DrawRecord | None]] = []

    for group in all_groups:
        sub_a = [a[i] for i in groups_a.get(group, [])]
        sub_b = [b[i] for i in groups_b.get(group, [])]
        keys_a = make_match_keys(sub_a)
        keys_b = make_match_keys(sub_b)
        pairs = lcs_align(keys_a, keys_b)
        for ia, ib in pairs:
            ra = sub_a[ia] if ia is not None else None
            rb = sub_b[ib] if ib is not None else None
            result.append((ra, rb))

    return result
