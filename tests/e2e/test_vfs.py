"""E2E tests for VFS navigation commands (ls, cat, tree).

Black-box tests that invoke the real CLI via subprocess against a vkcube.rdc
capture session. Requires a working renderdoc installation.

Capture: vkcube.rdc — 1 draw at EID 11, texture 97, shader 111/112,
pass "Colour Pass #1 (1 Target + Depth)".
"""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import rdc_fail, rdc_ok

pytestmark = pytest.mark.gpu

PNG_MAGIC = b"\x89PNG"


class TestLsRoot:
    """5.1: rdc ls / lists root VFS entries."""

    def test_root_entries(self, vkcube_session: str) -> None:
        """Root listing contains expected top-level entries."""
        out = rdc_ok("ls", "/", session=vkcube_session)
        for name in ("info", "stats", "events", "draws", "resources", "textures", "shaders"):
            assert name in out


class TestLsLong:
    """5.2: rdc ls -l / shows long format with NAME/TYPE columns."""

    def test_long_format_columns(self, vkcube_session: str) -> None:
        """Long format contains NAME and TYPE columns with kind indicators."""
        out = rdc_ok("ls", "-l", "/", session=vkcube_session)
        assert "NAME" in out
        assert "TYPE" in out
        for kind in ("leaf", "dir"):
            assert kind in out


class TestTreeRoot:
    """5.3: rdc tree / --depth 1 shows tree formatting."""

    def test_tree_formatting(self, vkcube_session: str) -> None:
        """Tree output uses box-drawing characters."""
        out = rdc_ok("tree", "/", "--depth", "1", session=vkcube_session)
        assert "\u251c\u2500\u2500" in out  # "├──"


class TestTreeDraws:
    """5.4: rdc tree /draws --depth 2 shows draw subtree."""

    def test_draws_subtree(self, vkcube_session: str) -> None:
        """Draw subtree contains pipeline/, shader/, targets/ entries."""
        out = rdc_ok("tree", "/draws", "--depth", "2", session=vkcube_session)
        for name in ("pipeline", "shader", "targets"):
            assert name in out


class TestCatInfo:
    """5.5: rdc cat /info shows capture metadata."""

    def test_capture_info(self, vkcube_session: str) -> None:
        """Capture info mentions Vulkan and Events."""
        out = rdc_ok("cat", "/info", session=vkcube_session)
        assert "Vulkan" in out or "vulkan" in out.lower()
        assert "Events" in out or "events" in out.lower()


class TestCatStats:
    """5.6: rdc cat /stats shows per-pass data."""

    def test_stats_output(self, vkcube_session: str) -> None:
        """Stats output contains per_pass data."""
        out = rdc_ok("cat", "/stats", session=vkcube_session)
        assert "per_pass" in out or "pass" in out.lower()


class TestCatLog:
    """5.7: rdc cat /log shows log messages."""

    def test_log_columns(self, vkcube_session: str) -> None:
        """Log output has LEVEL, EID, MESSAGE header."""
        out = rdc_ok("cat", "/log", session=vkcube_session)
        assert "LEVEL" in out
        assert "EID" in out
        assert "MESSAGE" in out


class TestCatCapabilities:
    """5.8: rdc cat /capabilities shows capture capabilities."""

    def test_capabilities(self, vkcube_session: str) -> None:
        """Capabilities output contains capture info."""
        out = rdc_ok("cat", "/capabilities", session=vkcube_session)
        assert len(out.strip()) > 0


class TestCatEvent:
    """5.9: rdc cat /events/11 shows event detail."""

    def test_event_detail(self, vkcube_session: str) -> None:
        """Event 11 detail contains vkCmdDraw."""
        out = rdc_ok("cat", "/events/11", session=vkcube_session)
        assert "vkCmdDraw" in out or "Draw" in out


class TestCatPipelineTopology:
    """5.10: rdc cat /draws/11/pipeline/topology shows TriangleList."""

    def test_topology(self, vkcube_session: str) -> None:
        """Pipeline topology is TriangleList."""
        out = rdc_ok("cat", "/draws/11/pipeline/topology", session=vkcube_session)
        assert "TriangleList" in out


class TestCatShaderDisasm:
    """5.11: rdc cat /draws/11/shader/vs/disasm shows SPIR-V disassembly."""

    def test_spirv_disasm(self, vkcube_session: str) -> None:
        """Vertex shader disassembly contains SPIR-V markers."""
        out = rdc_ok("cat", "/draws/11/shader/vs/disasm", session=vkcube_session)
        assert "SPIR-V" in out or "OpCapability" in out or "spir" in out.lower()


class TestCatPostVS:
    """5.12: rdc cat /draws/11/postvs shows post-VS data."""

    def test_postvs_data(self, vkcube_session: str) -> None:
        """Post-VS data contains vertexResourceId."""
        out = rdc_ok("cat", "/draws/11/postvs", session=vkcube_session)
        assert "vertexResourceId" in out or "vertex" in out.lower()


class TestCatDescriptors:
    """5.13: rdc cat /draws/11/descriptors shows descriptor columns."""

    def test_descriptor_columns(self, vkcube_session: str) -> None:
        """Descriptors output has STAGE and TYPE columns."""
        out = rdc_ok("cat", "/draws/11/descriptors", session=vkcube_session)
        assert "STAGE" in out
        assert "TYPE" in out


class TestCatResourceInfo:
    """5.15: rdc cat /resources/97/info shows resource detail."""

    def test_resource_info(self, vkcube_session: str) -> None:
        """Resource 97 info contains id field."""
        out = rdc_ok("cat", "/resources/97/info", session=vkcube_session)
        assert "97" in out


class TestCatTextureInfo:
    """5.16: rdc cat /textures/97/info shows texture metadata."""

    def test_texture_metadata(self, vkcube_session: str) -> None:
        """Texture 97 info contains width, height, format."""
        out = rdc_ok("cat", "/textures/97/info", session=vkcube_session)
        assert "width" in out.lower()
        assert "height" in out.lower()
        assert "format" in out.lower()


class TestCatShaderInfo:
    """5.17: rdc cat /shaders/111/info shows shader info."""

    def test_shader_info(self, vkcube_session: str) -> None:
        """Shader 111 info contains stage and entry information."""
        out = rdc_ok("cat", "/shaders/111/info", session=vkcube_session)
        assert "111" in out


class TestLsTextures:
    """5.18: rdc ls /textures lists texture IDs."""

    def test_texture_ids(self, vkcube_session: str) -> None:
        """Texture listing includes expected IDs."""
        out = rdc_ok("ls", "/textures", session=vkcube_session)
        for tid in ("97", "255", "256", "257", "276"):
            assert tid in out


class TestLsShaders:
    """5.19: rdc ls /shaders lists shader IDs."""

    def test_shader_ids(self, vkcube_session: str) -> None:
        """Shader listing includes expected IDs."""
        out = rdc_ok("ls", "/shaders", session=vkcube_session)
        for sid in ("111", "112"):
            assert sid in out


class TestLsPasses:
    """5.20: rdc ls /passes lists pass names."""

    def test_pass_names(self, vkcube_session: str) -> None:
        """Pass listing is non-empty."""
        out = rdc_ok("ls", "/passes", session=vkcube_session)
        assert len(out.strip()) > 0


class TestCatNotFound:
    """5.22: rdc cat /nonexistent returns error exit 1."""

    def test_not_found_error(self, vkcube_session: str) -> None:
        """Accessing a non-existent path produces an error."""
        out = rdc_fail("cat", "/nonexistent", session=vkcube_session, exit_code=1)
        assert "error" in out.lower()


class TestLsNotFound:
    """5.23: rdc ls /nonexistent returns error exit 1."""

    def test_not_found_error(self, vkcube_session: str) -> None:
        """Listing a non-existent path produces an error."""
        out = rdc_fail("ls", "/nonexistent", session=vkcube_session, exit_code=1)
        assert "error" in out.lower()


class TestCatTexturePng:
    """5.25: rdc cat /textures/97/image.png -o {tmp} creates a PNG file."""

    def test_texture_png_export(self, vkcube_session: str, tmp_out: Path) -> None:
        """Exported texture is a valid PNG file."""
        dest = tmp_out / "tex.png"
        rdc_ok("cat", "/textures/97/image.png", "-o", str(dest), session=vkcube_session)
        assert dest.exists()
        assert dest.stat().st_size > 0
        assert dest.read_bytes()[:4] == PNG_MAGIC


class TestCatRenderTargetPng:
    """5.26: rdc cat /draws/11/targets/color0.png -o {tmp} creates a PNG file."""

    def test_rt_png_export(self, vkcube_session: str, tmp_out: Path) -> None:
        """Exported render target is a valid PNG file."""
        dest = tmp_out / "rt.png"
        rdc_ok("cat", "/draws/11/targets/color0.png", "-o", str(dest), session=vkcube_session)
        assert dest.exists()
        assert dest.stat().st_size > 0
        assert dest.read_bytes()[:4] == PNG_MAGIC


class TestTreeBadFlag:
    """5.27: rdc tree / --max-depth 1 exits with usage error."""

    def test_bad_flag_exit_code(self, vkcube_session: str) -> None:
        """Using --max-depth instead of --depth produces exit code 2."""
        out = rdc_fail(
            "tree",
            "/",
            "--max-depth",
            "1",
            session=vkcube_session,
            exit_code=2,
        )
        assert "depth" in out.lower()
