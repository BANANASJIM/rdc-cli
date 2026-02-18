# Test Plan: bootstrap-foundation

## Scope
- In scope:
  - CLI entrypoint behavior
  - doctor checks and exit code contract
  - capture wrapper argv mapping and failure handling
- Out of scope:
  - real RenderDoc replay
  - GPU integration

## Test Matrix
- Unit:
  - command registration and help
  - doctor result rendering
  - capture arg mapping
- Mock:
  - monkeypatch `shutil.which`, `subprocess.run`, `importlib.import_module`
- Integration:
  - deferred to Phase 0 W3+
- Regression:
  - ensure stderr/stdout contracts stay stable

## Cases
- Happy path:
  - `rdc --version` exits 0
  - `rdc doctor` all checks pass exits 0
  - `rdc capture -o out.rdc -- ./app` maps args correctly
- Error path:
  - renderdoccmd not found => exit 1 + stderr error
  - doctor check failure => exit 1
  - subprocess non-zero => same exit code propagated
- Edge cases:
  - unknown extra args passthrough in capture

## Assertions
- Exit codes:
  - doctor: 0 pass, 1 fail
  - capture: passthrough subprocess code; 1 when missing binary
- stdout/stderr contract:
  - errors and hints on stderr
- TSV/JSON schema contract:
  - not applicable for this change

## Risks & Rollback
- Potential regressions:
  - future global option parsing can break capture passthrough
- Rollback checks:
  - if capture wrapper breaks, command can be temporarily disabled without affecting doctor/version
