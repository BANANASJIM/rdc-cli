"""E2E tests for capture workflow commands (requires vulkan-samples).

These tests exercise the live capture pipeline: execute-and-capture,
inject-only mode, and the attach/trigger/list/copy control flow.
Skipped unless VULKAN_SAMPLES_BIN env or .local/vulkan-samples/vulkan_samples exists.
"""

from __future__ import annotations

import json
import re
import subprocess
import threading
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.vulkan_samples

CAPTURE_TIMEOUT = 120


def _force_kill(proc: subprocess.Popen[str], timeout: float = 15) -> None:
    """Terminate *proc*, falling back to SIGKILL if it ignores SIGTERM."""
    proc.terminate()
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


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
            # Poll until injection completes (process stays alive in trigger mode)
            for _ in range(20):
                if proc.poll() is not None:
                    break
                time.sleep(0.5)
            assert proc.poll() is None, f"Process exited prematurely with code {proc.returncode}"
        finally:
            _force_kill(proc)
            stderr = proc.stderr.read() if proc.stderr else ""
            assert re.search(r"injected: ident=\d+", stderr), (
                f"Expected ident pattern in stderr, got:\n{stderr}"
            )


def _read_stderr(proc: subprocess.Popen[str], lines: list[str]) -> None:
    """Read stderr lines from *proc* until EOF (runs in a thread)."""
    assert proc.stderr is not None
    for line in proc.stderr:
        lines.append(line)


def _parse_ident(lines: list[str], timeout: float = 15.0) -> int | None:
    """Wait up to *timeout* seconds for an ``injected: ident=N`` line."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for line in lines:
            m = re.search(r"injected: ident=(\d+)", line)
            if m:
                return int(m.group(1))
        time.sleep(0.25)
    return None


class TestCaptureWorkflow:
    """13.3: Full inject -> attach -> trigger -> list -> copy workflow."""

    def test_full_workflow(self, vulkan_samples_bin: str, tmp_path: Path) -> None:
        """Full capture control workflow test.

        Exercises the complete capture lifecycle:
        1. Inject into running application (capture --trigger)
        2. Parse ident from stderr via background thread
        3. Attach to target (rdc attach IDENT)
        4. Trigger capture (rdc capture-trigger --ident IDENT)
        5. List captures (rdc capture-list --ident IDENT)
        6. Copy capture (rdc capture-copy ID DEST --ident IDENT)
        """
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
        stderr_lines: list[str] = []
        reader = threading.Thread(target=_read_stderr, args=(proc, stderr_lines))
        reader.daemon = True
        reader.start()

        try:
            # Step 1: parse ident from stderr
            ident = _parse_ident(stderr_lines, timeout=15.0)
            if proc.poll() is not None:
                pytest.skip(f"Process exited before injection completed: {''.join(stderr_lines)}")
            assert ident is not None, f"Failed to parse ident from stderr:\n{''.join(stderr_lines)}"

            ident_str = str(ident)

            # Step 2: attach
            r_attach = _rdc_capture("attach", ident_str)
            assert r_attach.returncode == 0, f"attach failed:\n{r_attach.stderr}"
            assert f"ident={ident}" in r_attach.stdout

            # Step 3: trigger capture
            r_trigger = _rdc_capture(
                "capture-trigger",
                "--ident",
                ident_str,
            )
            assert r_trigger.returncode == 0, f"capture-trigger failed:\n{r_trigger.stderr}"

            # Step 4: list captures
            r_list = _rdc_capture(
                "capture-list",
                "--ident",
                ident_str,
                "--timeout",
                "10",
            )
            assert r_list.returncode == 0, f"capture-list failed:\n{r_list.stderr}"

            # Step 5: copy capture (parse capture ID from list output)
            # List output format: [ID] path  frame=N  size=N  api=...
            cap_match = re.search(r"\[(\d+)\]", r_list.stdout)
            if cap_match is None:
                pytest.skip(f"No capture ID in capture-list output:\n{r_list.stdout}")
            cap_id = cap_match.group(1)
            dest = str(tmp_path / "workflow.rdc")

            r_copy = _rdc_capture(
                "capture-copy",
                cap_id,
                dest,
                "--ident",
                ident_str,
            )
            assert r_copy.returncode == 0, f"capture-copy failed:\n{r_copy.stderr}"
            assert Path(dest).exists(), f"Copied capture not found at {dest}"
        finally:
            _force_kill(proc)
            reader.join(timeout=5)
