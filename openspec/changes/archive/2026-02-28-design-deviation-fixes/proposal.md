# Design Deviation Fixes

**Date**: 2026-02-28
**Priority**: DEV-1 (P2), DEV-2 (P3), DEV-3 (P3)

## Motivation

An audit of the rdc-cli codebase against the canonical design documents identified three deviations from spec. Two are cosmetic or documentation-level issues (P3); one is a missing VFS feature that breaks the path-addressing contract (P2).

- **DEV-1**: The VFS router does not expose `/draws/{eid}/bindings/{set}/{binding}` leaf nodes despite the spec in `设计/路径寻址设计.md` requiring them. Users and tooling that navigate the VFS tree cannot read individual binding details at the slot level.
- **DEV-2**: `设计/命令总览.md` annotates `diff --trace` and `diff --trace-all` as Phase 4, but those flags depend on pixel tracing and shader debug, which are Phase 5C capabilities. The wrong annotation creates misleading roadmap expectations.
- **DEV-3**: `rdc open --listen` omits the `connect with:` convenience line from its output, which the split-mode design (`设计/远程Split模式.md`) requires. Users must manually compose the connection command from separate host/port/token lines.

## Scope

| ID | Component | Kind | Priority |
|----|-----------|------|----------|
| DEV-1 | `src/rdc/vfs/router.py`, `tree_cache.py`, `vfs.py` | Feature gap | P2 |
| DEV-2 | `Documents/Obsidian Vault/rdoc-cli/设计/命令总览.md` | Doc correction | P3 |
| DEV-3 | `src/rdc/commands/session.py` | Output line gap | P3 |

## Design

### DEV-1: VFS binding leaf node route

The VFS currently treats `/draws/{eid}/bindings/{set}` as a terminal directory. The spec requires a further level: `/draws/{eid}/bindings/{set}/{binding}` where `{binding}` is the slot index (fixedBindNumber), returning per-slot binding details.

**router.py**: Add a leaf route entry immediately after the existing bindings set route:

```python
_r(
    r"/draws/(?P<eid>\d+)/bindings/(?P<set>\d+)/(?P<binding>\d+)",
    "leaf", "bindings",
    [("eid", int), ("set", int), ("binding", int)],
)
```

**tree_cache.py**: The `binding_sets` field on the per-event cache entry currently stores `set[int]` (set indices only). Change it to `dict[int, set[int]]` mapping set index to a set of slot indices. During tree population, collect `fixedBindNumber` from both `readOnlyResources` and `readWriteResources` for each pipeline stage, mirroring the cbuffer leaf pattern used at lines 327-349. Generate `VfsNode` leaf children under each set directory node for each discovered slot.

**vfs.py**: Add an `_EXTRACTORS["bindings"]` entry that formats leaf content as TSV with columns: `EID`, `STAGE`, `KIND`, `SET`, `SLOT`, `NAME`. The extractor passes the resolved `(eid, set, binding)` triple to `_handle_bindings`, which already accepts set and binding filter parameters.

### DEV-2: diff --trace Phase annotation correction

In `设计/命令总览.md`, lines 165-166 annotate `diff --trace` and `diff --trace-all` as Phase 4. Change both annotations to Phase 5C to reflect their true dependency on pixel tracing and shader debug infrastructure.

No code changes are required.

### DEV-3: --listen connect hint output

In `src/rdc/commands/session.py`, after the `token:` output line (currently line 179), insert:

```python
click.echo(
    f"connect with: rdc open --connect"
    f" {result['host']}:{result['port']}"
    f" --token {result['token']}"
)
```

This produces a ready-to-copy connection command consistent with the spec in `设计/远程Split模式.md`. The format matches the `rdc open --connect HOST:PORT --token TOKEN` invocation documented there.

## Risks

**DEV-1**: Changing `binding_sets` from `set[int]` to `dict[int, set[int]]` alters the shape of children lists in the VFS tree. Completion logic and `ls` output that iterate over binding set children must be verified to handle the new slot-level leaf nodes without regressions. Mitigation: follow the cbuffer implementation pattern exactly, which is already exercised by existing tests.

**DEV-2**: Documentation only. Zero code risk. Annotation change may prompt questions from users who see Phase 5C on the roadmap for those flags.

**DEV-3**: Existing tests that assert the exact `rdc open --listen` output will fail if they check for a specific number of output lines or match on the full stdout string. Those tests must be updated to include the new hint line. No behavioral change occurs.
