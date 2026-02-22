#!/usr/bin/env bash
# Auto-link .local/renderdoc from main worktree into current worktree.
# Called by: pixi run sync
# No-op if .local/renderdoc already exists or we're in the main worktree.
set -euo pipefail

[ -d .local/renderdoc ] && exit 0

main=$(git worktree list --porcelain | head -1 | sed 's/worktree //')
[ "$main" = "$(pwd)" ] && exit 0
[ -d "$main/.local/renderdoc" ] || exit 0

mkdir -p .local
ln -s "$main/.local/renderdoc" .local/renderdoc
echo "linked .local/renderdoc → $main/.local/renderdoc"
