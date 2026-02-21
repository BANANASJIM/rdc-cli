# Test Plan: AUR PKGBUILD

## Scope

### In scope
- PKGBUILD syntax and structure
- Build-time dependency completeness
- Runtime dependency completeness
- Shell completion installation paths

### Out of scope
- Actual AUR submission (done manually)
- Full makepkg build test (requires clean chroot, done manually)

## Test Matrix

| Layer | Target | Method |
|-------|--------|--------|
| Static | PKGBUILD syntax | `namcap` lint |
| Static | Shell paths | Review standard Arch paths |
| Manual | Full build | `makepkg -s` in clean chroot |
| Manual | Install + smoke | `pacman -U`, `rdc doctor`, `rdc --help` |

## Assertions

- `pkgver()` produces valid version from git tags
- `build()` compiles renderdoc with pyrenderdoc only (no Qt, no GL)
- `package()` installs renderdoc.so + librenderdoc.so to site-packages
- Shell completions at standard paths (bash/zsh/fish)
- `rdc doctor` passes after install (renderdoc module found)

## Risks

- renderdoc build time is ~5min (acceptable for AUR -git package)
- Python version upgrade breaks renderdoc.so (rebuild required)
