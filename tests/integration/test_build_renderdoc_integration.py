"""Integration tests for scripts/build_renderdoc.py (manual only)."""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="requires cmake+git+network; run manually")
def test_full_build_linux(tmp_path):
    """Full build from scratch into tmp_path.

    Manual verification:
        python scripts/build_renderdoc.py /tmp/rdoc-test --build-dir /tmp/rdoc-build
    """
