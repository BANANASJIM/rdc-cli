# Tasks: Design Deviation Fixes

## DEV-1: VFS Binding Leaf Node Route (Agent A — worktree)

- [ ] `src/rdc/vfs/router.py` — Add leaf route for `/draws/{eid}/bindings/{set}/{binding}` with `handler="bindings"`
- [ ] `src/rdc/vfs/tree_cache.py` — Change `binding_sets: set[int]` to `dict[int, set[int]]`; collect `fixedBindNumber` from `readOnlyResources` and `readWriteResources`; create `VfsNode` leaf nodes and set children lists on set-directory nodes (mirror cbuffer pattern at lines 342-349)
- [ ] `src/rdc/commands/vfs.py` — Add `_EXTRACTORS["bindings"]` with TSV formatter
- [ ] `tests/unit/test_vfs_router.py` — Add binding leaf route resolution tests
- [ ] `tests/unit/test_vfs_tree_cache.py` (or equivalent) — Add binding leaf node population tests
- [ ] `tests/unit/test_vfs_commands.py` — Add binding extractor TSV tests (T1-5, T1-6)

## DEV-2: diff --trace Phase Annotation (main agent — doc only)

- [ ] Obsidian `设计/命令总览.md` — Change Phase `"4"` to `"5C"` on the `diff --trace` and `diff --trace-all` lines (lines 165–166)

## DEV-3: --listen Connect Hint (Agent B — worktree)

- [ ] `src/rdc/commands/session.py` — Add `"connect with:"` output line after the token line in `--listen` mode
- [ ] `tests/unit/test_split_core.py` — Add assertion for `"connect with:"` line in `test_listen_outputs_connection_info`

## Post-implementation

- [ ] Merge worktree outputs back to feature branch
- [ ] Run `pixi run lint && pixi run test` — zero failures allowed
- [ ] New Opus subagent code review
