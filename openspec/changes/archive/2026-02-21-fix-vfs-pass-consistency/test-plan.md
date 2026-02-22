# Test Plan: fix/vfs-pass-consistency

## Scope

### In scope
- draws handler PASS column value
- VFS intermediate directory resolution and population
- `_friendly_pass_name` fallback for parenthesized formats without C=/D=

### Out of scope
- Other handler output changes
- CLI formatting layer

## Test Matrix

| Layer | Coverage |
|-------|----------|
| Unit (mock) | _friendly_pass_name variants, pass_name_for_eid, router resolution, tree_cache population |
| GPU integration | draws PASS matches passes NAME, cbuffer/bindings intermediate dirs non-empty |

## Unit Tests — `tests/unit/test_pass_vfs_fixes.py`

| Test | Assertion |
|------|-----------|
| `test_pass_name_for_eid` | EID within pass range returns friendly name |
| `test_pass_name_for_eid_no_match` | EID outside any pass returns "-" |
| `test_draws_handler_uses_friendly_name` | mock handler output PASS column != "vkCmd..." |
| `test_friendly_pass_name_clear_format` | `(Clear)` -> contains "1 Target" |
| `test_friendly_pass_name_cd_format` | `(C=Clear, D=Clear)` -> "1 Target + Depth" |
| `test_friendly_pass_name_multi_target` | `(C=Clear, C=Load, D=Clear)` -> "2 Targets + Depth" |
| `test_vfs_router_cbuffer_set_dir` | resolve `/draws/11/cbuffer/0` -> dir type |
| `test_vfs_router_bindings_set_dir` | resolve `/draws/11/bindings/0` -> dir type |
| `test_populate_draw_subtree_bindings` | after populate, bindings/.children non-empty |
| `test_populate_draw_subtree_cbuffer` | after populate, cbuffer/.children non-empty |

## GPU Tests — appended to `tests/integration/test_daemon_handlers_real.py`

| Test | Assertion |
|------|-----------|
| `test_draws_pass_matches_passes` | draws PASS column values are subset of passes NAME values |
| `test_draws_pass_no_api_name` | draws PASS column contains no "vkCmd" |
| `test_vfs_cbuffer_intermediate` | `ls /draws/<eid>/cbuffer/` non-empty |
| `test_vfs_bindings_intermediate` | `ls /draws/<eid>/bindings/` non-empty (if bindings exist) |

## Risks & Rollback
- Low risk: changes are additive helpers + route additions
- Rollback: revert branch
