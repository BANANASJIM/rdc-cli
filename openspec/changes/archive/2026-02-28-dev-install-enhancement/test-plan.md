# Test Plan: Dev Install Enhancement

## Shell Detection

### `tests/unit/test_dev_install.py`

| ID | Component | Description | Expected Result |
|----|-----------|-------------|-----------------|
| SD-1 | `_detect_shell` | `SHELL=/bin/zsh` | Returns `"zsh"` |
| SD-2 | `_detect_shell` | `SHELL=/usr/bin/bash` | Returns `"bash"` |
| SD-3 | `_detect_shell` | `SHELL=/usr/bin/fish` | Returns `"fish"` |
| SD-4 | `_detect_shell` | `SHELL` unset | Falls back to `"bash"` |
| SD-5 | `_detect_shell` | `sys.platform == "win32"` | Returns `"powershell"` regardless of `SHELL` |
| SD-6 | `_detect_shell` | `SHELL=/usr/local/bin/zsh` (non-standard prefix) | Returns `"zsh"` |
| SD-7 | `_detect_shell` | `SHELL=/usr/bin/tcsh` (unsupported shell) | Falls back to `"bash"` |

## Completion Installation

### `tests/unit/test_dev_install.py`

| ID | Component | Description | Expected Result |
|----|-----------|-------------|-----------------|
| CI-1 | `_install_completion` | bash → writes to `~/.local/share/bash-completion/completions/rdc` | File exists at correct path with expected content |
| CI-2 | `_install_completion` | zsh → writes to `~/.zfunc/_rdc` | File exists at correct path with expected content |
| CI-3 | `_install_completion` | fish → writes to `~/.config/fish/completions/rdc.fish` | File exists at correct path with expected content |
| CI-4 | `_install_completion` | parent directory does not exist → created automatically | Parent dirs created; file written successfully |
| CI-5 | `_install_completion` | powershell → no file written, prints instructions | No file created; stdout contains instruction text |
| CI-6 | `_install_completion` | existing completion file is overwritten | File updated with new content |
| CI-7 | `_install_completion` | zsh completion prints fpath hint | stdout contains fpath snippet |

## UV Tool Install

### `tests/unit/test_dev_install.py`

| ID | Component | Description | Expected Result |
|----|-----------|-------------|-----------------|
| UV-1 | `_install_binary` | calls subprocess with `["uv", "tool", "install", "-e", ".", "--force"]` | `subprocess.run` invoked with exact args and `check=True` |
| UV-2 | `_install_binary` | `CalledProcessError` → propagates | Exception raised; subsequent steps not executed |

## Error Handling

### `tests/unit/test_dev_install.py`

| ID | Component | Description | Expected Result |
|----|-----------|-------------|-----------------|
| EH-1 | `_install_completion` | `_generate()` raises → non-fatal | Warning printed; script continues; no file written |
| EH-2 | `_install_completion` | file write `PermissionError` → non-fatal | Warning printed; script continues |

## End-to-End Flow

### `tests/unit/test_dev_install.py`

| ID | Component | Description | Expected Result |
|----|-----------|-------------|-----------------|
| E2E-1 | `main` | full flow with mocked subprocess and `_generate` | Binary install runs first, then shell detected, completion written, summary printed |
| E2E-2 | `main` | binary install fails → completion install skipped | Only error from uv install shown; no completion attempt |
