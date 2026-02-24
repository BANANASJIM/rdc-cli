# Fix AUR Build + Add PKGBUILD Validation CI

## Problem

`yay -S rdc-cli-git` fails because PKGBUILD `makedepends` lacks `python-setuptools-scm`,
which `pyproject.toml` requires via `setuptools-scm`. No CI step catches this drift.

## Solution

1. **Fix PKGBUILDs**: Add `python-setuptools-scm` to makedepends in both `aur/PKGBUILD`
   and `aur/stable/PKGBUILD`.

2. **Add `validate-aur` CI job**: Run in `archlinux:latest` container, parse makedepends
   directly from PKGBUILD, install them, then run `python -m build --wheel --no-isolation`
   (same command PKGBUILD uses). Catches any future makedepends drift automatically.

## Scope

- `aur/PKGBUILD` — add makedepend
- `aur/stable/PKGBUILD` — add makedepend
- `.github/workflows/ci.yml` — add `validate-aur` job
