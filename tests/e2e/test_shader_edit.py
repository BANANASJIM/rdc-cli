"""E2E tests for shader editing commands (build, replace, restore).

Black-box tests that invoke the real CLI via subprocess against a vkcube.rdc
capture session. Requires a working renderdoc installation.

NOTE: shader-build only supports GLSL encoding safely. SPIRV text asm causes
segfaults in RenderDoc.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import rdc, rdc_ok

pytestmark = pytest.mark.gpu

TIMEOUT = 60

MINIMAL_FRAG = """\
#version 450
layout(location = 0) out vec4 outColor;
void main() {
    outColor = vec4(1.0, 0.0, 0.0, 1.0);
}
"""

INVALID_FRAG = """\
#version 450
void main() {
    this is not valid glsl;
}
"""


class TestShaderBuild:
    """11.2: rdc shader-build compiles GLSL source."""

    def test_shader_build_glsl(self, vkcube_session: str, tmp_path: Path) -> None:
        """shader-build compiles valid GLSL and returns shader_id."""
        src = tmp_path / "test.frag"
        src.write_text(MINIMAL_FRAG)
        out = rdc_ok(
            "shader-build",
            str(src),
            "--stage",
            "ps",
            session=vkcube_session,
            timeout=TIMEOUT,
        )
        assert "shader_id" in out

    def test_shader_build_quiet(self, vkcube_session: str, tmp_path: Path) -> None:
        """shader-build -q outputs only the shader ID number."""
        src = tmp_path / "test.frag"
        src.write_text(MINIMAL_FRAG)
        out = rdc_ok(
            "shader-build",
            str(src),
            "--stage",
            "ps",
            "-q",
            session=vkcube_session,
            timeout=TIMEOUT,
        )
        assert out.strip().isdigit()

    def test_shader_build_json(self, vkcube_session: str, tmp_path: Path) -> None:
        """shader-build --json returns JSON with shader_id key."""
        src = tmp_path / "test.frag"
        src.write_text(MINIMAL_FRAG)
        r = rdc(
            "shader-build",
            str(src),
            "--stage",
            "ps",
            "--json",
            session=vkcube_session,
            timeout=TIMEOUT,
        )
        assert r.returncode == 0, f"shader-build --json failed:\n{r.stderr}"
        data = json.loads(r.stdout)
        assert "shader_id" in data

    def test_shader_build_bad_source(self, vkcube_session: str, tmp_path: Path) -> None:
        """shader-build with invalid GLSL exits non-zero."""
        src = tmp_path / "bad.frag"
        src.write_text(INVALID_FRAG)
        r = rdc(
            "shader-build",
            str(src),
            "--stage",
            "ps",
            session=vkcube_session,
            timeout=TIMEOUT,
        )
        assert r.returncode != 0


class TestShaderReplaceRestore:
    """11.3: rdc shader-replace / shader-restore / shader-restore-all."""

    def test_shader_replace_and_restore(self, vkcube_session: str, tmp_path: Path) -> None:
        """shader-replace swaps shader, shader-restore reverts it."""
        src = tmp_path / "replace.frag"
        src.write_text(MINIMAL_FRAG)

        # Build a replacement shader
        build = rdc(
            "shader-build",
            str(src),
            "--stage",
            "ps",
            "-q",
            session=vkcube_session,
            timeout=TIMEOUT,
        )
        assert build.returncode == 0, f"shader-build failed:\n{build.stderr}"
        shader_id = build.stdout.strip()

        try:
            # Replace shader at EID 11, pixel shader stage
            replace = rdc(
                "shader-replace",
                "11",
                "ps",
                "--with",
                shader_id,
                session=vkcube_session,
                timeout=TIMEOUT,
            )
            assert replace.returncode == 0, f"shader-replace failed:\n{replace.stderr}"
            assert "replaced" in replace.stdout

            # Restore original
            restore = rdc(
                "shader-restore",
                "11",
                "ps",
                session=vkcube_session,
                timeout=TIMEOUT,
            )
            assert restore.returncode == 0, f"shader-restore failed:\n{restore.stderr}"
            assert "restored" in restore.stdout
        finally:
            cleanup = rdc("shader-restore-all", session=vkcube_session, timeout=TIMEOUT)
            assert cleanup.returncode == 0, (
                f"shader-restore-all cleanup failed:\n{cleanup.stdout}\n{cleanup.stderr}"
            )

    def test_shader_restore_all(self, vkcube_session: str) -> None:
        """shader-restore-all clears all shader replacements."""
        r = rdc("shader-restore-all", session=vkcube_session, timeout=TIMEOUT)
        assert r.returncode == 0, f"shader-restore-all failed:\n{r.stderr}"
        assert "restored" in r.stdout
        assert "freed" in r.stdout
