# Test Plan: VFS Path Shell Completion

## Scope

**In:** `_complete_vfs_path` callback logic, integration with `ls_cmd`/`cat_cmd`/`tree_cmd`.

**Out:** Actual shell integration (bash/zsh/fish runtime behavior), `_complete` hidden command.

## Test Matrix

| Layer | What | Count |
|-------|------|-------|
| Unit | `_complete_vfs_path` callback with mock daemon | 8 |
| Unit | Argument wiring verification | 3 |

## Cases

### Happy path

1. **Root completion** — incomplete=`/d` → returns `["/draws/"]`
2. **Root all** — incomplete=`` (empty) → returns all root children
3. **Nested dir** — incomplete=`/draws/` → returns EID children
4. **Nested partial** — incomplete=`/draws/14` → filters to matching EIDs
5. **Leaf vs dir suffix** — dirs get `/`, leaves don't
6. **Deep path** — incomplete=`/draws/142/sh` → returns `/draws/142/shader/`

### Error path

7. **No session** — `_daemon_call` raises `SystemExit` → returns `[]`
8. **Invalid path** — daemon returns empty children → returns `[]`

### Wiring

9. **ls_cmd path has shell_complete** — verify callback is wired
10. **cat_cmd path has shell_complete** — verify callback is wired
11. **tree_cmd path has shell_complete** — verify callback is wired

## Assertions

- Return type is `list[CompletionItem]`
- Each item's `value` is a full path (not just the child name)
- Directory items end with `/`
- Leaf items do not end with `/`
- Empty list on error (no exception propagation)

## Risks & Rollback

- **Risk:** Completion callback makes daemon call during shell completion — adds
  latency. Mitigation: VFS ls is fast (tree cache), acceptable for TAB.
- **Rollback:** Remove `shell_complete=` parameter from 3 decorators.
