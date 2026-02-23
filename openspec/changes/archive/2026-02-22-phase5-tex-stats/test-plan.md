# Test Plan: Phase 5 — tex-stats

## Scope

### In scope
- `_handle_tex_stats` daemon handler (min/max, histogram)
- `tex_stats_cmd` CLI command (table output, JSON output, argument parsing)
- Mock extensions: `GetMinMax`, `GetHistogram` on `MockReplayController`
- GPU integration: real capture, verify statistical properties

### Out of scope
- Texture export pipeline (`tex_export`, `SaveTexture`)
- VFS tree changes (no new VFS routes)
- Non-float texture formats (depth/stencil special handling deferred)

## Test Matrix

| Layer | File | Coverage |
|---|---|---|
| Unit (mock) | `tests/unit/test_tex_stats.py` | handler logic, CLI output, error paths |
| GPU integration | `tests/integration/test_daemon_handlers_real.py` | real API, statistical sanity |

## Unit Tests — `tests/unit/test_tex_stats.py`

### Handler tests (monkeypatch `DaemonState` with mock adapter)

| ID | Test | Assertion |
|---|---|---|
| TS-01 | `test_tex_stats_no_adapter` | Returns `-32002` error when `state.adapter is None` |
| TS-02 | `test_tex_stats_no_rd` | Returns `-32002` error when `state.rd is None` |
| TS-03 | `test_tex_stats_unknown_id` | Returns `-32001` error for texture ID not in `tex_map` |
| TS-04 | `test_tex_stats_basic_minmax` | With `_min_max_map[rid]` set, result contains `min`/`max` keys with `r/g/b/a` floats |
| TS-05 | `test_tex_stats_minmax_values` | `result["min"]["r"]` equals `floatValue[0]` of the configured `PixelValue` |
| TS-06 | `test_tex_stats_no_histogram_by_default` | Result does not contain `"histogram"` key when `histogram=False` |
| TS-07 | `test_tex_stats_histogram_present` | With `histogram=True`, result contains `"histogram"` list of length 256 |
| TS-08 | `test_tex_stats_histogram_values` | Each histogram entry is a dict with keys `bucket`, `r`, `g`, `b`, `a` |
| TS-09 | `test_tex_stats_mip_slice_forwarded` | `_make_subresource` called with correct mip/slice values |
| TS-10 | `test_tex_stats_eid_navigation` | `_set_frame_event` called with provided eid |
| TS-11 | `test_tex_stats_eid_out_of_range` | Returns `-32002` error when eid exceeds `state.max_eid` |
| TS-12 | `test_tex_stats_msaa_rejected` | Returns `-32001` error when `tex.msSamp > 1` |

### CLI tests (monkeypatch `_daemon_call`, use `CliRunner`)

| ID | Test | Assertion |
|---|---|---|
| TS-13 | `test_cli_tex_stats_table_output` | Default output contains `CHANNEL\tMIN\tMAX` header and four rows: R/G/B/A |
| TS-14 | `test_cli_tex_stats_json_output` | `--json` flag produces valid JSON with `min`, `max` keys |
| TS-15 | `test_cli_tex_stats_histogram_table` | `--histogram` produces `BUCKET\tR\tG\tB\tA` header with 256 data rows |
| TS-16 | `test_cli_tex_stats_histogram_json` | `--histogram --json` JSON contains `histogram` list of length 256 |
| TS-17 | `test_cli_tex_stats_eid_arg` | Positional `eid` is included in `params` dict passed to daemon |
| TS-18 | `test_cli_tex_stats_eid_omitted` | Without `eid` argument, `params` dict has no `"eid"` key |
| TS-19 | `test_cli_tex_stats_mip_slice_opts` | `--mip 2 --slice 1` sets `params["mip"]=2`, `params["slice"]=1` |
| TS-20 | `test_cli_tex_stats_float_format` | Min/max values printed with 4 decimal places |

### Mock tests (verify new mock methods)

| ID | Test | Assertion |
|---|---|---|
| TS-21 | `test_mock_get_minmax_default` | `GetMinMax` returns `(PixelValue(), PixelValue())` when map is empty |
| TS-22 | `test_mock_get_minmax_configured` | `GetMinMax` returns configured tuple for known `rid` |
| TS-23 | `test_mock_get_histogram_default` | `GetHistogram` returns list of 256 zeros when map is empty |
| TS-24 | `test_mock_get_histogram_configured` | `GetHistogram` returns configured list for known `rid` |

## GPU Integration Tests — `tests/integration/test_daemon_handlers_real.py`

All GPU tests require a valid capture opened before the test class runs
(existing session fixture pattern).

| ID | Test | Assertion |
|---|---|---|
| TS-25 | `test_tex_stats_real_minmax` | `GetMinMax` on a real texture returns `min.r <= max.r` (and same for g/b/a) |
| TS-26 | `test_tex_stats_real_no_nan` | All min/max float values are finite (not NaN/Inf) |
| TS-27 | `test_tex_stats_real_histogram` | With `histogram=True`, histogram list length is 256; each entry has `r/g/b/a` ints |
| TS-28 | `test_tex_stats_real_histogram_nonneg` | All histogram bucket counts are >= 0 |
| TS-29 | `test_tex_stats_real_unknown_id` | tex-stats on nonexistent id 0 returns error code -32001 |
| TS-30 | `test_tex_stats_real_eid_navigation` | Providing a known draw eid succeeds and eid is echoed in result |

## Acceptance Criteria

1. `pixi run lint && pixi run test` passes with zero failures.
2. All TS-01..TS-24 unit tests pass without GPU.
3. All TS-25..TS-30 GPU tests pass with a real capture.
4. `rdc tex-stats <id>` prints a four-row CHANNEL/MIN/MAX table.
5. `rdc tex-stats <id> --histogram` appends a 256-row bucket table.
6. `rdc tex-stats <id> --json` produces valid JSON; `--histogram --json` includes `histogram` key.

## Risks and Rollback

- SWIG channel mask: if `list[bool]` is rejected, switch to per-call scalar
  mask using `rdcfixedarray` — unit tests will catch this immediately.
- GPU test flakiness: histogram bucket sums may vary by capture; only check
  structural properties (length, non-negative), not exact counts.
- Rollback: remove `tex_stats.py`, revert `texture.py`/`cli.py` additions.
