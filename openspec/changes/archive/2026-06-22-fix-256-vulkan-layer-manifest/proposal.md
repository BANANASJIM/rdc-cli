# Fix #256: Vulkan layer manifest template substitution + duplicate layer detection

## Motivation

Issue #256: on Windows, `rdc`'s own implicit Vulkan capture layer can never self-enable,
so Vulkan captures launched through `rdc capture` silently time out.

Two root causes were verified against the real code and the cloned RenderDoc source tree
(`.local/renderdoc-build/renderdoc/renderdoc/driver/vulkan/`):

| Cause | Where | Effect |
|-------|-------|--------|
| Unsubstituted CMake template vars in the layer manifest | `_build_renderdoc.py:_install_vulkan_layer` | `rdc`'s layer never self-enables |
| `doctor` returns green on the first manifest and never warns on duplicates | `commands/doctor.py:_check_win_vulkan_layer` | the system + `rdc` split-brain stays invisible |

### Cause 1: unsubstituted template vars

Upstream RenderDoc substitutes `renderdoc.json` via CMake `configure_file`, but that block is
UNIX-only (`driver/vulkan/CMakeLists.txt`: the substitution lives inside `elseif(UNIX)`). On
Windows the file ships verbatim (`<None Include="renderdoc.json"/>`), so the manifest still
contains `@...@` placeholders.

`_install_vulkan_layer` reads that template with `json.loads` and rewrites only `library_path`,
leaving the placeholders intact. In the in-scope version (`RDOC_TAG = "v1.41"`) the surviving
placeholders are:

- `enable_environment`: `{"@VULKAN_ENABLE_VAR@": "1"}` — the enable key the loader looks for is
  literally `@VULKAN_ENABLE_VAR@`, which no process ever sets, so the layer is never enabled.
- `implementation_version`: `"@RENDERDOC_VERSION_MINOR@"`.
- `disable_environment` key: `DISABLE_VULKAN_RENDERDOC_CAPTURE_@RENDERDOC_VERSION_MAJOR@_@RENDERDOC_VERSION_MINOR@`.

Newer upstream templates (e.g. v1.44) additionally template `name` as `"@VULKAN_LAYER_NAME@"`,
so the fix force-sets `name` too, making it version-robust.

The canonical substitution values come from `driver/vulkan/CMakeLists.txt`:
`VULKAN_ENABLE_VAR = ENABLE_VULKAN_${RDOC_BASE_NAME_UPPER}_CAPTURE` with base name `renderdoc`,
i.e. `ENABLE_VULKAN_RENDERDOC_CAPTURE`; the disable key is
`DISABLE_VULKAN_RENDERDOC_CAPTURE_<MAJOR>_<MINOR>`. The version is the SSOT `RDOC_TAG`
(or the `--version` arg), e.g. `v1.41` -> MAJOR=1, MINOR=41. This matches
`api/replay/version.h` in the cloned tree (`RENDERDOC_VERSION_MAJOR 1`, `RENDERDOC_VERSION_MINOR 41`).

This enable var (`ENABLE_VULKAN_RENDERDOC_CAPTURE`) is the same one already set at launch by
`capture_core.py:_build_launch_env`, so once the manifest declares it as its enable key the
existing launch env actually takes effect.

### Cause 2: doctor never warns on duplicate layers

`_check_win_vulkan_layer` collects candidate manifests from both HKLM and HKCU `ImplicitLayers`,
but returns green on the FIRST existing manifest. When a system RenderDoc install and `rdc`'s own
install both register a layer named `VK_LAYER_RENDERDOC_Capture`, the Vulkan loader picks one
non-deterministically (the split-brain), and capture silently times out. `doctor` gives no signal.

## Design

### Part 1: substitute all manifest template vars (`_install_vulkan_layer`)

Thread the in-scope version into `_install_vulkan_layer` (currently it receives only
`install_dir` and `build_dir`; `main()` passes `args.version`, default `RDOC_TAG`). Derive
`(major, minor)` from that version string with a small `_parse_version` helper (`v1.41` ->
`(1, 41)`).

After `json.loads`, force every layer field to a fully-resolved value rather than trusting the
template:

- `name = "VK_LAYER_RENDERDOC_Capture"` (canonical; robust against `@VULKAN_LAYER_NAME@`).
- `enable_environment = {"ENABLE_VULKAN_RENDERDOC_CAPTURE": "1"}`.
- `disable_environment = {f"DISABLE_VULKAN_RENDERDOC_CAPTURE_{major}_{minor}": "1"}`.
- `implementation_version = str(minor)`.
- `library_path = ".\\renderdoc.dll"` (unchanged behavior).

After serialization, assert no `@` remains in the written text. If any does, raise a clear
`RuntimeError` naming the offending content. This guard makes a future template change that
introduces a new placeholder fail loudly instead of silently shipping a dead layer.

### Part 2: detect duplicate layers (`_check_win_vulkan_layer`)

Refactor the registry enumeration into a small helper `_enumerate_implicit_layers()` that returns
the list of manifest paths registered under HKLM+HKCU `ImplicitLayers`. Importing `winreg` inside
the helper keeps it unit-testable cross-platform by mocking `sys.modules["winreg"]`.

In `_check_win_vulkan_layer`, resolve each manifest's `layer.name` and collect those that resolve
to `VK_LAYER_RENDERDOC_Capture`. If more than one resolves to that name, return a FAIL
`CheckResult` listing each manifest path, its resolved DLL, and its version. A single layer keeps
the existing green behavior (`registered at {path}`).

## Risks

- Force-setting `name`/`enable_environment` ignores any future upstream rename of these fields.
  Mitigated by the no-`@` guard (a renamed placeholder would still be caught) and by the fact that
  these names are loader-facing constants, not free to change without breaking the loader anyway.
- Duplicate detection reads each manifest file; a malformed JSON manifest is skipped (best-effort)
  rather than failing the whole check.

## DEFERRED: Part 3 — force `rdc`'s own layer for the spawned child

A third improvement was considered and is explicitly DEFERRED to a follow-up: forcing the spawned
capture target to load `rdc`'s own layer (and only that one) via the `ExecuteAndInject` env arg in
`capture_core.py`, using `VK_ADD_LAYER_PATH` / `VK_LOADER_LAYERS_ENABLE` / `VK_LOADER_LAYERS_DISABLE`.

Rationale for deferral:

1. It cannot be verified without a real Windows box with a dual RenderDoc install (system + `rdc`).
   The split-brain only reproduces with two registered layers; CI cannot exercise it.
2. The two layers share the exact name `VK_LAYER_RENDERDOC_Capture`, so
   `VK_LOADER_LAYERS_DISABLE=VK_LAYER_RENDERDOC_Capture` would disable BOTH layers, not just the
   system one. There is no by-name way to disable only the foreign layer. Selecting `rdc`'s layer
   while suppressing the other is an unresolved design question (candidate approaches:
   `VK_LOADER_LAYERS_ENABLE` precedence, manifest-path scoping, or renaming `rdc`'s layer — each
   has trade-offs that need on-device validation).

Parts 1 and 2 are independently correct and shippable: Part 1 makes `rdc`'s layer enable-able at
all, and Part 2 surfaces the split-brain to the user so they can act, without needing the unresolved
Part 3 design.
