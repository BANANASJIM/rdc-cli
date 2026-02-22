# Tasks: fix-event-break-and-test-flaky

## Implementation

- [x] Write OpenSpec (proposal + test-plan + tasks)
- [x] Create branch `fix/event-break-and-test-flaky`
- [ ] Write regression test `test_event_multi_event_all_params_shown` in `test_draws_events_daemon.py`
- [ ] Add monkeypatch to `TestNoSession` (6 tests) in `test_draws_events_cli.py`
- [ ] Add monkeypatch to `test_close_session_without_state` in `test_session_service.py`
- [ ] Delete `break` at `query.py:423` in `_handle_event`
- [ ] Run `pixi run check` — all green
- [ ] Agent code review (zero P0/P1)
- [ ] Commit, push, create PR
- [ ] Merge after CI green + review
- [ ] Archive OpenSpec
