#!/usr/bin/env python3
"""Cross-platform Android Platform Tools download script.

Downloads Android Platform Tools (contains adb) from Google into
.local/android-platform-tools/platform-tools/.

Idempotent: exits early if adb already exists.
"""

from __future__ import annotations

import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

_IS_WINDOWS = sys.platform == "win32"
_IS_MACOS = sys.platform == "darwin"

_ADB_NAME = "adb.exe" if _IS_WINDOWS else "adb"
TARGET = Path(".local/android-platform-tools")
_ADB_PATH = TARGET / "platform-tools" / _ADB_NAME

_DOWNLOAD_URLS = {
    "linux": "https://dl.google.com/android/repository/platform-tools-latest-linux.zip",
    "darwin": "https://dl.google.com/android/repository/platform-tools-latest-darwin.zip",
    "win32": "https://dl.google.com/android/repository/platform-tools-latest-windows.zip",
}


def _log(msg: str) -> None:
    sys.stdout.write(msg + "\n")
    sys.stdout.flush()


def _get_url() -> str:
    key = sys.platform if sys.platform in _DOWNLOAD_URLS else "linux"
    return _DOWNLOAD_URLS[key]


def main() -> None:
    """Download and extract Android Platform Tools; skip if adb already present.

    Extracts to .local/android-platform-tools/ so that
    .local/android-platform-tools/platform-tools/adb is available.
    All paths are resolved relative to the current working directory, which
    should be the repository root.
    """
    if _ADB_PATH.exists():
        _log(f"adb already present at {_ADB_PATH}")
        return

    url = _get_url()
    _log(f"Downloading Android Platform Tools from {url} ...")
    TARGET.mkdir(parents=True, exist_ok=True)

    tmp_zip: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
            tmp_zip = Path(f.name)
        urllib.request.urlretrieve(url, tmp_zip)
        _log("Extracting...")
        dest_resolved = TARGET.resolve()
        with zipfile.ZipFile(tmp_zip) as zf:
            for member in zf.infolist():
                target = (TARGET / member.filename).resolve()
                if not target.is_relative_to(dest_resolved):
                    sys.stderr.write(f"ERROR: zip-slip: {member.filename}\n")
                    raise SystemExit(1)
                zf.extract(member, TARGET)
    finally:
        if tmp_zip and tmp_zip.exists():
            tmp_zip.unlink()

    if not _ADB_PATH.exists():
        sys.stderr.write(f"ERROR: adb not found at {_ADB_PATH} after extraction\n")
        raise SystemExit(1)

    if not _IS_WINDOWS:
        _ADB_PATH.chmod(_ADB_PATH.stat().st_mode | 0o111)

    _log(f"Done: {_ADB_PATH}")


if __name__ == "__main__":
    main()
