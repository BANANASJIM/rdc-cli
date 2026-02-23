#!/usr/bin/env python3
"""Generate replay.json — run real rdc commands and capture output for docs terminal animation.

Output: array of playlists, each playlist is a themed session.
Wrapped playlists get auto open/close; unwrapped manage their own lifecycle.
The frontend rotates through playlists on each loop.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys

CAPTURE = "tests/fixtures/hello_triangle.rdc"
CAPTURE_B = "tests/fixtures/vkcube.rdc"

OPEN = ("rdc open hello_triangle.rdc", f"rdc open {CAPTURE}", None)
CLOSE = ("rdc close", "rdc close", None)

Scene = tuple[str, str, int | None]

# wrap=True: auto open/close around scenes
# wrap=False: scenes list IS the full playlist (manages its own open/close)
PLAYLISTS: list[tuple[str, bool, list[Scene]]] = [
    # 1. Quickstart: open → inspect → pipeline → close
    (
        "quickstart",
        True,
        [
            ("rdc info", "rdc info", None),
            ("rdc draws", "rdc draws", None),
            ("rdc pipeline 11", "rdc pipeline 11", None),
            ('rdc search "main"', 'rdc search "main"', None),
        ],
    ),
    # 2. VFS + Unix pipes: the key differentiator
    (
        "vfs-and-pipes",
        True,
        [
            ("rdc tree / --depth 1", "rdc tree / --depth 1", 15),
            ("rdc ls /draws/11", "rdc ls /draws/11", None),
            ("rdc cat /draws/11/pipeline/topology", "rdc cat /draws/11/pipeline/topology", None),
            ("rdc resources -q | wc -l", "rdc resources -q | wc -l", None),
            (
                'rdc draws --json | jq ".[0].triangles"',
                "rdc draws --json | jq '.[0].triangles'",
                None,
            ),
        ],
    ),
    # 3. Debug pixel: unique shader debugging capability
    (
        "debug-pixel",
        True,
        [
            ("rdc pick-pixel 300 300 11", "rdc pick-pixel 300 300 11", None),
            ("rdc pixel 300 300 11", "rdc pixel 300 300 11", None),
            ("rdc debug pixel 11 300 300", "rdc debug pixel 11 300 300", None),
            ("rdc debug pixel 11 300 300 --trace", "rdc debug pixel 11 300 300 --trace", 8),
        ],
    ),
    # 4. CI assertions + JSON: built for automation
    (
        "ci-json",
        True,
        [
            ("rdc draws --json", "rdc draws --json", None),
            ("rdc assert-count draws --expect 1 --op eq", "rdc assert-count draws --expect 1 --op eq", None),
            ("rdc assert-count events --expect 5 --op ge", "rdc assert-count events --expect 5 --op ge", None),
        ],
    ),
    # 5. Diff: compare two captures without a session
    (
        "diff",
        False,
        [
            (
                "rdc diff before.rdc after.rdc --draws",
                f"rdc diff {CAPTURE} {CAPTURE_B} --draws",
                None,
            ),
            (
                "rdc diff before.rdc after.rdc --stats",
                f"rdc diff {CAPTURE} {CAPTURE_B} --stats",
                None,
            ),
        ],
    ),
]

STRIP_PATTERNS = [
    re.compile(r"^session:"),
    re.compile(r"^has_callstacks:"),
    re.compile(r"^machine_ident:"),
    re.compile(r"^timestamp_base:"),
]


def run(cmd: str, max_lines: int | None = None) -> str:
    """Run command and return stdout (stderr on failure), cleaned up."""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
    out = result.stdout.strip() if result.stdout.strip() else result.stderr.strip()

    lines = [ln for ln in out.splitlines() if not any(p.match(ln) for p in STRIP_PATTERNS)]
    lines = [ln.replace(CAPTURE, "hello_triangle.rdc") for ln in lines]
    lines = [ln.replace(CAPTURE_B, "vkcube.rdc") for ln in lines]

    if max_lines and len(lines) > max_lines:
        lines = lines[:max_lines] + [f"... ({len(lines) - max_lines} more)"]

    return "\n".join(lines)


def run_scene(scene: Scene) -> dict[str, str]:
    display_cmd, actual_cmd, max_lines = scene
    return {"cmd": display_cmd, "output": run(actual_cmd, max_lines)}


def main() -> None:
    open_data = run_scene(OPEN)
    session_open = True

    playlists: list[list[dict[str, str]]] = []
    for _label, wrap, scenes in PLAYLISTS:
        if wrap:
            if not session_open:
                open_data = run_scene(OPEN)
                session_open = True
            playlist = [open_data]
            for scene in scenes:
                playlist.append(run_scene(scene))
            playlist.append(run_scene(CLOSE))
            session_open = False
            playlists.append(playlist)
        else:
            # Unwrapped: close existing session first if needed
            if session_open:
                run(CLOSE[1])
                session_open = False
            playlist = []
            for scene in scenes:
                playlist.append(run_scene(scene))
            playlists.append(playlist)

    # Clean up
    if session_open:
        run(CLOSE[1])

    print(json.dumps(playlists, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
