# Design: phase0-structure-refactor

## Overview
Refactor command-heavy session logic into a service layer while preserving command contracts.

## Layers
- commands: user I/O + argument parsing only
- services: session orchestration and daemon interaction workflow
- transport/core: protocol and persistence helpers

## Backward compatibility
No CLI behavior changes expected. Existing command tests remain primary regression signal.
