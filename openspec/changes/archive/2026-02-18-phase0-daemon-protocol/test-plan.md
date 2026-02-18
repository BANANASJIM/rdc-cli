# Test Plan: phase0-daemon-protocol

## Scope
- In scope: JSON-RPC message model validation and helper constructors.
- Out of scope: daemon socket transport.

## Test Matrix
- Unit: request/response builder and validation behavior.
- Mock: none needed.

## Cases
- Happy path: build `ping` and `shutdown` requests and parse responses.
- Error path: invalid jsonrpc version rejected.
- Edge: missing id for request rejected.

## Assertions
- Strict JSON-RPC `jsonrpc="2.0"`.
- request includes method and id.

## Risks
- Future fields can evolve; keep helpers backward compatible.
