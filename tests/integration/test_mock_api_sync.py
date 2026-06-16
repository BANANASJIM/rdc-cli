"""Verify mock_renderdoc stays in sync with the real renderdoc module.

Compares enum values and dataclass fields between mock and real API.
Runs only when real renderdoc is available (GPU marker).
"""

from __future__ import annotations

from typing import Any

import mock_renderdoc as mock
import pytest

pytestmark = pytest.mark.gpu

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


# SWIG injects these helper callables on every wrapped class; they are not part
# of the renderdoc API surface and must be filtered before comparing methods.
SWIG_METHOD_HELPERS = {"acquire", "append", "disown", "next", "own"}


def _public_methods(cls: Any) -> set[str]:
    """Reflect public method names off a class (never an instance).

    Real renderdoc SWIG classes (ReplayController, PipeState, CaptureFile) are
    not default-constructible, so reflection happens on the class object. Names
    that are private, SWIG-internal, or SWIG helper callables are excluded.

    Args:
        cls: A class object (mock or real renderdoc) to introspect.

    Returns:
        The set of public, callable attribute names declared on ``cls``.
    """
    return {
        k
        for k in dir(cls)
        if not k.startswith("_")
        and k not in SWIG_INTERNAL
        and k not in SWIG_METHOD_HELPERS
        and callable(getattr(cls, k, None))
    }


def _is_api_method(name: str) -> bool:
    """True for PascalCase renderdoc-API-style names (not snake_case helpers).

    Mock classes add snake_case convenience helpers (e.g. ``set_mesh_data``)
    that never claim to mirror the real API, so they are exempt from sync checks.

    Args:
        name: A method name.

    Returns:
        Whether the name looks like a renderdoc API method.
    """
    return name[:1].isupper()


def _missing_methods(real_methods: set[str], mock_methods: set[str]) -> set[str]:
    """Mock-claimed API methods that do not exist on the real class.

    Catches the drift the suite is meant to guard against: a mock method that
    silently survives after the upstream method was renamed or removed. Only
    PascalCase (API-style) mock methods are considered; snake_case test helpers
    are ignored.

    Args:
        real_methods: Public method names on the real renderdoc class.
        mock_methods: Public method names on the mock counterpart.

    Returns:
        Mock API methods absent from ``real_methods``.
    """
    return {m for m in mock_methods - real_methods if _is_api_method(m)}


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
    ("ResourceUsage", "ResourceUsage"),
    ("GPUCounter", "GPUCounter"),
    ("CounterUnit", "CounterUnit"),
    ("CompType", "CompType"),
    ("DescriptorType", "DescriptorType"),
    ("AddressMode", "AddressMode"),
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
    ("ShaderVariable", "ShaderVariable"),
    ("EventUsage", "EventUsage"),
    ("CounterDescription", "CounterDescription"),
    ("CounterResult", "CounterResult"),
    ("DescriptorAccess", "DescriptorAccess"),
    ("SamplerDescriptor", "SamplerDescriptor"),
    ("UsedDescriptor", "UsedDescriptor"),
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


# ---------------------------------------------------------------------------
# Method-surface sync tests (the heart of the mock-sync guard)
# ---------------------------------------------------------------------------
#
# The enum/struct checks above filter out callables, so a Mock* class can keep
# a method whose upstream counterpart was renamed or removed and CI still goes
# green. These tests close that gap by reflecting the real class's method
# surface and asserting the mock does not claim API methods that no longer
# exist upstream. Reflection is on the CLASS, not an instance, because the real
# SWIG classes are not default-constructible.

# (real_name, mock_name) for the SWIG classes whose methods are wrapped by rdc.
CLASS_PAIRS = [
    ("ReplayController", "MockReplayController"),
    ("PipeState", "MockPipeState"),
    ("CaptureFile", "MockCaptureFile"),
]

# Mock-only API-style methods that are deliberately not backed by the current
# real renderdoc surface. Each entry is an explicit, reviewable exception:
#   - GetCallstack: the daemon probes it via getattr() and falls back when
#     absent (see handlers/capturefile.py); the mock provides it for coverage.
#   - HasPendingDependencies / EmbedDependenciesIntoCapture: exercised only
#     through the mock; not present on the pinned renderdoc build. Drop the
#     entry (and the mock method) once upstream restores or renames them.
# A method must be listed here to be allowed to diverge; anything else fails.
KNOWN_MOCK_ONLY: dict[str, set[str]] = {
    "MockReplayController": {"GetCallstack"},
    "MockPipeState": set(),
    "MockCaptureFile": {"HasPendingDependencies", "EmbedDependenciesIntoCapture"},
}


@pytest.mark.gpu
@pytest.mark.parametrize("real_name,mock_name", CLASS_PAIRS, ids=[p[0] for p in CLASS_PAIRS])
def test_mock_methods_exist_on_real(rd_module: Any, real_name: str, mock_name: str) -> None:
    """Every API method the mock claims must still exist on real renderdoc.

    Guards against a mock method outliving a renamed or removed upstream method.
    Documented exceptions live in ``KNOWN_MOCK_ONLY``.
    """
    real_cls = getattr(rd_module, real_name)
    mock_cls = getattr(mock, mock_name)

    missing = _missing_methods(_public_methods(real_cls), _public_methods(mock_cls))
    unexpected = missing - KNOWN_MOCK_ONLY[mock_name]
    assert not unexpected, (
        f"{mock_name} claims API methods absent from real {real_name} "
        f"(renamed/removed upstream?): {sorted(unexpected)}"
    )


def test_real_class_names_resolve(rd_module: Any) -> None:
    """Negative guard: the real class names must resolve on renderdoc.

    Without this, a renamed real class would turn ``test_mock_methods_exist_on_real``
    into a silent no-op (every mock method trivially absent from an empty real
    surface). The ``rd_module`` fixture already skips with a reason when
    renderdoc is missing, so this can only fail on a genuine rename.
    """
    for real_name, _ in CLASS_PAIRS:
        real_cls = getattr(rd_module, real_name, None)
        assert real_cls is not None, f"renderdoc.{real_name} no longer resolves"
        assert _public_methods(real_cls), f"renderdoc.{real_name} exposes no public methods"


# ---------------------------------------------------------------------------
# CPU-tier coverage of the comparison logic (no GPU / no real renderdoc)
# ---------------------------------------------------------------------------


class _ShrunkRealController:
    """Stand-in for a shrunk real renderdoc class to exercise the helpers."""

    def GetRootActions(self) -> None: ...

    def GetResources(self) -> None: ...

    def set_mesh_data(self) -> None: ...  # snake_case helper, must be ignored


def test_missing_methods_helper_flags_drift() -> None:
    """_missing_methods reports an API method the shrunk real class lacks."""
    real = _public_methods(_ShrunkRealController)
    mock_methods = real | {"GetCallstack", "set_mesh_data"}

    missing = _missing_methods(real, mock_methods)
    assert missing == {"GetCallstack"}, missing
    assert "set_mesh_data" not in missing


def test_public_methods_filters_swig_helpers() -> None:
    """_public_methods drops SWIG helpers, dunders, and snake_case is kept raw."""
    methods = _public_methods(_ShrunkRealController)
    assert "GetRootActions" in methods
    assert "set_mesh_data" in methods
    assert SWIG_METHOD_HELPERS.isdisjoint(methods)
    assert not any(m.startswith("_") for m in methods)


def test_missing_methods_empty_when_subset() -> None:
    """A mock that only implements a subset of real methods is fully in sync."""
    real = _public_methods(_ShrunkRealController)
    mock_methods = {"GetRootActions"}
    assert _missing_methods(real, mock_methods) == set()
