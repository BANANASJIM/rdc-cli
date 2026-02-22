# Tasks: diff-pipeline

## Phase A — Unit tests (pipeline logic)

- [ ] Create `tests/unit/test_diff_pipeline.py`
- [ ] Test `build_draw_records`: full row with all fields → correct `DrawRecord`
- [ ] Test `build_draw_records`: missing `marker` key → `marker_path="-"`
- [ ] Test `build_draw_records`: empty list → `[]`
- [ ] Test `find_aligned_pair`: marker found in both → returns `(a, b)` pair
- [ ] Test `find_aligned_pair`: marker only in A (b=None) → error tuple for B
- [ ] Test `find_aligned_pair`: marker only in B (a=None) → error tuple for A
- [ ] Test `find_aligned_pair`: marker absent entirely → error tuple for A
- [ ] Test `find_aligned_pair`: repeated marker, no index → returns index 0, sets warning flag
- [ ] Test `find_aligned_pair`: repeated marker `[1]` suffix → returns index 1
- [ ] Test `find_aligned_pair`: `[99]` out of range → returns error
- [ ] Test `diff_pipeline_sections`: identical flat section → `changed=False`, values equal
- [ ] Test `diff_pipeline_sections`: scalar field changed → `changed=True`, correct values
- [ ] Test `diff_pipeline_sections`: `eid` key never appears in output fields
- [ ] Test `diff_pipeline_sections`: nested dict (stencil) field changed → dot-path field name
- [ ] Test `diff_pipeline_sections`: list section element differs → index-path field name
- [ ] Test `diff_pipeline_sections`: list length mismatch → `field="count"`, `changed=True`
- [ ] Test `diff_pipeline_sections`: section result is `None` → section skipped, no exception
- [ ] Test `diff_pipeline_sections`: all sections identical → all `changed=False`
- [ ] Test `render_pipeline_tsv` changed-only: only changed rows present, each ends with `<- changed`
- [ ] Test `render_pipeline_tsv` verbose: all rows present, unchanged rows lack `<- changed`
- [ ] Test `render_pipeline_tsv` no-header: no header line
- [ ] Test `render_pipeline_json`: valid JSON array with required keys per element
- [ ] Test `render_pipeline_json`: empty diff list → `[]`

## Phase B — CLI unit tests

- [ ] In `tests/unit/test_diff_command.py`, add/extend:
- [ ] Test `--pipeline MARKER` dispatches to pipeline handler (not stub); exit 0
  (monkeypatch `query_both`, `query_both_sync`, and `find_aligned_pair`)
- [ ] Test `--pipeline` + `--json`: JSON on stdout, exit 0
- [ ] Test `--pipeline` + `--verbose`: all fields rendered
- [ ] Test `--pipeline` + `--no-header`: header absent
- [ ] Test `--pipeline` marker not found: exit 2, error to stderr
- [ ] Test `--pipeline` draws fetch failure (both None): exit 2
- [ ] Test `--pipeline` section RPC partial failure: affected sections skipped, exit 0

## Phase C — Implementation: `src/rdc/diff/pipeline.py`

- [ ] Create `src/rdc/diff/pipeline.py`
- [ ] Define `PipeFieldDiff` dataclass: `section`, `field`, `value_a`, `value_b`, `changed`
- [ ] Implement `build_draw_records(draws: list[dict]) -> list[DrawRecord]`:
  - Map `eid`, `type`→`draw_type`, `marker`→`marker_path` (default `"-"`),
    `triangles`, `instances`, `pass`→`pass_name`, `shader_hash=""`, `topology=""`
- [ ] Implement `find_aligned_pair(aligned, marker_path) -> tuple[(DrawRecord|None, DrawRecord|None), str]`:
  - Parse optional `[N]` suffix from marker_path
  - Count occurrences among aligned pairs where both sides are non-None
  - Return `(None, None, error_msg)` on not-found or out-of-range
  - Return warning string (non-empty) if duplicates and no index suffix given
- [ ] Implement `_diff_flat(section, d_a, d_b) -> list[PipeFieldDiff]`:
  - Skip `eid` key; compare all other scalar fields
- [ ] Implement `_diff_nested(section, d_a, d_b) -> list[PipeFieldDiff]`:
  - For dict values: recurse with dot-path prefix
- [ ] Implement `_diff_list(section, key, list_a, list_b) -> list[PipeFieldDiff]`:
  - Compare length; compare element dicts by index
- [ ] Implement `diff_pipeline_sections(results_a, results_b, section_names) -> list[PipeFieldDiff]`:
  - Dispatch each section to appropriate diff strategy
  - Skip section pair if either result is `None`; emit warning
- [ ] Implement `render_pipeline_tsv(diffs, *, verbose=False, header=True) -> str`
- [ ] Implement `render_pipeline_json(diffs) -> str`
- [ ] Define `PIPE_SECTION_CALLS`: ordered list of `(method, section_key)` pairs for all 13 sections

## Phase D — CLI wiring: `src/rdc/commands/diff.py`

- [ ] Remove `"pipeline"` from `_MODE_STUBS`
- [ ] Import pipeline functions from `rdc.diff.pipeline`
- [ ] In `diff_cmd`, when `mode == "pipeline"`:
  - Call `query_both(ctx, "draws", {})` → error exit 2 if both fail
  - Build `DrawRecord` lists via `build_draw_records`
  - Call `align_draws(records_a, records_b)`
  - Call `find_aligned_pair(aligned, pipeline_marker)` → exit 2 on error, print warning on duplicates
  - Build `PIPE_SECTION_CALLS` with `eid` params for each side
  - Call `query_both_sync(ctx, calls_a_and_b)` (or two separate calls for each EID)
  - Call `diff_pipeline_sections`
  - Render and `click.echo` output
- [ ] Verify Phase B tests pass: `pixi run test -k test_diff`

## Phase E — Final verification

- [ ] `pixi run lint` — zero ruff errors
- [ ] `pixi run test` — all unit tests green, coverage >= 80%
- [ ] Multi-agent code review (Opus / Codex / Gemini) — zero P0/P1 blockers
- [ ] Archive: move `openspec/changes/2026-02-22-diff-pipeline/` → `openspec/changes/archive/`
- [ ] Merge delta into `openspec/specs/commands/diff.md`
- [ ] Update `进度跟踪.md` in Obsidian vault
- [ ] Commit, push branch, open PR
