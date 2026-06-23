# Fix #257: Test Plan

## Unit: join_cmdline() — tests/unit/test_platform.py

- [ ] `test_join_cmdline_posix_simple`: POSIX branch, no-space arg — output equals `shlex.join(["app"])`
- [ ] `test_join_cmdline_posix_space`: POSIX branch, arg with spaces — output equals `shlex.join(["my app"])`
- [ ] `test_join_cmdline_posix_multi`: POSIX branch, multiple args including backslash path — `shlex.join` result
- [ ] `test_join_cmdline_windows_backslash_path`: Windows branch, `D:\path\script.das` — no single quotes in output
- [ ] `test_join_cmdline_windows_space_arg`: Windows branch, arg with spaces — double-quoted by `list2cmdline`
- [ ] `test_join_cmdline_windows_multi`: Windows branch, multiple args — matches `subprocess.list2cmdline` output

## Integration smoke (manual, Windows VM)

- [ ] `rdc capture -- myapp.exe D:\path\script.das` launches without single-quote artefacts in injected cmdline
- [ ] `rdc capture -- "my app.exe" "arg with space"` still works on POSIX
