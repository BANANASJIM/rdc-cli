# Fix #256: Tasks

## Part 1: manifest substitution

- [x] `_build_renderdoc.py`: add `_parse_version(version) -> (major, minor)` helper
- [x] `_build_renderdoc.py`: `_install_vulkan_layer` takes a `version` arg
- [x] `_build_renderdoc.py`: substitute all manifest fields (`name`, `enable_environment`,
      `disable_environment`, `implementation_version`, `library_path`)
- [x] `_build_renderdoc.py`: assert no `@` remains after serialization, else raise
- [x] `_build_renderdoc.py`: `main()` forwards `args.version` to `_install_vulkan_layer`

## Part 2: duplicate detection

- [x] `commands/doctor.py`: extract `_enumerate_implicit_layers()` helper (mockable `winreg`)
- [x] `commands/doctor.py`: resolve each manifest `layer.name`; warn when >1 resolves to
      `VK_LAYER_RENDERDOC_Capture`, listing path + DLL + version
- [x] `commands/doctor.py`: dedup candidates by resolved path so one manifest registered
      under both hives is not double-counted

## Tests

- [x] `test_build_renderdoc.py`: real-template substitution case + guard case + `_parse_version`
- [x] `test_build_renderdoc.py`: keep existing clean-fixture test green
- [x] `test_doctor.py`: duplicate-detection cases via mocked `winreg` (incl. same-manifest-both-hives dedup)
- [x] `pixi run lint && pixi run typecheck && pixi run test` all green
