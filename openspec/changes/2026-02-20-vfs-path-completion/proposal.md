# Proposal: VFS Path Shell Completion

## Summary

Wire Click 8's native `shell_complete` callback into `rdc ls`, `rdc cat`, and
`rdc tree` path arguments so that `rdc ls /dr<TAB>` expands to `/draws/`.

## Motivation

`rdc completion` generates shell scripts that handle command/option completion,
but VFS path arguments complete as filesystem paths (useless). The hidden
`_complete` command already queries the daemon for VFS children but is not
connected to the shell completion system.

## Design

Add a single `_complete_vfs_path(ctx, param, incomplete)` callback that:

1. Parses `incomplete` into `dir_path` + `prefix`
2. Calls `_daemon_call("vfs_ls", {"path": dir_path})`
3. Filters children by prefix
4. Returns `list[CompletionItem]` with `/` suffix for directories

Wire it via `shell_complete=_complete_vfs_path` on the `path` argument of
`ls_cmd`, `cat_cmd`, and `tree_cmd`.

No new shell scripts needed — Click's generated scripts already invoke the
completion system. Users must re-source their completion script after upgrade.

### Edge cases

- No active session → `_daemon_call` raises `SystemExit` → return `[]`
- Root completion (`/d`) → list `/` children, filter by `d`
- Nested completion (`/draws/14`) → list `/draws/` children, filter by `14`
- Empty incomplete → list all children of `/`

## Scope

**In:** `_complete_vfs_path` callback, `shell_complete=` on 3 commands, unit tests.

**Out:** `_complete` hidden command removal (keep for manual testing), new shell
script format, fish/bash-specific workarounds.

## Files Changed

- `src/rdc/commands/vfs.py` — add callback, modify 3 argument decorators
- `tests/unit/test_vfs_completion.py` — new test file
