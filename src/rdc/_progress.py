"""Progress callback factory for RenderDoc long-running operations."""

from __future__ import annotations

import math
import time
from collections.abc import Callable

import click


def make_progress_cb(label: str, min_interval: float = 1.0) -> Callable[[float], None]:
    """Return a callback suitable for RenderDoc ProgressCallback.

    Writes to stderr. On tty: '\\r{label}: {pct:.0%}' in place, '\\n' at
    completion. Non-tty: one line per call, throttled to min_interval seconds.
    First call (progress=0.0001) and final call (progress>=1.0) always emit.
    Clamps NaN/negative/inf to [0, 1].
    """
    last_echo: list[float] = [0.0]
    first_seen: list[bool] = [False]

    def _cb(progress: float) -> None:
        if math.isnan(progress) or progress < 0:
            progress = 0.0
        elif math.isinf(progress) or progress > 1.0:
            progress = 1.0

        is_first = not first_seen[0]
        is_done = progress >= 1.0
        first_seen[0] = True

        stderr = click.get_text_stream("stderr")
        on_tty = stderr.isatty()

        if on_tty:
            end = "\n" if is_done else "\r"
            click.echo(f"{label}: {progress:.0%}", nl=False, err=True)
            click.echo(end, nl=False, err=True)
        else:
            now = time.monotonic()
            if is_first or is_done or (now - last_echo[0] >= min_interval):
                click.echo(f"{label}: {progress:.0%}", err=True)
                last_echo[0] = now

    return _cb
