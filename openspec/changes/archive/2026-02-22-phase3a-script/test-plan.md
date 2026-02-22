# Test Plan: phase3a-script

## Scope

### In scope
- Daemon handler `script`: exec() a local `.py` file inside daemon, return
  `{stdout, stderr, elapsed_ms, return_value}`
- stdout/stderr capture via `contextlib.redirect_stdout/redirect_stderr` + `StringIO`
- `result` variable extraction with JSON-serialization fallback to `str()`
- `BaseException` guard preventing `SystemExit` / `KeyboardInterrupt` from
  killing the daemon
- SyntaxError pre-flight via `compile()` returning line-number message
- Error codes: no replay (-32002), file missing (-32002), is-directory (-32002),
  syntax error (-32002), runtime error (-32002)
- CLI `rdc script <file.py>`: default formatted output + `--json` raw mode
- CLI `--arg KEY=VALUE` parsing → `args` dict forwarded to daemon
- Registration in `daemon_server.py` HANDLERS dispatch and `cli.py` group

### Out of scope
- Sandbox or security isolation beyond token auth
- VFS path for script execution
- Streaming output (stdout returned only after script completes)
- Script timeout / resource limits
- Script caching or module import reuse between calls

## Test Matrix

| Layer       | Scope                                               | Runner                         |
|-------------|-----------------------------------------------------|--------------------------------|
| Unit        | Handler happy path, error paths, capture isolation  | pytest (`test_script_handler.py`) |
| Unit        | CLI output format, `--json`, `--arg` parsing        | pytest + CliRunner (`test_script_command.py`) |
| Integration | Mock API sync (no new mock API needed)              | existing `test_mock_api_sync.py` (no change expected) |
| GPU         | Real capture: `controller.GetResources()` via script | pytest -m gpu (`test_daemon_handlers_real.py`) |

## Cases

### Handler: happy paths

1. **Print + result assignment**: script does `print("hello")` and `result = 42`.
   Response: `stdout="hello\n"`, `return_value=42`, `elapsed_ms >= 0`, `stderr=""`.

2. **stderr output**: script does `import sys; sys.stderr.write("warn\n")`.
   Response: `stderr="warn\n"`, `stdout=""`.

3. **No result variable**: script only prints. Response: `return_value=null`.

4. **Non-serializable result**: script assigns `result = object()`.
   Response: `return_value` is a non-empty string (str() coercion), not an error.

5. **Dict/list result**: script assigns `result = {"k": [1, 2]}`.
   Response: `return_value={"k": [1, 2]}` (JSON-native).

6. **Empty script**: zero-byte file. Response: `stdout=""`, `stderr=""`,
   `return_value=null`, exit success.

7. **`args` forwarded**: script reads `args["mode"]`, handler passes `{"mode": "fast"}`.
   Response contains expected output.

### Handler: error paths

8. **No replay loaded** (`state.adapter is None`): response error code `-32002`,
   message `"no replay loaded"`. Daemon keeps running (verified by checking
   the handler return value is `(response_dict, True)` where `True` means keep running).

9. **File not found**: `params["path"]` points to a non-existent file. Error `-32002`,
   message contains `"script not found"`.

10. **Path is a directory**: `params["path"]` is an existing directory. Error `-32002`,
    message `"script path is a directory"`.

11. **SyntaxError**: script contains `def foo(:`. Error `-32002`, message starts with
    `"syntax error:"` and includes the offending line number.

12. **RuntimeError**: script raises `raise ValueError("bad input")`. Error `-32002`,
    message `"script error: ValueError: bad input"`. Daemon does not crash.

13. **`SystemExit`**: script calls `sys.exit(0)`. Error `-32002`, message
    `"script error: SystemExit: 0"`. Daemon process continues (verified by
    confirming a subsequent valid handler call succeeds in the same test session).

14. **`KeyboardInterrupt`**: script raises `KeyboardInterrupt()`. Error `-32002`,
    message `"script error: KeyboardInterrupt: "`. Daemon continues.

### Handler: isolation

15. **stdout not leaked to daemon process stdout**: after handler returns, real
    `sys.stdout` is the original stream (redirect is properly restored via
    `contextlib` context manager even on exception).

16. **Concurrent calls do not share globals**: two sequential script executions
    with different `result` assignments return independent values.

### CLI: output format

17. **Default output — stdout content**: `result.stdout` is printed to stdout
    exactly as returned (no extra newline added if already present).

18. **Default output — stderr routing**: `result.stderr` is printed to stderr,
    not stdout.

19. **Default output — elapsed footer**: `stderr` receives a line matching
    `# elapsed: \d+ ms`.

20. **Default output — return_value footer**: when `return_value` is not null,
    stderr receives `# result: <value>`.

21. **`--json` flag**: stdout receives the raw JSON object from the daemon
    response. Nothing printed to stderr. Exit 0.

22. **Daemon error → exit 1**: daemon returns error code → error message to
    stderr, exit 1.

### CLI: `--arg` parsing

23. **Single `--arg KEY=VALUE`**: `args` dict `{"KEY": "VALUE"}` forwarded to daemon.

24. **Multiple `--arg`**: all pairs merged into one dict.

25. **`--arg` missing `=`**: Click/handler raises error, exit 2, message mentions
    invalid format.

26. **No `--arg`**: `args` defaults to `{}` in the request.

### Edge cases

27. **Large stdout**: script prints 100 KB of text. Full content returned in
    `stdout` field (no truncation at handler level).

28. **Script imports stdlib**: script does `import json; result = json.dumps([1,2])`.
    Returns successfully; no import restrictions.

29. **Script path with spaces**: path `"/tmp/my script.py"` handled correctly
    (pathlib.Path, not string splitting).

## Assertions

### Exit codes
- `0`: script executed successfully (no exception raised)
- `1`: daemon error (no session, no replay, file not found, script exception)
- `2`: CLI argument error (bad `--arg` format, missing required argument)

### stdout/stderr contract (default mode)
- stdout: exact content of `result.stdout`, byte-for-byte
- stderr: exact content of `result.stderr`, then footer lines (`# elapsed:`, optionally `# result:`)
- No interleaving of script stdout with daemon log lines

### JSON schema (`script` handler success response)
```json
{
    "stdout": <str>,
    "stderr": <str>,
    "elapsed_ms": <int, >= 0>,
    "return_value": <any JSON value or null>
}
```
- `stdout` and `stderr` are always strings (empty string, never null)
- `elapsed_ms` is a non-negative integer
- `return_value` is null when the script does not assign `result`

### Error response (JSON-RPC)
- Code always `-32002` for all script-execution errors
- `"message"` is a non-empty string
- Error output goes to stderr; stdout is empty on error

## Risks & Rollback

| Risk | Impact | Mitigation |
|------|--------|------------|
| `BaseException` catch silences real interpreter bugs | Hard to debug daemon issues | Log the full traceback to daemon log at WARNING level before returning error |
| stdout redirect not restored on exception | Daemon stdout corrupted permanently | Use `contextlib.redirect_stdout` as context manager (always restores) |
| `exec()` modifies `__builtins__` in shared namespace | Persistent state corruption between calls | Always construct a fresh `script_globals = {}` dict per call |
| Large stdout (> 10 MB) causes JSON serialization OOM | Daemon OOM | Document limit; add note that scripts should write to file for bulk data |
| `compile()` pre-flight diverges from `exec()` behavior | SyntaxError not caught pre-flight | Pre-flight covers 99% of cases; remaining caught by BaseException guard |
| Rollback | — | Revert branch; no master changes until PR squash-merge |
