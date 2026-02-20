# Tasks: phase2-descriptors

## Phase A — Mock infrastructure

- [ ] Add `DescriptorType` `IntEnum` to `mock_renderdoc.py` (Unknown=0, ConstantBuffer=1, Sampler=2, ImageSampler=3, Image=4, TypeBuffer=5, ReadWriteImage=6, ReadWriteBuffer=7, ReadWriteTypedBuffer=8, InputAttachment=9)
- [ ] Add `AddressMode` `IntEnum` to `mock_renderdoc.py` (Wrap=0, Mirror=1, MirrorOnce=2, ClampEdge=3, ClampBorder=4)
- [ ] Add `DescriptorAccess` dataclass to `mock_renderdoc.py`: `stage: ShaderStage`, `type: DescriptorType`, `index: int`, `arrayElement: int`, `descriptorStore: ResourceId`, `byteOffset: int`, `byteSize: int`, `staticallyUnused: bool`
- [ ] Add `SamplerDescriptor` dataclass to `mock_renderdoc.py`: `addressU: AddressMode`, `addressV: AddressMode`, `addressW: AddressMode`, `filter: str`, `compareFunction: str`, `minLOD: float`, `maxLOD: float`, `mipBias: float`, `maxAnisotropy: float`, `seamlessCubeMap: bool`, `maxLODClamp: float`, `borderColor: FloatVector`
  - Note: `filter` is `str` in mock (simplification); real API has opaque SWIG type, handler uses `str(getattr(s, 'filter', ''))`
- [ ] Add `UsedDescriptor` dataclass to `mock_renderdoc.py`: `access: DescriptorAccess`, `descriptor: Descriptor`, `sampler: SamplerDescriptor`
  - Note: `UsedSampler` is NOT replaced — it remains for `GetSamplers()`. `UsedDescriptor` is a new independent class for `GetAllUsedDescriptors()`
- [ ] Add `_used_descriptors: list[UsedDescriptor]` field to `MockPipeState.__init__`
- [ ] Add `GetAllUsedDescriptors(onlyUsed: bool) -> list[UsedDescriptor]` method to `MockPipeState`

## Phase B — Tests: daemon handler

- [ ] Create `tests/unit/test_descriptors_daemon.py`
- [ ] Test happy path — 2 `ConstantBuffer` descriptors (VS + PS): assert `result["eid"]` matches, `len(result["descriptors"]) == 2`, each entry has keys `stage`, `type`, `index`, `array_element`, `resource_id`, `format`, `byte_size`; `type == "ConstantBuffer"`
- [ ] Test mixed types — 1 ConstantBuffer + 1 Image + 1 Sampler: assert `type` values are `"ConstantBuffer"`, `"Image"`, `"Sampler"`; Sampler entry has `"sampler"` sub-dict with `filter`, `address_u`, `address_v`, `address_w`, `compare_function`, `min_lod`, `max_lod`, `mip_bias`, `max_anisotropy`; non-sampler entries do NOT have `"sampler"` key
- [ ] Test empty — `GetAllUsedDescriptors` returns `[]`: assert `result["descriptors"] == []`
- [ ] Test no adapter (`state.adapter is None`): assert error code `-32002`
- [ ] Test eid out of range: assert error code `-32002`

## Phase C — Daemon handler implementation

- [ ] Add `descriptors` branch to `_handle_request` in `daemon_server.py`
- [ ] Return `-32002` when `state.adapter is None` (check FIRST, before eid)
- [ ] Accept `eid` param; call `_set_frame_event(state, eid)` — return `-32002` on error
- [ ] `pipe_state = state.adapter.get_pipeline_state()` (adapter pattern, NOT `controller.GetPipelineState()`)
- [ ] `used = pipe_state.GetAllUsedDescriptors(True)`
- [ ] For each `UsedDescriptor`, extract dict: `stage` (`.access.stage.name`), `type` (`.access.type.name`), `index` (`.access.index`), `array_element` (`.access.arrayElement`), `resource_id` (`int(.descriptor.resource)`), `format` (`.descriptor.format.Name()` or `""`), `byte_size` (`.descriptor.byteSize`)
  - Note: use `access.type.name` for descriptor category, NOT `descriptor.type` (which is an int)
- [ ] For Sampler / ImageSampler entries, add `"sampler"` sub-dict: `address_u` (`str(.sampler.addressU)`), `address_v`, `address_w`, `filter` (`str(getattr(.sampler, 'filter', ''))`), `compare_function`, `min_lod` (`.sampler.minLOD`), `max_lod`, `mip_bias`, `max_anisotropy`
- [ ] Return `{"eid": eid, "descriptors": [...]}`
- [ ] Verify Phase B tests pass: `pixi run test -k test_descriptors_daemon`

## Phase D — Tests: VFS route + tree cache

- [ ] Add route test to `tests/unit/test_vfs_router.py`: `/draws/42/descriptors` → `PathMatch(kind="leaf", handler="descriptors", args={"eid": 42})`
- [ ] Add tree cache test to `tests/unit/test_vfs_tree_cache.py`: `build_vfs_skeleton` produces `"descriptors"` in children of `/draws/<eid>` node; `/draws/<eid>/descriptors` is `VfsNode(kind="leaf")`
  - Note: update existing `test_draw_node_structure` expected children list

## Phase E — VFS route + tree cache + extractor

- [ ] Add route to `router.py`: `_r(r"/draws/(?P<eid>\d+)/descriptors", "leaf", "descriptors", [("eid", int)])`
- [ ] Add `"descriptors"` to `_DRAW_CHILDREN` in `tree_cache.py`
- [ ] Add `tree.static[f"{prefix}/descriptors"] = VfsNode("descriptors", "leaf")` in the draw loop in `build_vfs_skeleton` (static leaf, no `populate_draw_subtree` change)
- [ ] Add `"descriptors"` extractor to `_EXTRACTORS` in `commands/vfs.py`: TSV with header `STAGE\tTYPE\tINDEX\tARRAY_EL\tRESOURCE\tFORMAT\tBYTE_SIZE`, one row per descriptor entry from `result["descriptors"]`
- [ ] Verify Phase D tests pass: `pixi run test -k "test_vfs_router or test_vfs_tree_cache"`

## Phase F — Mock API sync

- [ ] Add `DescriptorType` and `AddressMode` to `ENUM_PAIRS` in `tests/integration/test_mock_api_sync.py`
- [ ] Add `DescriptorAccess`, `SamplerDescriptor`, `UsedDescriptor` to `STRUCT_PAIRS` in `tests/integration/test_mock_api_sync.py`
- [ ] Verify sync tests pass: `pixi run test -k test_mock_api_sync`

## Phase G — GPU integration tests

- [ ] Add `test_descriptors_basic` to `tests/integration/test_daemon_handlers_real.py`: call daemon `descriptors` for a known draw eid on `hello_triangle.rdc`, assert `result["descriptors"]` is a list with >= 2 entries, each has `stage`, `type`, `index`, `resource_id`, `format`, `byte_size`; all `type == "ConstantBuffer"`; `resource_id > 0`; `byte_size > 0`
- [ ] Add `test_descriptors_sampler` (conditional): use `separate_image_sampler` capture if available, else `pytest.skip`; assert >= 3 entries with ConstantBuffer + Image + Sampler types; Sampler entry has `"sampler"` dict with non-empty `filter`
- [ ] Add `test_vfs_cat_descriptors`: `rdc cat /draws/<eid>/descriptors` on hello_triangle → exit 0, first line is `STAGE\tTYPE\tINDEX\tARRAY_EL\tRESOURCE\tFORMAT\tBYTE_SIZE`
- [ ] Run GPU tests: `RENDERDOC_PYTHON_PATH=... pixi run test-gpu -k test_descriptor`

## Phase H — Final verification

- [ ] `pixi run check` passes (ruff lint + ruff format + mypy strict + pytest >= 80% coverage)
- [ ] GPU tests pass on `hello_triangle.rdc`
- [ ] All task checkboxes checked
- [ ] Archive: move `openspec/changes/2026-02-20-phase2-descriptors/` → `openspec/changes/archive/`
- [ ] Merge delta into `openspec/specs/`
- [ ] Update `进度跟踪.md` in Obsidian vault
