# Test Plan: Design Deviation Fixes (DEV-1, DEV-2, DEV-3)

## DEV-1: VFS Binding Leaf Node Route

### `tests/unit/test_vfs_router.py` — router resolution

| ID | Component | Description | Expected Result |
|----|-----------|-------------|-----------------|
| T1-1 | VFS router | `resolve_path("/draws/142/bindings/0/0")` | Returns `PathMatch(kind="leaf", handler="bindings", args={"eid": 142, "set": 0, "binding": 0})` |
| T1-2 | VFS router | `resolve_path("/draws/142/bindings/0/5")` | Returns `PathMatch(kind="leaf", handler="bindings", args={"eid": 142, "set": 0, "binding": 5})` |

### `tests/unit/test_vfs_tree_cache.py` — tree population

| ID | Component | Description | Expected Result |
|----|-----------|-------------|-----------------|
| T1-3 | Tree cache | `populate_draw_subtree` called for a draw with bindings | Creates child nodes at path `bindings/{set}/{binding}` for each descriptor |
| T1-4 | Tree cache | Binding child nodes structure | Each binding child has `kind="leaf"` and `name` equal to the binding slot number as a string |

### `tests/unit/test_vfs_commands.py` — extractor behavior

| ID | Component | Description | Expected Result |
|----|-----------|-------------|-----------------|
| T1-5 | VFS extractor | `_EXTRACTORS["bindings"]` called with valid rows | Formats output as TSV with header line `EID\tSTAGE\tKIND\tSET\tSLOT\tNAME` followed by data rows |
| T1-6 | VFS extractor | `_EXTRACTORS["bindings"]` called with empty rows list | Returns only the header line with no data rows and no error |

---

## DEV-2: `diff --trace` Phase Annotation (doc-only)

| ID | Component | Description | Expected Result |
|----|-----------|-------------|-----------------|
| T2-1 | Documentation | Manual check of `设计/命令总览.md` for `diff --trace` entries | Phase annotation shows `5C` (changed from `4`) for all `diff --trace` command lines |

No automated code tests required for this item.

---

## DEV-3: `--listen` "connect with:" Output Line

### `tests/unit/test_split_core.py` — CLI output assertions

| ID | Component | Description | Expected Result |
|----|-----------|-------------|-----------------|
| T3-1 | `--listen` output | `test_listen_outputs_connection_info` asserts "connect with:" line | Output contains the line `connect with: rdc open --connect 0.0.0.0:9999 --token secret123` |
| T3-2 | `--listen` output | Existing host/port/token line assertions still pass | Output still contains separate host, port, and token lines (no regression) |
