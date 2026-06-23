# Fix #257: Tasks

- [x] `src/rdc/_platform.py`: add `import shlex`; add `join_cmdline(args: list[str]) -> str`
- [x] `src/rdc/commands/capture.py`: replace both `shlex.join(app_args)` call sites with `_platform.join_cmdline(app_args)`
- [x] `src/rdc/commands/capture.py`: remove now-unused `import shlex`
- [x] `tests/unit/test_platform.py`: add `TestJoinCmdline` with 6 cases covering both branches
- [x] `pixi run lint && pixi run typecheck && pixi run test` passes
