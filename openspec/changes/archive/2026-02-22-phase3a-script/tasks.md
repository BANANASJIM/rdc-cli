# Tasks: phase3a-script

## Phase A — Handler unit tests

- [ ] Create `tests/unit/test_script_handler.py`
- [ ] Test happy path: script prints + assigns `result = 42` → `stdout`, `return_value`, `elapsed_ms >= 0`
- [ ] Test stderr capture: script writes to `sys.stderr` → `stderr` field, `stdout` empty
- [ ] Test no `result` variable → `return_value` is `None`
- [ ] Test non-serializable `result` → `return_value` is a string (str() coercion)
- [ ] Test dict/list `result` → `return_value` is JSON-native value
- [ ] Test empty script → all fields empty/null, no error
- [ ] Test `args` forwarded: handler passes `{"mode": "fast"}`, script reads `args["mode"]`
- [ ] Test no replay loaded (`state.adapter is None`) → error `-32002`, message `"no replay loaded"`, assert handler return tuple[1] is True
- [ ] Test file not found → error `-32002`, message contains `"script not found"`
- [ ] Test path is directory → error `-32002`, message `"script path is a directory"`
- [ ] Test SyntaxError → error `-32002`, message starts with `"syntax error:"`, includes line number
- [ ] Test RuntimeError (`raise ValueError`) → error `-32002`, message `"script error: ValueError: ..."`, no crash
- [ ] Test `SystemExit` → error `-32002`, message `"script error: SystemExit: 0"`, daemon continues
- [ ] Test `KeyboardInterrupt` → error `-32002`, no crash
- [ ] Test stdout isolation: after handler returns, original `sys.stdout` is restored

## Phase B — CLI unit tests

- [ ] Create `tests/unit/test_script_command.py`
- [ ] Test default output: `result.stdout` content goes to stdout exactly
- [ ] Test default output: `result.stderr` goes to stderr
- [ ] Test default output: elapsed footer line on stderr matches `# elapsed: \d+ ms`
- [ ] Test default output: `return_value` not null → `# result:` line on stderr
- [ ] Test `--json` flag: raw JSON object on stdout, nothing on stderr, exit 0
- [ ] Test daemon error → exit 1, error message to stderr
- [ ] Test `--arg KEY=VALUE` single: `args={"KEY": "VALUE"}` in request
- [ ] Test `--arg` multiple: all pairs merged
- [ ] Test `--arg` missing `=`: exit 2 with error message
- [ ] Test no `--arg`: `args` defaults to `{}`

## Phase C — Handler implementation

- [ ] Create `src/rdc/handlers/script.py`
- [ ] Implement `_handle_script(request_id, params, state)`:
  - Validate `state.adapter is not None` → `-32002` if missing
  - Validate `path.exists()` → `-32002` with `"script not found"` message
  - Validate `path.is_file()` → `-32002` with `"script path is a directory"` message
  - `source = path.read_text("utf-8")`
  - Pre-flight: `compile(source, str(path), "exec")` → catch `SyntaxError`
  - Build fresh `script_globals = {"controller": ..., "rd": ..., "adapter": ..., "state": ..., "args": ...}`
  - Redirect stdout/stderr with `contextlib.redirect_stdout/redirect_stderr` + `StringIO`
  - Time with `time.perf_counter()`
  - `exec(code, script_globals)` under `BaseException` guard
  - Extract `result` variable; try `json.dumps()`, fall back to `str()`
  - Return `{stdout, stderr, elapsed_ms, return_value}`
- [ ] Expose `HANDLERS: dict[str, Any] = {"script": _handle_script}`
- [ ] Verify Phase A tests pass: `pixi run test -k test_script_handler`

## Phase D — CLI implementation

- [ ] Create `src/rdc/commands/script.py`
- [ ] Implement `script_cmd` Click command:
  - `@click.argument("script_file", type=click.Path(exists=True, dir_okay=False, path_type=Path))`
  - `@click.option("--arg", "args", multiple=True, metavar="KEY=VALUE")`
  - `@click.option("--json", "output_json", is_flag=True)`
  - Parse `--arg` list into `dict[str, str]`; exit 2 on missing `=`
  - Send daemon request `{"method": "script", "params": {"path": str(abs_path), "args": args_dict}}`
  - Default mode: print `stdout` to stdout, `stderr` to stderr, elapsed/result footers to stderr
  - `--json` mode: `click.echo(json.dumps(response))`
- [ ] Verify Phase B tests pass: `pixi run test -k test_script_command`

## Phase E — Registration

- [ ] In `daemon_server.py`: import `from rdc.handlers.script import HANDLERS as _SCRIPT_HANDLERS` and merge into `_DISPATCH`
- [ ] In `src/rdc/cli.py`: import `script_cmd` and add to CLI group
- [ ] Run `pixi run check` — lint + typecheck + all unit tests must pass

## Phase F — GPU integration test

- [ ] In `tests/integration/test_daemon_handlers_real.py`, add `test_script_get_resources_real`:
  - Write a temp script (`tmp_path / "probe.py"`) that calls `controller.GetResources()` and assigns `result = len(controller.GetResources())`
  - Call daemon `script` handler with the temp path
  - Assert `return_value` is an integer > 0
  - Assert `stdout == ""`
  - Assert `elapsed_ms >= 0`
- [ ] Run GPU tests: `RENDERDOC_PYTHON_PATH=... pixi run test-gpu -k test_script`

## Phase G — Final verification

- [ ] `pixi run lint` — zero ruff errors
- [ ] `pixi run test` — all unit tests green, coverage >= 80%
- [ ] GPU tests pass on `tests/fixtures/hello_triangle.rdc`
- [ ] Multi-agent code review (Opus / Codex / Gemini) — zero P0/P1 blockers
- [ ] Archive: move `openspec/changes/2026-02-22-phase3a-script/` → `openspec/changes/archive/`
- [ ] Merge delta into `openspec/specs/commands/script.md`
- [ ] Update `进度跟踪.md` in Obsidian vault
- [ ] Commit, push branch, open PR
