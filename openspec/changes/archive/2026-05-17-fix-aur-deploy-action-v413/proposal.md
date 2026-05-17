# Fix AUR Deploy Action Pin: v4.1.1 → v4.1.3

## Problem

### Symptom

`AUR Publish` workflow run 26001352704, job `Publish rdc-cli (stable)`, failed on
the v0.5.5 tag with:

```
bash: --command: invalid option
```

The job exited before `/build.sh` ran. The `aur-git` job was not triggered (it
fires on branch push only). The v0.5.5 PyPI release and GitHub Release were
already shipped; the AUR `rdc-cli` package was not updated.

### Root cause

Both jobs pin
`KSXGitHub/github-actions-deploy-aur@2ac5a4c1d7035885d46b10e3193393be8460b6f1`
(v4.1.1). That action's `entrypoint.sh` ends with:

```sh
exec runuser builder --command 'bash -l -c /build.sh'
```

With the `util-linux` `runuser` binary now present in the current `archlinux:base`
Docker image, the `--command` flag is parsed as an option to `bash` (su(1)-compat
syntax passes the argument onward), and bash has no `--command` option. The process
crashes before `/build.sh` ever runs.

This latent bug existed in v3.0.1 through v4.1.1 of the action. Earlier workflow
runs on v0.5.2/v0.5.3 were green because the then-current `archlinux:base` image
did not expose the issue. A recent Arch base image update surfaced it.

### Why `post_process: git checkout -B master` is innocent

`build.sh` (which clones the AUR repo, evaluates `$post_process`, commits, and
force-pushes to AUR master) is byte-identical across v4.1.1, v4.1.2, and v4.1.3.
The crash happens in `entrypoint.sh` before `build.sh` is ever invoked, so
`post_process` was never reached and plays no role in the failure.

### Fix-forward context

The v0.5.5 PyPI package and GitHub Release are already published and cannot be
retracted. The only outstanding item is the AUR `rdc-cli` package backfill, which
requires a successful workflow run for version 0.5.5.

## Solution

Bump the action pin on **both** jobs in `.github/workflows/aur.yml`:

| Location | Current | After |
|---|---|---|
| Line 25, job `aur-git` | `2ac5a4c1d7035885d46b10e3193393be8460b6f1 # v4.1.1` | `da03e160361ce01bf087e790b6ffd196d7dccff7 # v4.1.3` |
| Line 72, job `aur-stable` | `2ac5a4c1d7035885d46b10e3193393be8460b6f1 # v4.1.1` | `da03e160361ce01bf087e790b6ffd196d7dccff7 # v4.1.3` |

All other inputs on both jobs (`force_push: true`, `post_process: git checkout -B
master`, `pkgname`, `pkgbuild`, credential secrets) remain unchanged.

v4.1.3 fixes `entrypoint.sh` to:

```sh
exec runuser -u builder -- bash -l /build.sh
```

This is the POSIX-correct `runuser` invocation that does not pass arguments to
bash. v4.1.2 used `runuser -u builder -- bash -l -c /build.sh` (also correct);
v4.1.3 drops the redundant `-c`.

## Why the bump is safe with respect to #183 and #184

The `post_process: git checkout -B master` input (PR #183, detached-HEAD fix) and
`force_push: true` input (PR #184) are passed to `build.sh` as environment
variables, not to `entrypoint.sh`. Because `build.sh` is byte-identical across
v4.1.1, v4.1.2, and v4.1.3, both fixes are fully preserved by this pin bump.

## Residual risk

The action uses `FROM archlinux:base` with no image digest pin. A future update to
the Arch base image could introduce a different incompatibility regardless of the
action tag. This is inherent to the action's design; no mitigation is proposed
here beyond monitoring workflow runs after future Arch base image refreshes.

## Spec delta

There is no existing spec in `openspec/specs/` covering AUR publishing or CI
release workflows. No spec delta applies.

## Post-merge backfill (operational, not a code change)

After this PR merges, manually trigger `AUR Publish` via `workflow_dispatch` with
input `version=0.5.5`. The `aur-stable` job will:
1. Normalize version → `0.5.5`
2. Checkout `refs/tags/v0.5.5` (already exists)
3. `curl` the tarball and compute sha256
4. Patch `aur/stable/PKGBUILD`
5. Deploy to AUR via the fixed action

This is the acceptance gate for this change.
