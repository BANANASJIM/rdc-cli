# Phase R2: Test Infrastructure Consolidation

## Motivation

Phase R1 eliminated the most widespread copy-paste patterns in source and test files.
R2 targets the next layer of duplication that R1 left in scope: daemon state
construction, CLI monkeypatching, and output format assertions.

All changes are pure refactors — zero behavioral change, zero modification to
production code.

## Changes

### R2.1 Shared `make_daemon_state()` builder

23 definitions of `_make_state()` exist across the test suite. Signatures diverge:

- Minimal: `_make_state() -> DaemonState` (no args, hardcoded defaults)
- With controller: `_make_state(ctrl: MockReplayController) -> DaemonState`
- With actions: `_make_state(actions: list | None) -> DaemonState`
- With pipe: `_make_state(tmp_path, pipe: MockPipeState) -> DaemonState`
- With remote flag: `_make_state(*, is_remote: bool) -> DaemonState`
- Miscellaneous overrides: `_make_state_with_ps()`, `_make_state_with_cbuffer()`, etc.

A single `make_daemon_state()` factory in `tests/unit/conftest.py` accepting
keyword-only arguments covers all variants. Fields not provided default to
sensible values (`capture="test.rdc"`, `current_eid=0`, `token="tok"`,
`max_eid=100`, `rd=mock_renderdoc`, etc.).

Files affected: `test_draws_daemon.py`, `test_vfs_daemon.py`,
`test_capturefile_handlers.py`, `test_daemon_output_quality.py`,
`test_tex_stats_handler.py`, `test_draws_events_daemon.py`,
`test_pipeline_section_routing.py`, `test_script_handler.py`,
`test_handlers_remote.py`, `test_descriptors_daemon.py`,
`test_fix1_draws_pass_name.py`, `test_pipeline_daemon.py`,
`test_debug_handlers.py`, `test_pick_pixel_daemon.py`,
`test_binary_daemon.py`, `test_pixel_history_daemon.py`,
`test_shader_edit_handlers.py`, `test_daemon_shader_api_fix.py`,
`test_daemon_pipeline_extended.py`.

### R2.2 CLI monkeypatch fixture

15 test files import `rdc.commands._helpers as mod` and repeat:

```python
session = type("S", (), {"host": "127.0.0.1", "port": 1, "token": "tok"})()
monkeypatch.setattr(mod, "load_session", lambda: session)
monkeypatch.setattr(mod, "send_request", lambda _h, _p, _payload: {"result": response})
```

A `patch_helpers` fixture (or helper function) in `conftest.py` encapsulates
this pattern. It accepts a `response` dict and an optional `session` override,
and handles the import and both `setattr` calls.

Inconsistent import paths (`import rdc.commands._helpers` at function scope vs
module scope) are normalized to module-scope imports where safe.

### R2.3 Output assertion helpers

CLI tests assert on JSON, JSONL, and TSV outputs with inline boilerplate:

- JSON: `data = json.loads(result.output); assert data[key] == value`
- JSONL: `lines = [json.loads(ln) for ln in result.output.strip().splitlines()]`
- TSV: `assert "COL1\tCOL2" in result.output`

Three helpers in `conftest.py`:

- `assert_json_output(result, **checks)` — parses and asserts dict keys
- `assert_jsonl_output(result) -> list[dict]` — returns parsed lines
- `assert_tsv_output(result, header=None)` — asserts header row and returns rows

## Risks

- **R2.1**: Some `_make_state` variants set uncommon fields (`disasm_cache`,
  `replay_output`, `built_shaders`). The factory must expose these via `**kwargs`
  forwarded to `DaemonState`, or tests that need them keep a local wrapper. Audit
  required before removal.
- **R2.2**: `send_request` lambda signatures differ subtly across files
  (`_h, _p, _payload` vs `*a`). The fixture must choose the most permissive form
  or expose a `send_fn` override parameter.
- **R2.3**: Helpers are pure convenience — no risk of hiding assertion intent.
  Must not swallow `result.exit_code` checks (callers remain responsible).

## Out of Scope

- Command layer unification (R3)
- Handler consolidation (R4)
- Any modification to production source code
