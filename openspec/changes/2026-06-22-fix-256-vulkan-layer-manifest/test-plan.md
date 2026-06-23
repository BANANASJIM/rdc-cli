# Fix #256: Test Plan

## Part 1: manifest template substitution (`test_build_renderdoc.py`)

- [ ] Unit: real-template fixture containing `@VULKAN_ENABLE_VAR@`, `@VULKAN_LAYER_NAME@`,
      `@RENDERDOC_VERSION_MAJOR@`, `@RENDERDOC_VERSION_MINOR@` -> written manifest has zero `@`.
- [ ] Unit: written `enable_environment == {"ENABLE_VULKAN_RENDERDOC_CAPTURE": "1"}`.
- [ ] Unit: written `name == "VK_LAYER_RENDERDOC_Capture"`.
- [ ] Unit: written `disable_environment` has key `DISABLE_VULKAN_RENDERDOC_CAPTURE_1_41` for version `v1.41`.
- [ ] Unit: written `library_path == ".\\renderdoc.dll"`.
- [ ] Unit: `implementation_version == "41"` for version `v1.41`.
- [ ] Unit: existing clean-fixture test (`library_path` only) stays green.
- [ ] Unit: a fixture that would leave a stray `@FOO@` after substitution raises a clear error
      (guard test) — exercised by force-injecting an extra placeholder field.
- [ ] Unit: `_parse_version("v1.41") == (1, 41)` and `_parse_version("1.44") == (1, 44)`.
- [ ] Unit: `main()` forwards `args.version` into `_install_vulkan_layer` on Windows.

## Part 2: duplicate layer detection (`test_doctor.py`)

Cross-platform via mocked `winreg` (`patch.dict("sys.modules", {"winreg": fake})`):

- [ ] Unit: two registered manifests, both resolving to `VK_LAYER_RENDERDOC_Capture` with
      different DLLs -> FAIL CheckResult listing both manifest paths.
- [ ] Unit: single registered manifest resolving to `VK_LAYER_RENDERDOC_Capture` -> ok,
      `registered at {path}`.
- [ ] Unit: `_enumerate_implicit_layers()` returns manifest paths from both HKLM and HKCU.
- [ ] Existing Windows-only tests stay green.

## Manual (Windows VM, post-merge)

- [ ] `rdc setup-renderdoc` then inspect installed `renderdoc.json`: no `@` placeholders,
      `enable_environment` is `ENABLE_VULKAN_RENDERDOC_CAPTURE`.
- [ ] With both a system RenderDoc and `rdc`'s install registered, `rdc doctor` reports the
      duplicate `win-vulkan-layer` as FAIL listing both paths.
- [ ] `rdc capture` against a Vulkan target no longer times out (Part 1 effect).
