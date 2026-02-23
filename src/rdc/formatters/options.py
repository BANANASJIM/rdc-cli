"""Shared output options decorator for list commands."""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any

import click


def list_output_options(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Attach --no-header, --jsonl, -q to a Click command."""

    @click.option("--no-header", is_flag=True, help="Omit TSV header")
    @click.option("--jsonl", "use_jsonl", is_flag=True, help="JSONL output")
    @click.option("-q", "--quiet", is_flag=True, help="Print primary key column only")
    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return fn(*args, **kwargs)

    return wrapper
