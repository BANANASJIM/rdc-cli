# Test Plan: CLI Enhancements

## Scope

### In scope
- `rdc completion` command: bash/zsh/fish output, auto-detect, invalid shell
- `rdc doctor` build hint: shown when renderdoc missing, cmake instructions

### Out of scope
- Actual shell completion behavior (Click's responsibility)
- renderdoc module loading (tested elsewhere)

## Test Matrix

| Layer | Target | Count |
|-------|--------|-------|
| Unit  | completion command (bash/zsh/fish/auto/invalid) | 5 |
| Unit  | doctor build hint when renderdoc missing | 1 |
| Unit  | doctor success + failure (existing, updated) | 2 |

## Cases

### Completion (test_completion.py)
1. `test_completion_bash` — exit 0, output contains `_rdc_completion` and `complete`
2. `test_completion_zsh` — exit 0, output contains `compdef` or `_rdc_completion`
3. `test_completion_fish` — exit 0, output contains `complete` and `rdc`
4. `test_completion_auto_detect` — monkeypatch `_detect_shell`, verify detection message
5. `test_completion_invalid_shell` — `powershell` → exit != 0

### Doctor (test_doctor.py)
1. `test_doctor_success` — patched find_renderdoc returns fake module, exit 0
2. `test_doctor_failure_when_missing_renderdoccmd` — missing renderdoccmd, exit 1
3. `test_doctor_shows_build_hint_when_renderdoc_missing` — find_renderdoc returns None, cmake hint in output

## Assertions
- Exit codes: 0 for success, 1 for failures, != 0 for invalid shell
- Completion output contains shell-specific markers
- Build hint contains `cmake -B build -DENABLE_PYRENDERDOC=ON`

## Risks
- BashComplete.source() spawns real bash subprocess → mitigated by autouse fixture mocking `_check_version`
- Click's completion output format may change across versions → assertions kept minimal
