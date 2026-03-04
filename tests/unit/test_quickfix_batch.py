"""Tests for code-quickfix-batch fixes."""

from __future__ import annotations

import importlib.metadata
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import mock_renderdoc as rd
from conftest import make_daemon_state, rpc_request

from rdc.adapter import RenderDocAdapter
from rdc.daemon_server import DaemonState, _handle_request
from rdc.vfs.tree_cache import build_vfs_skeleton

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_actions() -> list[rd.ActionDescription]:
    return [
        rd.ActionDescription(
            eventId=10,
            flags=rd.ActionFlags.Drawcall,
            numIndices=300,
            _name="Draw #10",
        ),
    ]


def _make_resources() -> list[rd.ResourceDescription]:
    return [
        rd.ResourceDescription(
            resourceId=rd.ResourceId(100),
            name="Texture 100",
            type=rd.ResourceType.Texture,
            byteSize=8294400,
        ),
        rd.ResourceDescription(
            resourceId=rd.ResourceId(200),
            name="Buffer 200",
            type=rd.ResourceType.Buffer,
        ),
    ]


def _make_vfs_state() -> DaemonState:
    actions = _make_actions()
    resources = _make_resources()
    sf = SimpleNamespace(chunks=[])
    ctrl = SimpleNamespace(
        GetRootActions=lambda: actions,
        GetResources=lambda: resources,
        GetTextures=lambda: [],
        GetBuffers=lambda: [],
        GetAPIProperties=lambda: SimpleNamespace(pipelineType="Vulkan"),
        GetPipelineState=lambda: rd.MockPipeState(),
        SetFrameEvent=lambda eid, force: None,
        GetStructuredFile=lambda: sf,
        GetDebugMessages=lambda: [],
        Shutdown=lambda: None,
    )
    state = make_daemon_state(
        ctrl=ctrl,
        version=(1, 33),
        max_eid=300,
        structured_file=sf,
        res_names={100: "Texture 100", 200: "Buffer 200"},
        res_types={100: "Texture", 200: "Buffer"},
        res_rid_map={int(r.resourceId): r for r in resources},
    )
    state.vfs_tree = build_vfs_skeleton(actions, resources, sf=sf)
    return state


# ---------------------------------------------------------------------------
# Fix 1: byteSize
# ---------------------------------------------------------------------------


class TestFix1ByteSize:
    def test_bytesize_read_from_full_resource(self) -> None:
        """TC-1.1: byteSize read from res_rid_map via full resource object."""
        state = _make_vfs_state()
        resp, _ = _handle_request(
            rpc_request("vfs_ls", {"path": "/resources", "long": True}), state
        )
        result = resp["result"]
        child_100 = next(c for c in result["children"] if c["name"] == "100")
        assert child_100["size"] == 8294400

    def test_missing_bytesize_falls_back(self) -> None:
        """TC-1.2: missing byteSize falls back to '-'."""
        state = _make_vfs_state()
        # Replace resource 200 with object lacking byteSize
        state.res_rid_map[200] = SimpleNamespace()
        resp, _ = _handle_request(
            rpc_request("vfs_ls", {"path": "/resources", "long": True}), state
        )
        result = resp["result"]
        child_200 = next(c for c in result["children"] if c["name"] == "200")
        assert child_200["size"] == "-"

    def test_getusage_receives_resource_id(self) -> None:
        """TC-1.3: GetUsage call sites receive a ResourceId, not ResourceDescription."""
        ctrl = rd.MockReplayController()
        ctrl._resources = _make_resources()
        ctrl._usage_map = {
            100: [rd.EventUsage(eventId=10, usage=rd.ResourceUsage.ColorTarget)],
            200: [],
        }
        state = DaemonState(capture="x.rdc", current_eid=0, token="tok")
        state.adapter = RenderDocAdapter(controller=ctrl, version=(1, 33))
        state.res_names = {int(r.resourceId): r.name for r in ctrl._resources}
        state.res_types = {int(r.resourceId): r.type.name for r in ctrl._resources}
        state.res_rid_map = {int(r.resourceId): r for r in ctrl._resources}

        captured_args: list[Any] = []
        original_get_usage = ctrl.GetUsage

        def tracking_get_usage(rid: Any) -> list[Any]:
            captured_args.append(rid)
            return original_get_usage(rid)

        ctrl.GetUsage = tracking_get_usage  # type: ignore[assignment]

        resp, _ = _handle_request(rpc_request("usage", {"id": 100}), state)
        assert "result" in resp
        assert len(captured_args) == 1
        # Should receive a ResourceId (int-convertible), not a ResourceDescription
        assert int(captured_args[0]) == 100


# ---------------------------------------------------------------------------
# Fix 2: zombie process cleanup
# ---------------------------------------------------------------------------


class TestFix2ZombieCleanup:
    @patch("rdc.services.session_service._check_existing_session", return_value=(False, None))
    @patch("rdc.services.session_service.wait_for_ping", return_value=(False, "timeout"))
    @patch("rdc.services.session_service.start_daemon")
    def test_proc_wait_called_on_timeout(
        self,
        mock_start: MagicMock,
        mock_ping: MagicMock,
        mock_check: MagicMock,
    ) -> None:
        """TC-2.1: proc.wait() called after communicate raises TimeoutExpired."""
        from rdc.services.session_service import open_session

        mock_proc = MagicMock()
        mock_proc.communicate.side_effect = subprocess.TimeoutExpired(cmd="rdc", timeout=5)
        mock_start.return_value = mock_proc

        ok, msg = open_session(Path("test.rdc"))
        assert not ok
        assert mock_proc.wait.call_count >= 1

    @patch("rdc.services.session_service._check_existing_session", return_value=(False, None))
    @patch("rdc.services.session_service.wait_for_ping", return_value=(False, "timeout"))
    @patch("rdc.services.session_service.start_daemon")
    def test_normal_communicate_no_extra_wait(
        self,
        mock_start: MagicMock,
        mock_ping: MagicMock,
        mock_check: MagicMock,
    ) -> None:
        """TC-2.2: normal communicate path does not call proc.wait()."""
        from rdc.services.session_service import open_session

        mock_proc = MagicMock()
        mock_proc.communicate.return_value = ("", "some error\n")
        mock_start.return_value = mock_proc

        ok, msg = open_session(Path("test.rdc"))
        assert not ok
        assert "some error" in msg
        assert mock_proc.wait.call_count == 0


# ---------------------------------------------------------------------------
# Fix 3: /by-marker removed
# ---------------------------------------------------------------------------


class TestFix3ByMarkerRemoved:
    def test_by_marker_absent_from_skeleton(self) -> None:
        """TC-3.1: by-marker absent from root children after skeleton build."""
        tree = build_vfs_skeleton(actions=[], resources=[])
        assert "by-marker" not in tree.static["/"].children
        assert "/by-marker" not in tree.static

    def test_vfs_ls_root_no_by_marker(self) -> None:
        """TC-3.2: root listing via vfs_ls does not include by-marker."""
        state = _make_vfs_state()
        resp, _ = _handle_request(rpc_request("vfs_ls", {"path": "/"}), state)
        names = [c["name"] for c in resp["result"]["children"]]
        assert "by-marker" not in names


# ---------------------------------------------------------------------------
# Fix 4: rich optional dependency removed
# ---------------------------------------------------------------------------


class TestFix4RichRemoved:
    def test_rich_not_in_optional_deps(self) -> None:
        """TC-4.1: rich not listed as optional dependency in package metadata."""
        meta = importlib.metadata.metadata("rdc-cli")
        requires = meta.get_all("Requires-Dist") or []
        rich_extras = [r for r in requires if r.startswith("rich") and 'extra == "rich"' in r]
        assert rich_extras == []
