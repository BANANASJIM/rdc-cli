# Test Plan: AUR Build Fix + CI Validation

## Automated (CI)

1. **`validate-aur` job passes** — new CI job in `archlinux:latest` container successfully
   builds wheel using makedepends parsed from PKGBUILD.

## Manual

1. **`yay -S rdc-cli-git`** succeeds after PKGBUILD is pushed to AUR.
2. CI shows `validate-aur` job in PR check list.
