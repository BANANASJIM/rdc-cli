from __future__ import annotations

import pytest

from rdc.vfs.router import PathMatch, resolve_path

# ── Root leaves ──────────────────────────────────────────────────────


def test_root() -> None:
    m = resolve_path("/")
    assert m == PathMatch(kind="dir", handler=None, args={})


def test_info() -> None:
    m = resolve_path("/info")
    assert m == PathMatch(kind="leaf", handler="info", args={})


def test_stats() -> None:
    m = resolve_path("/stats")
    assert m == PathMatch(kind="leaf", handler="stats", args={})


def test_capabilities() -> None:
    m = resolve_path("/capabilities")
    assert m == PathMatch(kind="leaf", handler="info", args={})


def test_log() -> None:
    m = resolve_path("/log")
    assert m == PathMatch(kind="leaf", handler="log", args={})


# ── Events ───────────────────────────────────────────────────────────


def test_events_dir() -> None:
    m = resolve_path("/events")
    assert m == PathMatch(kind="dir", handler=None, args={})


def test_events_eid() -> None:
    m = resolve_path("/events/42")
    assert m == PathMatch(kind="leaf", handler="event", args={"eid": 42})


def test_events_eid_is_int() -> None:
    m = resolve_path("/events/999")
    assert m is not None
    assert isinstance(m.args["eid"], int)


# ── Draws ────────────────────────────────────────────────────────────


def test_draws_dir() -> None:
    m = resolve_path("/draws")
    assert m == PathMatch(kind="dir", handler=None, args={})


def test_draws_eid() -> None:
    m = resolve_path("/draws/142")
    assert m == PathMatch(kind="dir", handler=None, args={"eid": 142})


# ── Pipeline ─────────────────────────────────────────────────────────


def test_draws_pipeline_dir() -> None:
    m = resolve_path("/draws/142/pipeline")
    assert m == PathMatch(kind="dir", handler=None, args={"eid": 142})


def test_draws_pipeline_summary() -> None:
    m = resolve_path("/draws/142/pipeline/summary")
    assert m == PathMatch(kind="leaf", handler="pipeline", args={"eid": 142, "section": None})


def test_draws_pipeline_invalid_section() -> None:
    assert resolve_path("/draws/142/pipeline/bad") is None


def test_draws_pipeline_ia_not_routed() -> None:
    """ia/rs/om are not yet in route table."""
    assert resolve_path("/draws/142/pipeline/ia") is None


# ── Shader ───────────────────────────────────────────────────────────


def test_draws_shader_dir() -> None:
    m = resolve_path("/draws/142/shader")
    assert m == PathMatch(kind="dir", handler=None, args={"eid": 142})


@pytest.mark.parametrize("stage", ["vs", "hs", "ds", "gs", "ps", "cs"])
def test_draws_shader_stage_dir(stage: str) -> None:
    m = resolve_path(f"/draws/142/shader/{stage}")
    assert m == PathMatch(kind="dir", handler=None, args={"eid": 142, "stage": stage})


def test_draws_shader_invalid_stage() -> None:
    assert resolve_path("/draws/142/shader/xx") is None


@pytest.mark.parametrize(
    "leaf,handler",
    [
        ("disasm", "shader_disasm"),
        ("source", "shader_source"),
        ("reflect", "shader_reflect"),
        ("constants", "shader_constants"),
    ],
)
def test_draws_shader_leaf(leaf: str, handler: str) -> None:
    m = resolve_path(f"/draws/142/shader/ps/{leaf}")
    assert m == PathMatch(kind="leaf", handler=handler, args={"eid": 142, "stage": "ps"})


def test_draws_shader_binary_not_routed() -> None:
    """binary is Phase 2+ — not yet in route table."""
    assert resolve_path("/draws/142/shader/ps/binary") is None


# ── Bindings ─────────────────────────────────────────────────────────


def test_draws_bindings_dir() -> None:
    m = resolve_path("/draws/142/bindings")
    assert m == PathMatch(kind="dir", handler=None, args={"eid": 142})


# ── Passes ───────────────────────────────────────────────────────────


def test_passes_dir() -> None:
    m = resolve_path("/passes")
    assert m == PathMatch(kind="dir", handler=None, args={})


def test_passes_name_dir() -> None:
    m = resolve_path("/passes/GBuffer")
    assert m == PathMatch(kind="dir", handler=None, args={"name": "GBuffer"})


def test_passes_name_info() -> None:
    m = resolve_path("/passes/GBuffer/info")
    assert m == PathMatch(kind="leaf", handler="pass", args={"name": "GBuffer"})


def test_passes_name_draws() -> None:
    m = resolve_path("/passes/Shadow/draws")
    assert m == PathMatch(kind="dir", handler=None, args={"name": "Shadow"})


def test_passes_name_attachments() -> None:
    m = resolve_path("/passes/Shadow/attachments")
    assert m == PathMatch(kind="dir", handler=None, args={"name": "Shadow"})


# ── Resources ────────────────────────────────────────────────────────


def test_resources_dir() -> None:
    m = resolve_path("/resources")
    assert m == PathMatch(kind="dir", handler=None, args={})


def test_resources_id_dir() -> None:
    m = resolve_path("/resources/88")
    assert m == PathMatch(kind="dir", handler=None, args={"id": 88})


def test_resources_id_info() -> None:
    m = resolve_path("/resources/88/info")
    assert m == PathMatch(kind="leaf", handler="resource", args={"id": 88})


def test_resources_id_is_int() -> None:
    m = resolve_path("/resources/88/info")
    assert m is not None
    assert isinstance(m.args["id"], int)


# ── Top-level dirs / aliases ─────────────────────────────────────────


def test_shaders_dir() -> None:
    assert resolve_path("/shaders") == PathMatch(kind="dir", handler=None, args={})


def test_by_marker_dir() -> None:
    assert resolve_path("/by-marker") == PathMatch(kind="dir", handler=None, args={})


def test_textures_dir() -> None:
    assert resolve_path("/textures") == PathMatch(kind="dir", handler=None, args={})


def test_buffers_dir() -> None:
    assert resolve_path("/buffers") == PathMatch(kind="dir", handler=None, args={})


def test_current_alias() -> None:
    assert resolve_path("/current") == PathMatch(kind="alias", handler=None, args={})


# ── Edge cases ───────────────────────────────────────────────────────


def test_nonexistent_returns_none() -> None:
    assert resolve_path("/nonexistent") is None


def test_non_numeric_eid_returns_none() -> None:
    assert resolve_path("/draws/abc") is None


def test_non_numeric_resource_id_returns_none() -> None:
    assert resolve_path("/resources/abc") is None


def test_unknown_shader_leaf_returns_none() -> None:
    assert resolve_path("/draws/142/shader/ps/nonexistent") is None


def test_empty_string_resolves_as_root() -> None:
    assert resolve_path("") == PathMatch(kind="dir", handler=None, args={})


def test_trailing_slash_stripped() -> None:
    assert resolve_path("/draws/142/") == resolve_path("/draws/142")


class TestBufferDecodeRoutes:
    def test_cbuffer_dir(self) -> None:
        m = resolve_path("/draws/42/cbuffer")
        assert m is not None
        assert m.kind == "dir"
        assert m.args["eid"] == 42

    def test_cbuffer_decode(self) -> None:
        m = resolve_path("/draws/42/cbuffer/0/3")
        assert m is not None
        assert m.kind == "leaf"
        assert m.handler == "cbuffer_decode"
        assert m.args == {"eid": 42, "set": 0, "binding": 3}

    def test_vbuffer_decode(self) -> None:
        m = resolve_path("/draws/42/vbuffer")
        assert m is not None
        assert m.kind == "leaf"
        assert m.handler == "vbuffer_decode"
        assert m.args["eid"] == 42

    def test_ibuffer_decode(self) -> None:
        m = resolve_path("/draws/42/ibuffer")
        assert m is not None
        assert m.kind == "leaf"
        assert m.handler == "ibuffer_decode"
        assert m.args["eid"] == 42


def test_trailing_slash_on_leaf() -> None:
    assert resolve_path("/info/") == resolve_path("/info")


def test_path_traversal_returns_none() -> None:
    assert resolve_path("/../etc/passwd") is None


def test_double_dot_mid_path_returns_none() -> None:
    assert resolve_path("/draws/../events") is None


def test_pipeline_summary_section_is_none() -> None:
    m = resolve_path("/draws/142/pipeline/summary")
    assert m is not None
    assert m.args["section"] is None


def test_all_shader_stages_on_all_leaves() -> None:
    """Every stage x leaf combination must resolve."""
    stages = ["vs", "hs", "ds", "gs", "ps", "cs"]
    leaves = ["disasm", "source", "reflect", "constants"]
    for stage in stages:
        for leaf in leaves:
            m = resolve_path(f"/draws/1/shader/{stage}/{leaf}")
            assert m is not None, f"/draws/1/shader/{stage}/{leaf} should resolve"
            assert stage == m.args["stage"]


def test_pass_name_with_special_chars() -> None:
    m = resolve_path("/passes/Main-Pass_01/info")
    assert m is not None
    assert m.args["name"] == "Main-Pass_01"


# ── Textures (Phase 2) ─────────────────────────────────────────────


def test_textures_id_dir() -> None:
    m = resolve_path("/textures/42")
    assert m == PathMatch(kind="dir", handler=None, args={"id": 42})


def test_textures_id_info() -> None:
    m = resolve_path("/textures/42/info")
    assert m == PathMatch(kind="leaf", handler="tex_info", args={"id": 42})


def test_textures_id_image_png() -> None:
    m = resolve_path("/textures/42/image.png")
    assert m == PathMatch(kind="leaf_bin", handler="tex_export", args={"id": 42})


def test_textures_id_mips_dir() -> None:
    m = resolve_path("/textures/42/mips")
    assert m == PathMatch(kind="dir", handler=None, args={"id": 42})


@pytest.mark.parametrize("mip", [0, 3])
def test_textures_id_mips_png(mip: int) -> None:
    m = resolve_path(f"/textures/42/mips/{mip}.png")
    assert m == PathMatch(kind="leaf_bin", handler="tex_export", args={"id": 42, "mip": mip})


def test_textures_id_data() -> None:
    m = resolve_path("/textures/42/data")
    assert m == PathMatch(kind="leaf_bin", handler="tex_raw", args={"id": 42})


# ── Buffers (Phase 2) ──────────────────────────────────────────────


def test_buffers_id_dir() -> None:
    m = resolve_path("/buffers/7")
    assert m == PathMatch(kind="dir", handler=None, args={"id": 7})


def test_buffers_id_info() -> None:
    m = resolve_path("/buffers/7/info")
    assert m == PathMatch(kind="leaf", handler="buf_info", args={"id": 7})


def test_buffers_id_data() -> None:
    m = resolve_path("/buffers/7/data")
    assert m == PathMatch(kind="leaf_bin", handler="buf_raw", args={"id": 7})


# ── Draw targets (Phase 2) ─────────────────────────────────────────


def test_draws_targets_dir() -> None:
    m = resolve_path("/draws/142/targets")
    assert m == PathMatch(kind="dir", handler=None, args={"eid": 142})


@pytest.mark.parametrize("target", [0, 3])
def test_draws_targets_color_png(target: int) -> None:
    m = resolve_path(f"/draws/142/targets/color{target}.png")
    assert m == PathMatch(kind="leaf_bin", handler="rt_export", args={"eid": 142, "target": target})


def test_draws_targets_depth_png() -> None:
    m = resolve_path("/draws/142/targets/depth.png")
    assert m == PathMatch(kind="leaf_bin", handler="rt_depth", args={"eid": 142})


# ── Phase 2 edge / error cases ─────────────────────────────────────


@pytest.mark.parametrize(
    "path",
    [
        "/textures/abc",
        "/textures/42/nonexistent",
        "/buffers/abc",
        "/draws/142/targets/colorX.png",
        "/textures/42/mips/abc.png",
        "/textures/42/mips/0",
        "/draws/142/targets/color0",
        "/draws/142/targets/depth",
    ],
)
def test_phase2_invalid_paths_return_none(path: str) -> None:
    assert resolve_path(path) is None


# ── Pipeline state routes (Phase 2) ────────────────────────────────


class TestPipelineStateRoutes:
    @pytest.mark.parametrize(
        "sub,handler",
        [
            ("topology", "pipe_topology"),
            ("viewport", "pipe_viewport"),
            ("scissor", "pipe_scissor"),
            ("blend", "pipe_blend"),
            ("stencil", "pipe_stencil"),
            ("vertex-inputs", "pipe_vinputs"),
            ("samplers", "pipe_samplers"),
            ("vbuffers", "pipe_vbuffers"),
            ("ibuffer", "pipe_ibuffer"),
        ],
    )
    def test_pipeline_sub_routes(self, sub: str, handler: str) -> None:
        m = resolve_path(f"/draws/42/pipeline/{sub}")
        assert m is not None
        assert m.handler == handler
        assert m.args["eid"] == 42

    def test_postvs_route(self) -> None:
        m = resolve_path("/draws/42/postvs")
        assert m is not None
        assert m.handler == "postvs"
        assert m.args["eid"] == 42


# ── Resource usage route ──────────────────────────────────────────────


def test_resources_id_usage() -> None:
    m = resolve_path("/resources/97/usage")
    assert m == PathMatch(kind="leaf", handler="usage", args={"id": 97})


# ── Counters ─────────────────────────────────────────────────────────


def test_counters_dir() -> None:
    m = resolve_path("/counters")
    assert m == PathMatch(kind="dir", handler=None, args={})


def test_counters_list_leaf() -> None:
    m = resolve_path("/counters/list")
    assert m == PathMatch(kind="leaf", handler="counter_list", args={})


# ── Descriptors ───────────────────────────────────────────────────────


def test_descriptors_route() -> None:
    m = resolve_path("/draws/42/descriptors")
    assert m is not None
    assert m.kind == "leaf"
    assert m.handler == "descriptors"
    assert m.args == {"eid": 42}
