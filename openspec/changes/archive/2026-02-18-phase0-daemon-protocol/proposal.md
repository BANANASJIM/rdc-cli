# Proposal: phase0-daemon-protocol

## Goal
Add a minimal JSON-RPC protocol skeleton for upcoming daemon work.

## Scope
- Define JSON-RPC request/response models.
- Add local protocol helpers for `ping` and `shutdown` payloads.
- Add unit tests for protocol validation.

## Non-goals
- TCP server implementation.
- Process lifecycle management.
