"""Pipeline state comparison between two captures."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from typing import Any

from rdc.diff.alignment import DrawRecord

# 13 pipeline sections: (rpc_method, section_key)
PIPE_SECTION_CALLS: list[tuple[str, str]] = [
    ("pipe_topology", "topology"),
    ("pipe_viewport", "viewport"),
    ("pipe_scissor", "scissor"),
    ("pipe_blend", "blend"),
    ("pipe_stencil", "stencil"),
    ("pipe_vinputs", "vinputs"),
    ("pipe_samplers", "samplers"),
    ("pipe_vbuffers", "vbuffers"),
    ("pipe_ibuffer", "ibuffer"),
    ("pipe_push_constants", "push_constants"),
    ("pipe_rasterizer", "rasterizer"),
    ("pipe_depth_stencil", "depth_stencil"),
    ("pipe_msaa", "msaa"),
]

# Sections whose result value is a list, keyed by name
_LIST_SECTIONS: dict[str, str] = {
    "blend": "blends",
    "vinputs": "inputs",
    "samplers": "samplers",
    "vbuffers": "vbuffers",
    "push_constants": "push_constants",
}

# Sections with nested dict sub-fields
_NESTED_SECTIONS: set[str] = {"stencil"}

_MARKER_INDEX_RE = re.compile(r"^(.+)\[(\d+)]$")


@dataclass
class PipeFieldDiff:
    """One field difference in a pipeline section."""

    section: str
    field: str
    value_a: Any
    value_b: Any
    changed: bool


def build_draw_records(draws: list[dict[str, Any]]) -> list[DrawRecord]:
    """Convert draws RPC response rows to DrawRecord list.

    Args:
        draws: List of draw dicts from the ``draws`` RPC response.

    Returns:
        List of DrawRecord with fields mapped from the RPC response.
    """
    return [
        DrawRecord(
            eid=d["eid"],
            draw_type=d.get("type", ""),
            marker_path=d.get("marker", "-"),
            triangles=d.get("triangles", 0),
            instances=d.get("instances", 0),
            pass_name=d.get("pass", ""),
            shader_hash="",
            topology="",
        )
        for d in draws
    ]


def find_aligned_pair(
    aligned: list[tuple[DrawRecord | None, DrawRecord | None]],
    marker_path: str,
) -> tuple[tuple[DrawRecord | None, DrawRecord | None] | None, str]:
    """Find the aligned pair matching a marker path.

    Supports ``marker[N]`` syntax for selecting among repeated markers.

    Args:
        aligned: Aligned draw record pairs from ``align_draws``.
        marker_path: Marker path, optionally with ``[N]`` index suffix.

    Returns:
        ``(pair, warning)`` on success, ``(None, error_msg)`` on failure.
        Warning is non-empty if duplicates exist and no index was given.
    """
    m = _MARKER_INDEX_RE.match(marker_path)
    if m:
        base_marker, target_idx = m.group(1), int(m.group(2))
    else:
        base_marker, target_idx = marker_path, 0

    # Collect matching pairs (both sides present and marker matches)
    matches: list[tuple[DrawRecord | None, DrawRecord | None]] = []
    for a, b in aligned:
        marker_a = a.marker_path if a else None
        marker_b = b.marker_path if b else None
        if marker_a == base_marker or marker_b == base_marker:
            matches.append((a, b))

    if not matches:
        return None, f"marker '{base_marker}' not found in either capture"

    if target_idx >= len(matches):
        return None, (
            f"marker '{base_marker}' index [{target_idx}] out of range "
            f"(only {len(matches)} occurrence{'s' if len(matches) != 1 else ''})"
        )

    pair = matches[target_idx]
    warning = ""
    if not m and len(matches) > 1:
        warning = (
            f"marker '{base_marker}' appears {len(matches)} times; "
            f"using index [0]. Specify [{base_marker}[N]] to select."
        )

    # Check both sides are present
    a, b = pair
    if a is None:
        return None, f"marker '{base_marker}' not found in capture A"
    if b is None:
        return None, f"marker '{base_marker}' not found in capture B"

    return pair, warning


def _strip_eid(d: dict[str, Any]) -> dict[str, Any]:
    """Return dict copy without 'eid' key."""
    return {k: v for k, v in d.items() if k != "eid"}


def _diff_flat(section: str, d_a: dict[str, Any], d_b: dict[str, Any]) -> list[PipeFieldDiff]:
    """Compare two flat dicts field-by-field."""
    a = _strip_eid(d_a)
    b = _strip_eid(d_b)
    all_keys = dict.fromkeys([*a.keys(), *b.keys()])
    diffs: list[PipeFieldDiff] = []
    for key in all_keys:
        va, vb = a.get(key), b.get(key)
        diffs.append(
            PipeFieldDiff(
                section=section,
                field=key,
                value_a=va,
                value_b=vb,
                changed=va != vb,
            )
        )
    return diffs


def _diff_nested(section: str, d_a: dict[str, Any], d_b: dict[str, Any]) -> list[PipeFieldDiff]:
    """Compare dicts that may contain nested dict values (e.g. stencil front/back)."""
    a = _strip_eid(d_a)
    b = _strip_eid(d_b)
    all_keys = dict.fromkeys([*a.keys(), *b.keys()])
    diffs: list[PipeFieldDiff] = []
    for key in all_keys:
        va, vb = a.get(key), b.get(key)
        if isinstance(va, dict) and isinstance(vb, dict):
            sub_keys = dict.fromkeys([*va.keys(), *vb.keys()])
            for sk in sub_keys:
                sva, svb = va.get(sk), vb.get(sk)
                diffs.append(
                    PipeFieldDiff(
                        section=section,
                        field=f"{key}.{sk}",
                        value_a=sva,
                        value_b=svb,
                        changed=sva != svb,
                    )
                )
        else:
            diffs.append(
                PipeFieldDiff(
                    section=section,
                    field=key,
                    value_a=va,
                    value_b=vb,
                    changed=va != vb,
                )
            )
    return diffs


def _diff_list(
    section: str, list_key: str, d_a: dict[str, Any], d_b: dict[str, Any]
) -> list[PipeFieldDiff]:
    """Compare list-valued sections element-by-element."""
    a_stripped = _strip_eid(d_a)
    b_stripped = _strip_eid(d_b)
    list_a: list[dict[str, Any]] = a_stripped.get(list_key, [])
    list_b: list[dict[str, Any]] = b_stripped.get(list_key, [])
    diffs: list[PipeFieldDiff] = []

    if len(list_a) != len(list_b):
        diffs.append(
            PipeFieldDiff(
                section=section,
                field="count",
                value_a=len(list_a),
                value_b=len(list_b),
                changed=True,
            )
        )

    for i in range(min(len(list_a), len(list_b))):
        elem_a, elem_b = list_a[i], list_b[i]
        all_keys = dict.fromkeys([*elem_a.keys(), *elem_b.keys()])
        for key in all_keys:
            va, vb = elem_a.get(key), elem_b.get(key)
            diffs.append(
                PipeFieldDiff(
                    section=section,
                    field=f"{list_key}[{i}].{key}",
                    value_a=va,
                    value_b=vb,
                    changed=va != vb,
                )
            )

    return diffs


def diff_pipeline_sections(
    results_a: list[dict[str, Any] | None],
    results_b: list[dict[str, Any] | None],
    section_names: list[str] | None = None,
) -> list[PipeFieldDiff]:
    """Compare pipeline section results from both captures.

    Args:
        results_a: RPC results for capture A (one per section, may be None).
        results_b: RPC results for capture B (one per section, may be None).
        section_names: Section keys in order. Defaults to PIPE_SECTION_CALLS order.

    Returns:
        List of PipeFieldDiff for all compared fields.
    """
    if section_names is None:
        section_names = [s for _, s in PIPE_SECTION_CALLS]

    diffs: list[PipeFieldDiff] = []
    for i, section in enumerate(section_names):
        ra = results_a[i] if i < len(results_a) else None
        rb = results_b[i] if i < len(results_b) else None

        if ra is None or rb is None:
            continue

        # Extract the result payload
        da = ra.get("result", ra) if isinstance(ra, dict) else ra
        db = rb.get("result", rb) if isinstance(rb, dict) else rb

        if section in _LIST_SECTIONS:
            diffs.extend(_diff_list(section, _LIST_SECTIONS[section], da, db))
        elif section in _NESTED_SECTIONS:
            diffs.extend(_diff_nested(section, da, db))
        else:
            diffs.extend(_diff_flat(section, da, db))

    return diffs


def render_pipeline_tsv(
    diffs: list[PipeFieldDiff],
    *,
    verbose: bool = False,
    header: bool = True,
) -> str:
    """Render pipeline diffs as TSV text.

    Args:
        diffs: List of field diffs.
        verbose: If True, show all fields; otherwise only changed.
        header: If True, include a header line.

    Returns:
        TSV-formatted string.
    """
    lines: list[str] = []
    if header:
        lines.append("SECTION\tFIELD\tA\tB")

    for d in diffs:
        if not verbose and not d.changed:
            continue
        suffix = "\t<- changed" if d.changed else ""
        lines.append(f"{d.section}\t{d.field}\t{d.value_a}\t{d.value_b}{suffix}")

    return "\n".join(lines)


def render_pipeline_json(diffs: list[PipeFieldDiff]) -> str:
    """Render pipeline diffs as JSON array.

    Args:
        diffs: List of field diffs.

    Returns:
        JSON string with all diff entries.
    """
    return json.dumps([asdict(d) for d in diffs], indent=2)
