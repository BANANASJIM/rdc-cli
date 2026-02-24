"""CI assertion commands: assert-pixel, assert-clean, assert-count, assert-state."""

from __future__ import annotations

import json
import operator
import sys
from typing import Any

import click

from rdc.commands._helpers import _json_mode
from rdc.commands.unix_helpers import _COUNT_TARGETS
from rdc.daemon_client import send_request
from rdc.protocol import _request
from rdc.session_state import load_session


def _err_exit(msg: str) -> None:
    """Print error (JSON or plain text based on context) and exit(2)."""
    if _json_mode():
        click.echo(json.dumps({"error": {"message": msg}}), err=True)
    else:
        click.echo(f"error: {msg}", err=True)
    sys.exit(2)


_SEVERITY_RANK: dict[str, int] = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "INFO": 3, "UNKNOWN": 4}

_OPS: dict[str, Any] = {
    "eq": operator.eq,
    "gt": operator.gt,
    "lt": operator.lt,
    "ge": operator.ge,
    "le": operator.le,
}

_VALID_SECTIONS: frozenset[str] = frozenset(
    {
        "topology",
        "viewport",
        "scissor",
        "blend",
        "stencil",
        "rasterizer",
        "depth-stencil",
        "msaa",
        "vbuffers",
        "ibuffer",
        "samplers",
        "push-constants",
        "vinputs",
        "vs",
        "hs",
        "ds",
        "gs",
        "ps",
        "cs",
    }
)

_HYPHENATED_SECTIONS: frozenset[str] = frozenset({"depth-stencil", "push-constants"})


def _assert_call(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """JSON-RPC call with exit(2) on any error."""
    session = load_session()
    if session is None:
        msg = "no active session"
        if _json_mode():
            click.echo(json.dumps({"error": {"message": msg}}), err=True)
        else:
            click.echo(f"error: {msg}", err=True)
        sys.exit(2)
    payload = _request(method, 1, {"_token": session.token, **(params or {})}).to_dict()
    try:
        resp = send_request(session.host, session.port, payload)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        msg = f"daemon unreachable: {exc}"
        if _json_mode():
            click.echo(json.dumps({"error": {"message": msg}}), err=True)
        else:
            click.echo(f"error: {msg}", err=True)
        sys.exit(2)
    if "error" in resp:
        msg = resp["error"]["message"]
        if _json_mode():
            click.echo(json.dumps({"error": {"message": msg}}), err=True)
        else:
            click.echo(f"error: {msg}", err=True)
        sys.exit(2)
    return resp["result"]  # type: ignore[no-any-return]


def _parse_key_path(key_path: str) -> tuple[str, list[str]]:
    """Split key-path into (section, field_path) handling hyphenated sections."""
    for hs in _HYPHENATED_SECTIONS:
        if key_path == hs or key_path.startswith(hs + "."):
            rest = key_path[len(hs) + 1 :] if len(key_path) > len(hs) else ""
            return hs, rest.split(".") if rest else []
    parts = key_path.split(".")
    return parts[0], parts[1:]


def _traverse_path(data: Any, path: list[str]) -> Any:
    """Walk nested dict/list by path segments; exit(2) on invalid path."""
    for seg in path:
        if isinstance(data, list):
            try:
                data = data[int(seg)]
            except (ValueError, IndexError):
                _err_exit(f"invalid path segment '{seg}'")
        elif isinstance(data, dict):
            if seg not in data:
                _err_exit(f"key '{seg}' not found")
            data = data[seg]
        else:
            _err_exit(f"cannot traverse into {type(data).__name__}")
    return data


def _normalize_value(v: Any) -> str:
    """Normalize a value to string for comparison; booleans lowercased."""
    if isinstance(v, bool):
        return str(v).lower()
    return str(v)


# ---------------------------------------------------------------------------
# assert-pixel
# ---------------------------------------------------------------------------


@click.command("assert-pixel")
@click.argument("eid", type=int)
@click.argument("x", type=int)
@click.argument("y", type=int)
@click.option("--expect", required=True, help="Expected RGBA as 4 space-separated floats.")
@click.option("--tolerance", default=0.01, type=float, help="Per-channel tolerance.")
@click.option("--target", default=0, type=int, help="Render target index.")
@click.option("--json", "use_json", is_flag=True, help="JSON output.")
def assert_pixel_cmd(
    eid: int, x: int, y: int, expect: str, tolerance: float, target: int, use_json: bool
) -> None:
    """Assert pixel RGBA at (x, y) matches expected value within tolerance."""
    parts = expect.split()
    if len(parts) != 4:
        _err_exit("--expect must have exactly 4 floats (R G B A)")
    try:
        expected = [float(v) for v in parts]
    except ValueError:
        _err_exit("--expect values must be numeric")

    result = _assert_call("pixel_history", {"eid": eid, "x": x, "y": y, "target": target})
    mods = result.get("modifications", [])
    passing = [m for m in mods if m.get("passed")]
    if not passing:
        _err_exit("no passing modification found")

    last = passing[-1]
    pm = last["post_mod"]
    actual = [pm["r"], pm["g"], pm["b"], pm["a"]]

    passed = all(round(abs(a - e), 10) <= tolerance for a, e in zip(actual, expected, strict=True))

    if use_json:
        click.echo(
            json.dumps(
                {
                    "pass": passed,
                    "expected": expected,
                    "actual": actual,
                    "tolerance": tolerance,
                    "eid": eid,
                    "x": x,
                    "y": y,
                }
            )
        )
    elif passed:
        fmt = " ".join(f"{v:.4f}" for v in actual)
        click.echo(f"pass: pixel ({x}, {y}) = {fmt}")
    else:
        efmt = " ".join(f"{v:.4f}" for v in expected)
        afmt = " ".join(f"{v:.4f}" for v in actual)
        click.echo(f"fail: pixel ({x}, {y}) expected {efmt}, got {afmt}")

    sys.exit(0 if passed else 1)


# ---------------------------------------------------------------------------
# assert-clean
# ---------------------------------------------------------------------------


@click.command("assert-clean")
@click.option(
    "--min-severity",
    default="HIGH",
    type=click.Choice(["HIGH", "MEDIUM", "LOW", "INFO"], case_sensitive=False),
    help="Minimum severity threshold.",
)
@click.option("--json", "use_json", is_flag=True, help="JSON output.")
def assert_clean_cmd(min_severity: str, use_json: bool) -> None:
    """Assert capture log has no messages at or above given severity."""
    min_severity = min_severity.upper()
    result = _assert_call("log")
    messages = result.get("messages", [])
    threshold = _SEVERITY_RANK[min_severity]
    violations = [
        m for m in messages if _SEVERITY_RANK.get(m.get("level", "UNKNOWN"), 4) <= threshold
    ]

    passed = len(violations) == 0

    if use_json:
        click.echo(
            json.dumps(
                {
                    "pass": passed,
                    "min_severity": min_severity,
                    "count": len(violations),
                    "messages": violations,
                }
            )
        )
    elif passed:
        click.echo(f"pass: no messages at severity >= {min_severity}")
    else:
        click.echo(f"fail: {len(violations)} message(s) at severity >= {min_severity}")
        for m in violations:
            click.echo(f"  [{m.get('level')}] eid={m.get('eid')}: {m.get('message')}", err=True)

    sys.exit(0 if passed else 1)


# ---------------------------------------------------------------------------
# assert-count
# ---------------------------------------------------------------------------


@click.command("assert-count")
@click.argument("what", type=click.Choice(_COUNT_TARGETS, case_sensitive=False))
@click.option("--expect", required=True, type=int, help="Expected count value.")
@click.option(
    "--op",
    default="eq",
    type=click.Choice(["eq", "gt", "lt", "ge", "le"]),
    help="Comparison operator.",
)
@click.option("--pass", "pass_name", default=None, help="Filter by render pass name.")
@click.option("--json", "use_json", is_flag=True, help="JSON output.")
def assert_count_cmd(
    what: str,
    expect: int,
    op: str,
    pass_name: str | None,
    use_json: bool,
) -> None:
    """Assert a capture metric satisfies a numeric comparison."""
    params: dict[str, Any] = {"what": what}
    if pass_name is not None:
        params["pass"] = pass_name

    result = _assert_call("count", params)
    actual: int = result["value"]
    passed = _OPS[op](actual, expect)

    if use_json:
        click.echo(
            json.dumps(
                {
                    "pass": passed,
                    "what": what,
                    "actual": actual,
                    "expected": expect,
                    "op": op,
                }
            )
        )
    elif passed:
        click.echo(f"pass: {what} = {actual} (expected {op} {expect})")
    else:
        click.echo(f"fail: {what} = {actual} (expected {op} {expect})")

    sys.exit(0 if passed else 1)


# ---------------------------------------------------------------------------
# assert-state
# ---------------------------------------------------------------------------


@click.command("assert-state")
@click.argument("eid", type=int)
@click.argument("key_path", metavar="KEY_PATH")
@click.option("--expect", required=True, help="Expected value.")
@click.option("--json", "use_json", is_flag=True, help="JSON output.")
def assert_state_cmd(eid: int, key_path: str, expect: str, use_json: bool) -> None:
    """Assert pipeline state value at EID matches expected."""
    section, field_path = _parse_key_path(key_path)
    if section not in _VALID_SECTIONS:
        _err_exit(f"invalid section '{section}'")

    result = _assert_call("pipeline", {"eid": eid, "section": section})
    # Unwrap shader stage results — handler wraps them in {"row": {..., "section_detail": {...}}}
    if "row" in result:
        row = result["row"]
        sd = row.get("section_detail")
        result = sd if isinstance(sd, dict) else row
    # Single-segment path: extract leaf by section name
    if not field_path:
        actual_raw = result.get(section, result)
    else:
        actual_raw = _traverse_path(result, field_path)
    actual_str = _normalize_value(actual_raw)
    expect_str = expect.lower() if expect.lower() in ("true", "false") else expect

    passed = actual_str == expect_str

    if use_json:
        click.echo(
            json.dumps(
                {
                    "pass": passed,
                    "eid": eid,
                    "key_path": key_path,
                    "expected": expect_str,
                    "actual": actual_str,
                }
            )
        )
    elif passed:
        click.echo(f"pass: {key_path} = {actual_str}")
    else:
        click.echo(f"fail: {key_path} = {actual_str} (expected {expect_str})")

    sys.exit(0 if passed else 1)
