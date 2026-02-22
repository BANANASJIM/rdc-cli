# Tasks: Daemon Startup Timeout Fix

- [x] Create OpenSpec
- [x] Opus review + revisions
- [ ] Modify `start_daemon()`: stderr=PIPE
- [ ] Modify `wait_for_ping()`: timeout 15s, proc poll, return tuple
- [ ] Modify `open_session()`: pass proc, communicate() on failure
- [ ] Add 6 unit tests
- [ ] `pixi run lint && pixi run test`
