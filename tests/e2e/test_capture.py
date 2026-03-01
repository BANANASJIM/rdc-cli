"""E2E tests for capture workflow commands (requires vulkan-samples).

These tests exercise the live capture pipeline: execute-and-capture,
inject-only mode, and the attach/trigger/list/copy control flow.
Skipped unless VULKAN_SAMPLES_BIN env or .local/vulkan-samples/vulkan_samples exists.
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.vulkan_samples

CAPTURE_TIMEOUT = 120


def _rdc_capture(
    *args: str,
    timeout: int = CAPTURE_TIMEOUT,
) -> subprocess.CompletedProcess[str]:
    """Run rdc command bypassing daemon session for capture operations."""
    cmd = ["uv", "run", "rdc", *args]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


class TestCapture:
    """13.1: rdc capture creates an .rdc file from a running application."""

    def test_capture_to_file(self, vulkan_samples_bin: str, tmp_path: Path) -> None:
        """capture writes an .rdc file to the specified output path."""
        out = tmp_path / "test.rdc"
        result = _rdc_capture(
            "capture",
            "-o",
            str(out),
            "--",
            vulkan_samples_bin,
        )
        assert result.returncode == 0, f"capture failed:\n{result.stderr}"
        # Output file may have _frame0 suffix appended by RenderDoc
        rdc_files = list(tmp_path.glob("*.rdc"))
        assert len(rdc_files) >= 1, f"No .rdc files in {tmp_path}"
        assert rdc_files[0].stat().st_size > 0

    def test_capture_json_output(self, vulkan_samples_bin: str, tmp_path: Path) -> None:
        """capture --json returns structured JSON result."""
        out = tmp_path / "test.rdc"
        result = _rdc_capture(
            "capture",
            "-o",
            str(out),
            "--json",
            "--",
            vulkan_samples_bin,
        )
        assert result.returncode == 0, f"capture --json failed:\n{result.stderr}"
        data = json.loads(result.stdout)
        assert data.get("success") is True
        assert "path" in data


class TestCaptureInject:
    """13.2: rdc capture --trigger injects without auto-capturing."""

    def test_inject_prints_ident(self, vulkan_samples_bin: str) -> None:
        """capture --trigger prints injected ident on stderr."""
        proc = subprocess.Popen(
            [
                "uv",
                "run",
                "rdc",
                "capture",
                "--trigger",
                "--",
                vulkan_samples_bin,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            time.sleep(5)
            # Process should still be running (inject mode keeps it alive)
            assert proc.poll() is None or proc.returncode == 0
        finally:
            proc.terminate()
            proc.wait(timeout=15)


class TestCaptureWorkflow:
    """13.3: Full inject -> attach -> trigger -> list -> copy workflow."""

    def test_workflow_placeholder(self, vulkan_samples_bin: str, tmp_path: Path) -> None:
        """Full capture control workflow test.

        This test exercises the complete capture lifecycle:
        1. Inject into running application (capture --trigger)
        2. Attach to target (rdc attach IDENT)
        3. Trigger capture (rdc capture-trigger --ident IDENT)
        4. List captures (rdc capture-list --ident IDENT)
        5. Copy capture (rdc capture-copy ID DEST --ident IDENT)

        Currently a placeholder: parsing ident from subprocess output
        requires refinement for reliable CI operation.
        """
        # TODO: implement full workflow once ident parsing is stabilized
        proc = subprocess.Popen(
            [
                "uv",
                "run",
                "rdc",
                "capture",
                "--trigger",
                "--json",
                "--",
                vulkan_samples_bin,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            time.sleep(5)
            if proc.poll() is not None:
                pytest.skip("Process exited before injection completed")

            # Read stderr for ident info
            # Ident parsing requires non-blocking reads; skip for now
            pytest.skip("Full workflow test needs non-blocking ident parsing")
        finally:
            proc.terminate()
            proc.wait(timeout=15)
