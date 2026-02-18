# Test Plan: phase0-daemon-transport

## Scope
- In scope: daemon lifecycle and command transport for ping/status/goto/shutdown.
- Out of scope: replay operations.

## Test Matrix
- Unit: protocol encode/decode and token checks.
- Integration-lite: start daemon subprocess, perform requests, shutdown.

## Cases
- Happy path: open starts daemon, status returns current_eid, goto updates eid, close shuts down.
- Error path: invalid token rejected, goto without active session fails.
- Edge: daemon dies, status reports failure.

## Assertions
- Commands return code 0 on success, 1 on failures.
- Daemon only accepts requests with matching token.
