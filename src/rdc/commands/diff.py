"""rdc diff command -- dual-daemon capture comparison."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

import click

from rdc.diff import stats as diff_stats_mod
from rdc.diff.alignment import align_draws
from rdc.diff.draws import DiffStatus
from rdc.diff.draws import diff_draws as _diff_draws
from rdc.diff.draws import render_json as render_json_draws
from rdc.diff.draws import render_shortstat as render_shortstat_draws
from rdc.diff.draws import render_tsv as render_tsv_draws
from rdc.diff.draws import render_unified as render_unified_draws
from rdc.diff.framebuffer import FramebufferDiffResult, compare_framebuffers
from rdc.diff.pipeline import (
    PIPE_SECTION_CALLS,
    build_draw_records,
    diff_pipeline_sections,
    find_aligned_pair,
    render_pipeline_json,
    render_pipeline_tsv,
)
from rdc.diff.resources import (
    ResourceRecord,
    diff_resources,
    render_tsv,
)
from rdc.diff.resources import render_json as render_json_res
from rdc.diff.resources import render_shortstat as render_shortstat_res
from rdc.diff.resources import render_unified as render_unified_res
from rdc.diff.summary import diff_summary, render_text
from rdc.diff.summary import render_json as render_json_summary
from rdc.services.diff_service import (
    DiffContext,
    query_both,
    query_each_sync,
    start_diff_session,
    stop_diff_session,
)


def _render_framebuffer(
    result: FramebufferDiffResult,
    *,
    use_json: bool,
    threshold: float,
) -> None:
    """Render framebuffer diff result to stdout."""
    if use_json:
        data = asdict(result)
        data["diff_image"] = str(result.diff_image) if result.diff_image else None
        data["threshold"] = threshold
        click.echo(json.dumps(data, indent=2))
        return

    if result.identical:
        click.echo("identical")
    else:
        click.echo(
            f"diff: {result.diff_pixels}/{result.total_pixels} pixels ({result.diff_ratio:.2f}%)"
        )
    click.echo(f"  eid={result.eid} target={result.target}")
    if result.diff_image is not None:
        click.echo(f"  diff image: {result.diff_image}")


def _handle_pass_stats(
    ctx: DiffContext,
    *,
    label: str,
    use_json: bool,
    fmt: str,
    shortstat: bool,
    no_header: bool,
) -> None:
    """Query both daemons for per-pass stats and render the diff."""
    resp_a, resp_b, err = query_both(ctx, "stats", {})
    if resp_a is None or resp_b is None:
        click.echo(
            f"error: {label} query failed: {err or 'daemon returned no result'}",
            err=True,
        )
        sys.exit(2)

    passes_a: list[dict[str, object]] = resp_a.get("result", {}).get("per_pass", [])
    passes_b: list[dict[str, object]] = resp_b.get("result", {}).get("per_pass", [])

    rows = diff_stats_mod.diff_stats(passes_a, passes_b)

    if shortstat:
        click.echo(diff_stats_mod.render_shortstat(rows))
    elif use_json or fmt == "json":
        click.echo(diff_stats_mod.render_json(rows))
    elif fmt == "unified":
        click.echo(diff_stats_mod.render_unified(rows, ctx.capture_a, ctx.capture_b))
    else:
        click.echo(diff_stats_mod.render_tsv(rows, header=not no_header))

    has_changes = any(r.status != DiffStatus.EQUAL for r in rows)
    sys.exit(1 if has_changes else 0)


def _handle_draws(
    ctx: DiffContext,
    *,
    use_json: bool,
    fmt: str,
    shortstat: bool,
    no_header: bool,
) -> None:
    """Query both daemons for draw calls and render the diff."""
    resp_a, resp_b, err = query_both(ctx, "draws", {})
    if resp_a is None or resp_b is None:
        click.echo(
            f"error: draws query failed: {err or 'daemon returned no result'}",
            err=True,
        )
        sys.exit(2)

    draws_a = resp_a.get("result", {}).get("draws", [])
    draws_b = resp_b.get("result", {}).get("draws", [])

    records_a = build_draw_records(draws_a)
    records_b = build_draw_records(draws_b)
    rows = _diff_draws(records_a, records_b)

    if shortstat:
        click.echo(render_shortstat_draws(rows))
    elif use_json or fmt == "json":
        click.echo(render_json_draws(rows))
    elif fmt == "unified":
        click.echo(render_unified_draws(rows, ctx.capture_a, ctx.capture_b))
    else:
        click.echo(render_tsv_draws(rows, header=not no_header))

    has_changes = any(r.status != DiffStatus.EQUAL for r in rows)
    sys.exit(1 if has_changes else 0)


def _handle_summary(ctx: DiffContext, *, use_json: bool) -> None:
    """Query both daemons for summary stats and render a compact delta view."""
    resp_stats_a, resp_stats_b, err_s = query_both(ctx, "stats", {})
    resp_res_a, resp_res_b, _err_r = query_both(ctx, "resources", {})

    if resp_stats_a is None or resp_stats_b is None:
        click.echo(
            f"error: summary query failed: {err_s or 'daemon returned no result'}",
            err=True,
        )
        sys.exit(2)

    stats_a = resp_stats_a.get("result", {})
    stats_b = resp_stats_b.get("result", {})

    res_count_a = len(resp_res_a.get("result", {}).get("rows", [])) if resp_res_a else 0
    res_count_b = len(resp_res_b.get("result", {}).get("rows", [])) if resp_res_b else 0

    rows = diff_summary(stats_a, stats_b, res_count_a, res_count_b)

    if use_json:
        click.echo(render_json_summary(rows))
    else:
        click.echo(render_text(rows))

    has_changes = any(r.delta != 0 for r in rows)
    sys.exit(1 if has_changes else 0)


@click.command("diff")
@click.argument("capture_a", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.argument("capture_b", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--draws", "mode", flag_value="draws")
@click.option("--resources", "mode", flag_value="resources")
@click.option("--passes", "mode", flag_value="passes")
@click.option("--stats", "mode", flag_value="stats")
@click.option("--framebuffer", "mode", flag_value="framebuffer")
@click.option("--pipeline", "pipeline_marker", default=None, metavar="MARKER")
@click.option("--json", "use_json", is_flag=True)
@click.option("--format", "fmt", type=click.Choice(["tsv", "unified", "json"]), default="tsv")
@click.option("--shortstat", is_flag=True)
@click.option("--no-header", is_flag=True)
@click.option("--verbose", is_flag=True)
@click.option("--timeout", default=60.0, type=float)
@click.option("--target", default=0, type=int, help="Color target index (default 0)")
@click.option(
    "--threshold",
    default=0.0,
    type=float,
    help="Max diff ratio %% to count as identical",
)
@click.option("--eid", default=None, type=int, help="Compare at specific EID (default: last draw)")
@click.option(
    "--diff-output",
    default=None,
    type=click.Path(path_type=Path),
    help="Write diff PNG here",
)
def diff_cmd(
    capture_a: Path,
    capture_b: Path,
    mode: str | None,
    pipeline_marker: str | None,
    use_json: bool,
    fmt: str,
    shortstat: bool,
    no_header: bool,
    verbose: bool,
    timeout: float,
    target: int,
    threshold: float,
    eid: int | None,
    diff_output: Path | None,
) -> None:
    """Compare two RenderDoc captures side-by-side."""
    if pipeline_marker is not None:
        mode = "pipeline"
    if mode is None:
        mode = "summary"

    ctx, err = start_diff_session(str(capture_a), str(capture_b), timeout_s=timeout)
    if ctx is None:
        click.echo(f"error: {err}", err=True)
        sys.exit(2)

    try:
        if mode == "framebuffer":
            result, fb_err = compare_framebuffers(
                ctx,
                target=target,
                threshold=threshold,
                eid=eid,
                diff_output=diff_output,
                timeout_s=timeout,
            )
            if result is None:
                click.echo(f"error: {fb_err}", err=True)
                sys.exit(2)
            _render_framebuffer(result, use_json=use_json, threshold=threshold)
            sys.exit(0 if result.identical else 1)

        elif mode == "pipeline":
            assert pipeline_marker is not None
            exit_code = _handle_pipeline(
                ctx,
                pipeline_marker,
                use_json=use_json,
                verbose=verbose,
                no_header=no_header,
            )
            sys.exit(exit_code)

        elif mode == "resources":
            _handle_resources(
                ctx,
                capture_a,
                capture_b,
                fmt,
                use_json,
                shortstat,
                no_header,
                timeout,
            )

        elif mode == "stats":
            _handle_pass_stats(
                ctx,
                label="stats",
                use_json=use_json,
                fmt=fmt,
                shortstat=shortstat,
                no_header=no_header,
            )

        elif mode == "draws":
            _handle_draws(
                ctx,
                use_json=use_json,
                fmt=fmt,
                shortstat=shortstat,
                no_header=no_header,
            )

        elif mode == "passes":
            _handle_pass_stats(
                ctx,
                label="passes",
                use_json=use_json,
                fmt=fmt,
                shortstat=shortstat,
                no_header=no_header,
            )

        elif mode == "summary":
            _handle_summary(ctx, use_json=use_json)
    finally:
        stop_diff_session(ctx)


def _handle_pipeline(
    ctx: Any,
    marker: str,
    *,
    use_json: bool,
    verbose: bool,
    no_header: bool,
) -> int:
    """Execute pipeline diff and render output.

    Returns:
        Exit code: 0 = no differences, 1 = differences found, 2 = error.
    """
    # Fetch draws from both daemons
    resp_a, resp_b, err = query_both(ctx, "draws", {})
    if resp_a is None and resp_b is None:
        click.echo(f"error: {err}", err=True)
        return 2

    draws_a = resp_a["result"]["draws"] if resp_a else []
    draws_b = resp_b["result"]["draws"] if resp_b else []

    records_a = build_draw_records(draws_a)
    records_b = build_draw_records(draws_b)

    aligned = align_draws(records_a, records_b)
    pair, msg = find_aligned_pair(aligned, marker)

    if pair is None:
        click.echo(f"error: {msg}", err=True)
        return 2

    if msg:
        click.echo(f"warning: {msg}", err=True)

    rec_a, rec_b = pair
    assert rec_a is not None and rec_b is not None

    # Build per-side RPC calls with their own EIDs
    calls_a = [(method, {"eid": rec_a.eid}) for method, _ in PIPE_SECTION_CALLS]
    calls_b = [(method, {"eid": rec_b.eid}) for method, _ in PIPE_SECTION_CALLS]

    results_a, results_b, _ = query_each_sync(ctx, calls_a, calls_b)

    # Warn about failed sections
    section_names = [s for _, s in PIPE_SECTION_CALLS]
    for i, name in enumerate(section_names):
        if results_a[i] is None or results_b[i] is None:
            click.echo(f"warning: section '{name}' skipped (RPC failed)", err=True)

    diffs = diff_pipeline_sections(results_a, results_b)

    if use_json:
        click.echo(render_pipeline_json(diffs))
    else:
        click.echo(render_pipeline_tsv(diffs, verbose=verbose, header=not no_header))

    has_changes = any(d.changed for d in diffs)
    return 1 if has_changes else 0


def _handle_resources(
    ctx: object,
    capture_a: Path,
    capture_b: Path,
    fmt: str,
    use_json: bool,
    shortstat: bool,
    no_header: bool,
    timeout: float,
) -> None:
    """Handle --resources mode: query, diff, render, exit."""
    resp_a, resp_b, err = query_both(ctx, "resources", {}, timeout_s=timeout)  # type: ignore[arg-type]
    if resp_a is None or resp_b is None:
        msg = err or "one or both daemons returned no data"
        click.echo(f"error: {msg}", err=True)
        sys.exit(2)

    records_a = [ResourceRecord(**r) for r in resp_a["result"]["rows"]]
    records_b = [ResourceRecord(**r) for r in resp_b["result"]["rows"]]

    rows = diff_resources(records_a, records_b)

    if shortstat:
        click.echo(render_shortstat_res(rows))
    elif fmt == "json" or use_json:
        click.echo(render_json_res(rows))
    elif fmt == "unified":
        click.echo(render_unified_res(rows, str(capture_a), str(capture_b)))
    else:
        click.echo(render_tsv(rows, header=not no_header))

    has_changes = any(r.status != DiffStatus.EQUAL for r in rows)
    sys.exit(1 if has_changes else 0)
