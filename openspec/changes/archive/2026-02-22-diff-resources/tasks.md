# Tasks: diff-resources

## Phase A — Unit tests for `diff_resources()` logic

- [ ] Create `tests/unit/test_diff_resources.py`
- [ ] Test both lists empty → `[]`
- [ ] Test all EQUAL: same name + same type in both sides → all rows `EQUAL`, confidence `"high"`
- [ ] Test MODIFIED: same name, different type → `MODIFIED`, `type_a`/`type_b` set
- [ ] Test ADDED: resource only in B → `ADDED`, `type_a` is `None`
- [ ] Test DELETED: resource only in A → `DELETED`, `type_b` is `None`
- [ ] Test mixed batch: EQUAL + MODIFIED + DELETED + ADDED in one call
- [ ] Test case-insensitive name match: `"MyBuffer"` matches `"mybuffer"` → EQUAL
- [ ] Test name collision (duplicate names in one side) → no crash, extra treated as ADDED/DELETED
- [ ] Test unnamed same-type same-count → EQUAL, confidence `"low"`
- [ ] Test unnamed count mismatch → EQUAL rows + DELETED remainder
- [ ] Test unnamed type absent in other side → DELETED, confidence `"low"`
- [ ] Test mixed named + unnamed: named matched first, unnamed matched in type groups

## Phase B — Unit tests for renderers

- [ ] Test `render_tsv`: header present by default
- [ ] Test `render_tsv(header=False)`: no header line
- [ ] Test `render_tsv`: EQUAL / MODIFIED / DELETED / ADDED row format (tab-separated, empty TYPE columns)
- [ ] Test `render_shortstat`: all statuses present → correct counts
- [ ] Test `render_shortstat`: all equal → zero added/deleted/modified
- [ ] Test `render_json`: returns valid JSON array; status uses symbol; `None` → `null`
- [ ] Test `render_json`: all required keys present (`status`, `name`, `type_a`, `type_b`, `confidence`)
- [ ] Test `render_unified`: header lines `--- a/<a>` and `+++ b/<b>`
- [ ] Test `render_unified`: EQUAL / MODIFIED / DELETED / ADDED line format

## Phase C — Implementation: `src/rdc/diff/resources.py`

- [ ] Create `src/rdc/diff/resources.py`
- [ ] Define `ResourceRecord(id: int, type: str, name: str)` dataclass
- [ ] Define `ResourceDiffRow(status: DiffStatus, name: str, type_a: str | None, type_b: str | None, confidence: str)` dataclass
- [ ] Implement `diff_resources(a, b)`:
  - Separate named (non-empty name) from unnamed (empty name) in each side
  - Named: build dict keyed by `name.lower()`; iterate union of keys; emit EQUAL/MODIFIED/ADDED/DELETED
  - Unnamed: group by `type`; zip within each group → EQUAL; remainder → ADDED or DELETED; confidence `"low"`
- [ ] Implement `render_tsv(rows, *, header=True) -> str`
- [ ] Implement `render_shortstat(rows) -> str`
- [ ] Implement `render_json(rows) -> str` (reuse `DiffStatus.value` for symbol)
- [ ] Implement `render_unified(rows, capture_a, capture_b) -> str`
- [ ] Verify Phase A + B tests pass: `pixi run test -k test_diff_resources`

## Phase D — CLI unit tests

- [ ] Test `--resources` flag no longer emits "not yet implemented" (monkeypatch `query_both` → empty rows)
- [ ] Test exit 0 when no differences
- [ ] Test exit 1 when at least one non-EQUAL row
- [ ] Test exit 2 on both-sides RPC failure (`query_both` returns `(None, None, err)`)
- [ ] Test exit 2 when one side is `None`
- [ ] Test default TSV output: STATUS column in stdout
- [ ] Test `--shortstat`: stdout matches summary pattern
- [ ] Test `--json`: stdout is valid JSON array
- [ ] Test `--format unified`: stdout starts with `--- a/`
- [ ] Test `--no-header`: first line is not `STATUS\t...`

## Phase E — CLI wiring: `src/rdc/commands/diff.py`

- [ ] Remove `"resources"` from `_MODE_STUBS`
- [ ] Import from `rdc.diff.resources` and `rdc.services.diff_service`
- [ ] In `diff_cmd`, add `mode == "resources"` branch:
  - Call `query_both(ctx, "resources", {}, timeout_s=timeout)`
  - Exit 2 if either side is `None` (error to stderr)
  - Parse `resp["result"]["rows"]` → `list[ResourceRecord]` for each side
  - Call `diff_resources(records_a, records_b)` → `rows`
  - Dispatch to renderer based on `shortstat` / `fmt` / `output_json`
  - `sys.exit(0)` if all EQUAL, `sys.exit(1)` if any non-EQUAL
- [ ] Verify Phase D tests pass: `pixi run test -k test_diff_command or test_diff_resources`

## Phase F — Final verification

- [ ] `pixi run lint` — zero ruff errors
- [ ] `pixi run test` — all unit tests green, coverage >= 80%
- [ ] Multi-agent code review (Opus / Codex / Gemini) — zero P0/P1 blockers
- [ ] Archive: move `openspec/changes/2026-02-22-diff-resources/` → `openspec/changes/archive/`
- [ ] Merge delta into `openspec/specs/commands/diff.md`
- [ ] Update `进度跟踪.md` in Obsidian vault
- [ ] Commit, push branch, open PR
