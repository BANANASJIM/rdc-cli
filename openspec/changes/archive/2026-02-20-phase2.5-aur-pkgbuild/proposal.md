# Phase 2.5 OpenSpec #4: AUR PKGBUILD

## Summary

Add `aur/PKGBUILD` for `rdc-cli-git` AUR package that builds renderdoc
Python module from source and installs shell completions.

## Motivation

- Arch Linux is Jim's primary platform — AUR support is P0
- Arch's `extra/renderdoc` package does NOT include the Python module
- Users need a single `yay -S rdc-cli-git` to get everything working

## Design

### PKGBUILD structure

- `source=()`: rdc-cli git repo, renderdoc git repo, baldurk's SWIG fork zip
- `build()`: cmake renderdoc (pyrenderdoc only, no Qt/GL), build rdc-cli wheel,
  generate shell completions
- `package()`: install wheel, install renderdoc.so + librenderdoc.so to
  site-packages, install completions to system paths

### Key decisions

- renderdoc built with `-DENABLE_QRENDERDOC=OFF -DENABLE_RENDERDOCCMD=OFF`
  (Python module only, minimal build)
- Custom SWIG fork pre-fetched via `source=()` to avoid network access in build
- `librenderdoc.so` co-located with `renderdoc.so` in site-packages (RPATH=$ORIGIN)
- Shell completions installed to standard system paths

## Files

- `aur/PKGBUILD` (new)
