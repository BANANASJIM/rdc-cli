"""E2E tests for output format flags (category 4).

Tests --json, --jsonl, --no-header, and -q flags across various commands.
All IDs and counts are discovered dynamically via ``capture_meta``.
"""

from __future__ import annotations

import json

import pytest
from conftest import CaptureMetadata
from e2e_helpers import rdc, rdc_json, rdc_ok

pytestmark = pytest.mark.gpu


class TestEventsJson:
    """4.1: rdc events --json."""

    def test_valid_json_array(self, vkcube_session: str, capture_meta: CaptureMetadata) -> None:
        """``rdc events --json`` returns a valid JSON array."""
        data = rdc_json("events", session=vkcube_session)
        assert isinstance(data, list)
        assert len(data) == capture_meta.total_events
        for item in data:
            assert "eid" in item
            assert "type" in item
            assert "name" in item


class TestEventsJsonl:
    """4.2: rdc events --jsonl."""

    def test_one_json_per_line(self, vkcube_session: str, capture_meta: CaptureMetadata) -> None:
        """``rdc events --jsonl`` outputs one JSON object per line."""
        out = rdc_ok("events", "--jsonl", session=vkcube_session)
        lines = [ln for ln in out.strip().splitlines() if ln.strip()]
        assert len(lines) == capture_meta.total_events
        for line in lines:
            obj = json.loads(line)
            assert isinstance(obj, dict)
            assert "eid" in obj


class TestEventsNoHeader:
    """4.3: rdc events --no-header."""

    def test_no_eid_header(self, vkcube_session: str) -> None:
        """``rdc events --no-header`` omits the TSV header row."""
        out = rdc_ok("events", "--no-header", session=vkcube_session)
        first_line = out.strip().splitlines()[0]
        assert not first_line.startswith("EID")


class TestEventsQuiet:
    """4.4: rdc events -q."""

    def test_eids_only(self, vkcube_session: str, capture_meta: CaptureMetadata) -> None:
        """``rdc events -q`` outputs only EID values."""
        out = rdc_ok("events", "-q", session=vkcube_session)
        eids = [ln.strip() for ln in out.strip().splitlines() if ln.strip()]
        assert len(eids) == capture_meta.total_events
        expected = {str(e) for e in capture_meta.all_eids}
        assert set(eids) == expected


class TestDrawsJson:
    """4.5: rdc draws --json."""

    def test_valid_json_array(self, vkcube_session: str) -> None:
        """``rdc draws --json`` returns a valid JSON array."""
        data = rdc_json("draws", session=vkcube_session)
        assert isinstance(data, list)
        assert len(data) >= 1
        for item in data:
            assert "eid" in item
            assert "triangles" in item


class TestResourcesJson:
    """4.6: rdc resources --json."""

    def test_valid_json_items(self, vkcube_session: str, capture_meta: CaptureMetadata) -> None:
        """``rdc resources --json`` returns expected number of items."""
        data = rdc_json("resources", session=vkcube_session)
        assert isinstance(data, list)
        assert len(data) == capture_meta.total_resources
        for item in data:
            assert "id" in item
            assert "type" in item


class TestResourcesQuiet:
    """4.7: rdc resources -q."""

    def test_resource_ids_only(self, vkcube_session: str, capture_meta: CaptureMetadata) -> None:
        """``rdc resources -q`` outputs resource IDs only, one per line."""
        out = rdc_ok("resources", "-q", session=vkcube_session)
        ids = [ln.strip() for ln in out.strip().splitlines() if ln.strip()]
        assert len(ids) == capture_meta.total_resources
        for rid in ids:
            assert rid.isdigit()


class TestResourceJson:
    """4.8: rdc resource <texture_id> --json."""

    def test_lowercase_keys(self, vkcube_session: str, capture_meta: CaptureMetadata) -> None:
        """``rdc resource <id> --json`` returns JSON with lowercase keys."""
        data = rdc_json("resource", str(capture_meta.texture_id), session=vkcube_session)
        assert isinstance(data, dict)
        assert "id" in data
        assert "type" in data
        assert "name" in data
        for key in data:
            assert key == key.lower(), f"key {key!r} is not lowercase"


class TestPixelJson:
    """4.9: rdc pixel X Y EID --json."""

    def test_pixel_history_json(self, vkcube_session: str, capture_meta: CaptureMetadata) -> None:
        """``rdc pixel X Y EID --json`` returns full pixel history."""
        result = rdc(
            "pixel",
            str(capture_meta.pixel_x),
            str(capture_meta.pixel_y),
            str(capture_meta.draw_eid),
            "--json",
            session=vkcube_session,
            timeout=60,
        )
        assert result.returncode == 0, f"pixel --json failed:\n{result.stderr}"
        data = json.loads(result.stdout)
        assert isinstance(data, dict)
        assert "modifications" in data


class TestCatInfoJson:
    """4.10: rdc cat /info --json."""

    def test_vfs_leaf_json(self, vkcube_session: str) -> None:
        """``rdc cat /info --json`` returns VFS leaf content as JSON."""
        data = rdc_json("cat", "/info", session=vkcube_session)
        assert isinstance(data, dict)
