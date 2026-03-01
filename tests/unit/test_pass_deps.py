"""Tests for pass dependency DAG: service, daemon handler, CLI."""

from __future__ import annotations

import json
from typing import Any

import mock_renderdoc as rd
from click.testing import CliRunner
from conftest import patch_cli_session, rpc_request

from rdc.adapter import RenderDocAdapter
from rdc.commands.resources import passes_cmd
from rdc.daemon_server import DaemonState, _handle_request
from rdc.services.query_service import build_pass_deps

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _eu(eid: int, usage: rd.ResourceUsage) -> rd.EventUsage:
    return rd.EventUsage(eventId=eid, usage=usage)


def _pass(name: str, begin: int, end: int) -> dict[str, Any]:
    return {"name": name, "begin_eid": begin, "end_eid": end, "draws": 0}


# ---------------------------------------------------------------------------
# Service: build_pass_deps() — cases 1-20
# ---------------------------------------------------------------------------


class TestServiceSingleEdge:
    """Case 1: A writes 97 (ColorTarget), B reads 97 (PS_Resource)."""

    def test_single_edge(self) -> None:
        passes = [_pass("A", 1, 10), _pass("B", 11, 20)]
        usage = {
            97: [
                _eu(5, rd.ResourceUsage.ColorTarget),
                _eu(15, rd.ResourceUsage.PS_Resource),
            ]
        }
        result = build_pass_deps(passes, usage)
        assert len(result["edges"]) == 1
        e = result["edges"][0]
        assert e["src"] == "A"
        assert e["dst"] == "B"
        assert e["resources"] == [97]


class TestServiceNoEdges:
    """Case 2: Independent passes."""

    def test_no_edges(self) -> None:
        passes = [_pass("A", 1, 10), _pass("B", 11, 20)]
        usage = {
            97: [_eu(5, rd.ResourceUsage.ColorTarget)],
            200: [_eu(15, rd.ResourceUsage.ColorTarget)],
        }
        result = build_pass_deps(passes, usage)
        assert result["edges"] == []


class TestServiceChain:
    """Case 3: A->B->C chain."""

    def test_chain(self) -> None:
        passes = [_pass("A", 1, 10), _pass("B", 11, 20), _pass("C", 21, 30)]
        usage = {
            97: [
                _eu(5, rd.ResourceUsage.ColorTarget),
                _eu(15, rd.ResourceUsage.PS_Resource),
            ],
            200: [
                _eu(16, rd.ResourceUsage.ColorTarget),
                _eu(25, rd.ResourceUsage.PS_Resource),
            ],
        }
        result = build_pass_deps(passes, usage)
        edges = result["edges"]
        assert len(edges) == 2
        srcs_dsts = [(e["src"], e["dst"]) for e in edges]
        assert ("A", "B") in srcs_dsts
        assert ("B", "C") in srcs_dsts
        assert ("A", "C") not in srcs_dsts


class TestServiceDiamond:
    """Case 4: Diamond A->B, A->C, B->D, C->D."""

    def test_diamond(self) -> None:
        passes = [
            _pass("A", 1, 10),
            _pass("B", 11, 20),
            _pass("C", 21, 30),
            _pass("D", 31, 40),
        ]
        usage = {
            97: [
                _eu(5, rd.ResourceUsage.ColorTarget),
                _eu(15, rd.ResourceUsage.PS_Resource),
                _eu(25, rd.ResourceUsage.PS_Resource),
            ],
            200: [
                _eu(16, rd.ResourceUsage.ColorTarget),
                _eu(35, rd.ResourceUsage.PS_Resource),
            ],
            300: [
                _eu(26, rd.ResourceUsage.ColorTarget),
                _eu(36, rd.ResourceUsage.PS_Resource),
            ],
        }
        result = build_pass_deps(passes, usage)
        edges = result["edges"]
        pairs = {(e["src"], e["dst"]) for e in edges}
        assert pairs == {("A", "B"), ("A", "C"), ("B", "D"), ("C", "D")}


class TestServiceSinglePass:
    """Case 5: Single pass, no edges."""

    def test_single_pass(self) -> None:
        passes = [_pass("A", 1, 10)]
        usage = {97: [_eu(5, rd.ResourceUsage.ColorTarget)]}
        result = build_pass_deps(passes, usage)
        assert result["edges"] == []


class TestServiceSelfLoop:
    """Case 6: Self-loop excluded."""

    def test_self_loop_excluded(self) -> None:
        passes = [_pass("A", 1, 10)]
        usage = {
            97: [
                _eu(3, rd.ResourceUsage.Clear),
                _eu(7, rd.ResourceUsage.PS_Resource),
            ]
        }
        result = build_pass_deps(passes, usage)
        assert result["edges"] == []


class TestServiceOutsidePass:
    """Case 7: Events outside any pass ignored."""

    def test_outside_pass(self) -> None:
        passes = [_pass("A", 1, 20), _pass("B", 30, 40)]
        usage = {
            97: [
                _eu(50, rd.ResourceUsage.ColorTarget),
                _eu(55, rd.ResourceUsage.PS_Resource),
            ]
        }
        result = build_pass_deps(passes, usage)
        assert result["edges"] == []


class TestServiceEmptyPassList:
    """Case 8: Empty pass list."""

    def test_empty_passes(self) -> None:
        usage = {97: [_eu(5, rd.ResourceUsage.ColorTarget)]}
        result = build_pass_deps([], usage)
        assert result["edges"] == []


class TestServiceEmptyUsageMap:
    """Case 9: Empty usage map."""

    def test_empty_usage(self) -> None:
        passes = [_pass("A", 1, 10), _pass("B", 11, 20)]
        result = build_pass_deps(passes, {})
        assert result["edges"] == []


class TestServiceMultipleWriters:
    """Case 10: Resource written by multiple passes."""

    def test_multiple_writers(self) -> None:
        passes = [_pass("A", 1, 10), _pass("B", 11, 20), _pass("C", 21, 30)]
        usage = {
            97: [
                _eu(5, rd.ResourceUsage.ColorTarget),
                _eu(15, rd.ResourceUsage.ColorTarget),
                _eu(25, rd.ResourceUsage.PS_Resource),
            ]
        }
        result = build_pass_deps(passes, usage)
        pairs = {(e["src"], e["dst"]) for e in result["edges"]}
        assert ("A", "C") in pairs
        assert ("B", "C") in pairs


class TestServiceMultiResourceEdge:
    """Case 11: Multiple shared resources on one edge."""

    def test_multi_resource(self) -> None:
        passes = [_pass("A", 1, 10), _pass("B", 11, 20)]
        usage = {
            97: [
                _eu(5, rd.ResourceUsage.ColorTarget),
                _eu(15, rd.ResourceUsage.PS_Resource),
            ],
            200: [
                _eu(6, rd.ResourceUsage.ColorTarget),
                _eu(16, rd.ResourceUsage.PS_Resource),
            ],
        }
        result = build_pass_deps(passes, usage)
        assert len(result["edges"]) == 1
        assert set(result["edges"][0]["resources"]) == {97, 200}


class TestServiceCopyOp:
    """Case 12: Copy operation — CopySrc=read, CopyDst=write."""

    def test_copy(self) -> None:
        passes = [_pass("A", 1, 10), _pass("B", 11, 20), _pass("C", 21, 30)]
        usage = {
            97: [
                _eu(5, rd.ResourceUsage.CopySrc),
                _eu(15, rd.ResourceUsage.CopyDst),
                _eu(25, rd.ResourceUsage.PS_Resource),
            ]
        }
        result = build_pass_deps(passes, usage)
        pairs = {(e["src"], e["dst"]) for e in result["edges"]}
        assert ("B", "C") in pairs
        assert ("A", "C") not in pairs


class TestServiceComputeRW:
    """Case 13: CS_RWResource counts as write."""

    def test_compute_rw(self) -> None:
        passes = [_pass("A", 1, 10), _pass("B", 11, 20)]
        usage = {
            97: [
                _eu(5, rd.ResourceUsage.CS_RWResource),
                _eu(15, rd.ResourceUsage.CS_Resource),
            ]
        }
        result = build_pass_deps(passes, usage)
        assert len(result["edges"]) == 1
        assert result["edges"][0]["src"] == "A"


class TestServiceSinkPass:
    """Case 14: Pass with only reads (sink)."""

    def test_sink(self) -> None:
        passes = [_pass("A", 1, 10), _pass("Z", 11, 20)]
        usage = {
            97: [
                _eu(5, rd.ResourceUsage.ColorTarget),
                _eu(15, rd.ResourceUsage.PS_Resource),
            ],
        }
        result = build_pass_deps(passes, usage)
        assert len(result["edges"]) == 1
        assert result["edges"][0]["dst"] == "Z"
        # Z has no outgoing edges
        outgoing_from_z = [e for e in result["edges"] if e["src"] == "Z"]
        assert outgoing_from_z == []


class TestServiceSourcePass:
    """Case 15: Pass with only writes (source)."""

    def test_source(self) -> None:
        passes = [_pass("Z", 1, 10), _pass("B", 11, 20)]
        usage = {
            97: [
                _eu(5, rd.ResourceUsage.ColorTarget),
                _eu(15, rd.ResourceUsage.PS_Resource),
            ],
        }
        result = build_pass_deps(passes, usage)
        assert len(result["edges"]) == 1
        assert result["edges"][0]["src"] == "Z"
        incoming_to_z = [e for e in result["edges"] if e["dst"] == "Z"]
        assert incoming_to_z == []


class TestServiceDepthStencil:
    """Case 16: DepthStencilTarget write."""

    def test_depth_stencil(self) -> None:
        passes = [_pass("A", 1, 10), _pass("B", 11, 20)]
        usage = {
            97: [
                _eu(5, rd.ResourceUsage.DepthStencilTarget),
                _eu(15, rd.ResourceUsage.PS_Resource),
            ]
        }
        result = build_pass_deps(passes, usage)
        assert len(result["edges"]) == 1


class TestServiceClearWrite:
    """Case 17: Clear write."""

    def test_clear(self) -> None:
        passes = [_pass("A", 1, 10), _pass("B", 11, 20)]
        usage = {
            97: [
                _eu(5, rd.ResourceUsage.Clear),
                _eu(15, rd.ResourceUsage.PS_Resource),
            ]
        }
        result = build_pass_deps(passes, usage)
        assert len(result["edges"]) == 1


class TestServiceGenMips:
    """Case 18: GenMips write."""

    def test_genmips(self) -> None:
        passes = [_pass("A", 1, 10), _pass("B", 11, 20)]
        usage = {
            97: [
                _eu(5, rd.ResourceUsage.GenMips),
                _eu(15, rd.ResourceUsage.PS_Resource),
            ]
        }
        result = build_pass_deps(passes, usage)
        assert len(result["edges"]) == 1


class TestServiceResolveDst:
    """Case 19: ResolveDst is write, ResolveSrc is read."""

    def test_resolve(self) -> None:
        passes = [_pass("A", 1, 10), _pass("B", 11, 20)]
        usage = {
            97: [
                _eu(5, rd.ResourceUsage.ResolveDst),
                _eu(15, rd.ResourceUsage.PS_Resource),
            ]
        }
        result = build_pass_deps(passes, usage)
        assert len(result["edges"]) == 1

    def test_resolve_src_no_outgoing(self) -> None:
        passes = [_pass("A", 1, 10), _pass("B", 11, 20)]
        usage = {
            97: [
                _eu(5, rd.ResourceUsage.ResolveSrc),
                _eu(15, rd.ResourceUsage.PS_Resource),
            ]
        }
        result = build_pass_deps(passes, usage)
        assert result["edges"] == []


class TestServiceVertexIndexBufferRead:
    """Case 20: VertexBuffer/IndexBuffer are reads, not writes."""

    def test_vb_ib_no_edges(self) -> None:
        passes = [_pass("A", 1, 10), _pass("B", 11, 20)]
        usage = {
            97: [
                _eu(5, rd.ResourceUsage.VertexBuffer),
                _eu(15, rd.ResourceUsage.IndexBuffer),
            ]
        }
        result = build_pass_deps(passes, usage)
        assert result["edges"] == []


# ---------------------------------------------------------------------------
# Edge cases — cases 35-37
# ---------------------------------------------------------------------------


class TestServiceDuplicatePassNames:
    """Case 35: Two passes with identical names."""

    def test_duplicate_names(self) -> None:
        passes = [_pass("MainPass", 1, 10), _pass("MainPass", 11, 20)]
        usage = {
            97: [
                _eu(5, rd.ResourceUsage.ColorTarget),
                _eu(15, rd.ResourceUsage.PS_Resource),
            ]
        }
        result = build_pass_deps(passes, usage)
        assert len(result["edges"]) == 1
        e = result["edges"][0]
        assert e["src"] == "MainPass"
        assert e["dst"] == "MainPass"


class TestServiceResourceIdZero:
    """Case 36: Resource ID 0 excluded."""

    def test_rid_zero(self) -> None:
        passes = [_pass("A", 1, 10), _pass("B", 11, 20)]
        usage = {
            0: [
                _eu(5, rd.ResourceUsage.ColorTarget),
                _eu(15, rd.ResourceUsage.PS_Resource),
            ],
        }
        result = build_pass_deps(passes, usage)
        assert result["edges"] == []


class TestServiceLargeResourceSet:
    """Case 37: 200 resources, no crash."""

    def test_large(self) -> None:
        passes = [_pass("A", 1, 10), _pass("B", 11, 20)]
        usage = {}
        for rid in range(1, 201):
            usage[rid] = [
                _eu(5, rd.ResourceUsage.ColorTarget),
                _eu(15, rd.ResourceUsage.PS_Resource),
            ]
        result = build_pass_deps(passes, usage)
        assert len(result["edges"]) == 1
        assert len(result["edges"][0]["resources"]) == 200


# ---------------------------------------------------------------------------
# Daemon handler: pass_deps — cases 21-24
# ---------------------------------------------------------------------------


def _make_pass_deps_state() -> DaemonState:
    """Build state with two passes and a resource connecting them."""
    ctrl = rd.MockReplayController()
    ctrl._actions = [
        rd.ActionDescription(
            eventId=1,
            flags=rd.ActionFlags.BeginPass,
            children=[
                rd.ActionDescription(
                    eventId=5,
                    flags=rd.ActionFlags.Drawcall | rd.ActionFlags.Indexed,
                    numIndices=6,
                    _name="Draw #5",
                ),
            ],
            _name="Pass A",
        ),
        rd.ActionDescription(
            eventId=10,
            flags=rd.ActionFlags.EndPass,
            _name="EndPass",
        ),
        rd.ActionDescription(
            eventId=11,
            flags=rd.ActionFlags.BeginPass,
            children=[
                rd.ActionDescription(
                    eventId=15,
                    flags=rd.ActionFlags.Drawcall | rd.ActionFlags.Indexed,
                    numIndices=3,
                    _name="Draw #15",
                ),
            ],
            _name="Pass B",
        ),
        rd.ActionDescription(
            eventId=20,
            flags=rd.ActionFlags.EndPass,
            _name="EndPass",
        ),
    ]
    ctrl._resources = [
        rd.ResourceDescription(
            resourceId=rd.ResourceId(97), name="Tex 97", type=rd.ResourceType.Texture
        ),
    ]
    ctrl._usage_map = {
        97: [
            rd.EventUsage(eventId=5, usage=rd.ResourceUsage.ColorTarget),
            rd.EventUsage(eventId=15, usage=rd.ResourceUsage.PS_Resource),
        ],
    }
    state = DaemonState(capture="x.rdc", current_eid=0, token="tok")
    state.adapter = RenderDocAdapter(controller=ctrl, version=(1, 41))
    state.res_names = {int(r.resourceId): r.name for r in ctrl._resources}
    state.res_types = {int(r.resourceId): r.type.name for r in ctrl._resources}
    state.res_rid_map = {int(r.resourceId): r.resourceId for r in ctrl._resources}
    return state


class TestDaemonPassDepsHappy:
    """Case 21: Happy path — one edge."""

    def test_happy(self) -> None:
        state = _make_pass_deps_state()
        resp, running = _handle_request(rpc_request("pass_deps"), state)
        assert running
        edges = resp["result"]["edges"]
        assert len(edges) == 1
        e = edges[0]
        assert isinstance(e["src"], str)
        assert isinstance(e["dst"], str)
        assert 97 in e["resources"]
        assert resp["id"] == 1


class TestDaemonPassDepsNoEdges:
    """Case 22: No edges (no resource overlap)."""

    def test_no_edges(self) -> None:
        state = _make_pass_deps_state()
        ctrl = state.adapter.controller  # type: ignore[union-attr]
        ctrl._usage_map = {
            97: [rd.EventUsage(eventId=5, usage=rd.ResourceUsage.ColorTarget)],
        }
        resp, running = _handle_request(rpc_request("pass_deps"), state)
        assert running
        assert resp["result"]["edges"] == []


class TestDaemonPassDepsNoAdapter:
    """Case 23: No adapter → error -32002."""

    def test_no_adapter(self) -> None:
        state = DaemonState(capture="x.rdc", current_eid=0, token="tok")
        resp, _ = _handle_request(rpc_request("pass_deps"), state)
        assert resp["error"]["code"] == -32002
        assert resp["error"]["message"]


class TestDaemonPassDepsSchema:
    """Case 24: Response schema validation."""

    def test_schema(self) -> None:
        state = _make_pass_deps_state()
        resp, _ = _handle_request(rpc_request("pass_deps"), state)
        edges = resp["result"]["edges"]
        for e in edges:
            assert set(e.keys()) == {"src", "dst", "resources"}
            assert isinstance(e["src"], str) and e["src"]
            assert isinstance(e["dst"], str) and e["dst"]
            assert isinstance(e["resources"], list) and e["resources"]
            assert all(isinstance(r, int) and r > 0 for r in e["resources"])


# ---------------------------------------------------------------------------
# CLI: rdc passes --deps — cases 25-34b
# ---------------------------------------------------------------------------

_ONE_EDGE = {"edges": [{"src": "Shadow", "dst": "Main", "resources": [97]}]}
_TWO_EDGES = {
    "edges": [
        {"src": "Shadow", "dst": "Main", "resources": [97]},
        {"src": "Main", "dst": "Post", "resources": [200, 300]},
    ]
}
_NO_EDGES = {"edges": []}


class TestCliDepsTsv:
    """Cases 25-27: TSV output."""

    def test_tsv_one_edge(self, monkeypatch: Any) -> None:
        patch_cli_session(monkeypatch, _ONE_EDGE)
        result = CliRunner().invoke(passes_cmd, ["--deps"])
        assert result.exit_code == 0
        lines = result.output.strip().splitlines()
        assert lines[0] == "SRC\tDST\tRESOURCES"
        assert "Shadow\tMain\t97" == lines[1]

    def test_tsv_two_edges(self, monkeypatch: Any) -> None:
        patch_cli_session(monkeypatch, _TWO_EDGES)
        result = CliRunner().invoke(passes_cmd, ["--deps"])
        assert result.exit_code == 0
        lines = result.output.strip().splitlines()
        assert len(lines) == 3
        assert "200,300" in lines[2]

    def test_tsv_no_edges(self, monkeypatch: Any) -> None:
        patch_cli_session(monkeypatch, _NO_EDGES)
        result = CliRunner().invoke(passes_cmd, ["--deps"])
        assert result.exit_code == 0
        lines = result.output.strip().splitlines()
        assert lines == ["SRC\tDST\tRESOURCES"]


class TestCliDepsDot:
    """Cases 28-30: DOT output."""

    def test_dot_structure(self, monkeypatch: Any) -> None:
        patch_cli_session(monkeypatch, _ONE_EDGE)
        result = CliRunner().invoke(passes_cmd, ["--deps", "--dot"])
        assert result.exit_code == 0
        assert result.output.startswith("digraph")
        assert "->" in result.output
        assert result.output.strip().endswith("}")

    def test_dot_labels(self, monkeypatch: Any) -> None:
        patch_cli_session(monkeypatch, _ONE_EDGE)
        result = CliRunner().invoke(passes_cmd, ["--deps", "--dot"])
        assert '"Shadow"' in result.output
        assert '"Main"' in result.output
        assert 'label="97"' in result.output

    def test_dot_no_edges(self, monkeypatch: Any) -> None:
        patch_cli_session(monkeypatch, _NO_EDGES)
        result = CliRunner().invoke(passes_cmd, ["--deps", "--dot"])
        assert result.exit_code == 0
        assert "digraph" in result.output
        assert "->" not in result.output


class TestCliDepsJson:
    """Cases 31-32: JSON output."""

    def test_json(self, monkeypatch: Any) -> None:
        patch_cli_session(monkeypatch, _ONE_EDGE)
        result = CliRunner().invoke(passes_cmd, ["--deps", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "edges" in data
        assert len(data["edges"]) == 1
        e = data["edges"][0]
        assert isinstance(e["src"], str)
        assert isinstance(e["resources"], list)

    def test_json_no_edges(self, monkeypatch: Any) -> None:
        patch_cli_session(monkeypatch, _NO_EDGES)
        result = CliRunner().invoke(passes_cmd, ["--deps", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["edges"] == []


class TestCliDepsErrors:
    """Cases 33-34b: Error paths."""

    def test_no_session(self, monkeypatch: Any) -> None:
        patch_cli_session(monkeypatch, None)
        result = CliRunner().invoke(passes_cmd, ["--deps"])
        assert result.exit_code == 1

    def test_deps_without_dot_or_json(self, monkeypatch: Any) -> None:
        patch_cli_session(monkeypatch, _ONE_EDGE)
        result = CliRunner().invoke(passes_cmd, ["--deps"])
        assert result.exit_code == 0

    def test_dot_without_deps(self, monkeypatch: Any) -> None:
        result = CliRunner().invoke(passes_cmd, ["--dot"])
        assert result.exit_code == 2

    def test_graph_without_deps(self, monkeypatch: Any) -> None:
        result = CliRunner().invoke(passes_cmd, ["--graph"])
        assert result.exit_code == 2

    def test_deps_with_unsupported_flags(self, monkeypatch: Any) -> None:
        for flag in ["--no-header", "--jsonl", "-q"]:
            result = CliRunner().invoke(passes_cmd, ["--deps", flag])
            assert result.exit_code == 2, f"{flag} should be rejected with --deps"


class TestCliDepsGraph:
    """--graph output."""

    def test_graph_one_edge(self, monkeypatch: Any) -> None:
        patch_cli_session(monkeypatch, _ONE_EDGE)
        result = CliRunner().invoke(passes_cmd, ["--deps", "--graph"])
        assert result.exit_code == 0
        assert "Legend:" in result.output
        assert "Graph:" in result.output
        assert "[A]" in result.output
        assert "[B]" in result.output
        assert "──▶" in result.output

    def test_graph_chain(self, monkeypatch: Any) -> None:
        patch_cli_session(monkeypatch, _TWO_EDGES)
        result = CliRunner().invoke(passes_cmd, ["--deps", "--graph"])
        assert result.exit_code == 0
        assert "[A]" in result.output
        assert "[B]" in result.output
        assert "[C]" in result.output
        assert "(sink)" in result.output

    def test_graph_no_edges(self, monkeypatch: Any) -> None:
        patch_cli_session(monkeypatch, _NO_EDGES)
        result = CliRunner().invoke(passes_cmd, ["--deps", "--graph"])
        assert result.exit_code == 0
        assert "no dependencies" in result.output
