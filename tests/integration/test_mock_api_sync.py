"""Verify mock_renderdoc stays in sync with the real renderdoc module.

Compares enum values and dataclass fields between mock and real API.
Runs only when real renderdoc is available (GPU marker).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.gpu

sys.path.insert(0, str(Path(__file__).parent.parent / "mocks"))
import mock_renderdoc as mock  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SWIG_INTERNAL = {"this", "thisown"}


def _real_enum_members(cls: Any) -> dict[str, int]:
    return {m.name: m.value for m in cls}


def _mock_enum_members(cls: Any) -> dict[str, int]:
    return {m.name: m.value for m in cls}


def _instance_fields(cls: Any) -> set[str]:
    """Get non-callable, non-private attribute names from a default instance."""
    try:
        obj = cls()
    except Exception:
        return set()
    return {
        k
        for k in dir(obj)
        if not k.startswith("_") and not callable(getattr(obj, k)) and k not in SWIG_INTERNAL
    }


# ---------------------------------------------------------------------------
# Enum sync tests
# ---------------------------------------------------------------------------

ENUM_PAIRS = [
    ("ResourceType", "ResourceType"),
    ("TextureType", "TextureType"),
    ("TextureCategory", "TextureCategory"),
    ("BufferCategory", "BufferCategory"),
    ("FileType", "FileType"),
    ("ShaderStage", "ShaderStage"),
    ("ActionFlags", "ActionFlags"),
    ("MessageSeverity", "MessageSeverity"),
]


@pytest.mark.parametrize("real_name,mock_name", ENUM_PAIRS, ids=[p[0] for p in ENUM_PAIRS])
def test_enum_members_match(rd_module: Any, real_name: str, mock_name: str) -> None:
    """Every real enum member must exist in mock with the same value."""
    real_cls = getattr(rd_module, real_name)
    mock_cls = getattr(mock, mock_name)

    real_members = _real_enum_members(real_cls)
    mock_members = _mock_enum_members(mock_cls)

    missing = set(real_members) - set(mock_members)
    assert not missing, f"mock {mock_name} missing members: {sorted(missing)}"

    wrong = {
        k: (real_members[k], mock_members[k])
        for k in real_members
        if k in mock_members and real_members[k] != mock_members[k]
    }
    assert not wrong, f"mock {mock_name} value mismatch: {wrong}"


# ---------------------------------------------------------------------------
# Dataclass / struct field sync tests
# ---------------------------------------------------------------------------

STRUCT_PAIRS = [
    ("ResourceDescription", "ResourceDescription"),
    ("TextureDescription", "TextureDescription"),
    ("BufferDescription", "BufferDescription"),
    ("ResourceFormat", "ResourceFormat"),
    ("TextureSave", "TextureSave"),
    ("TextureSliceMapping", "TextureSliceMapping"),
    ("Subresource", "Subresource"),
    ("ShaderReflection", "ShaderReflection"),
    ("ShaderResource", "ShaderResource"),
    ("ConstantBlock", "ConstantBlock"),
    ("Descriptor", "Descriptor"),
    ("Viewport", "Viewport"),
    ("Scissor", "Scissor"),
    ("MeshFormat", "MeshFormat"),
]


@pytest.mark.parametrize("real_name,mock_name", STRUCT_PAIRS, ids=[p[0] for p in STRUCT_PAIRS])
def test_struct_fields_match(rd_module: Any, real_name: str, mock_name: str) -> None:
    """Every field on a real struct must exist on the mock counterpart."""
    real_cls = getattr(rd_module, real_name)
    mock_cls = getattr(mock, mock_name)

    real_fields = _instance_fields(real_cls)
    mock_fields = _instance_fields(mock_cls)

    missing = real_fields - mock_fields
    assert not missing, f"mock {mock_name} missing fields: {sorted(missing)}"
