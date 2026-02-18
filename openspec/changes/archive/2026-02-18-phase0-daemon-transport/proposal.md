# Proposal: phase0-daemon-transport

## Goal
Implement a minimal daemon transport skeleton over TCP localhost and connect session commands to it.

## Scope
- Add daemon process entrypoint with JSON-RPC line protocol.
- Support methods: ping, status, goto, shutdown.
- Update `open/status/goto/close` to use daemon calls.

## Non-goals
- RenderDoc replay integration.
- Multi-session support.
