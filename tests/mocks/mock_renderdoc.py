"""Mock renderdoc module for testing without GPU.

Provides fake implementations of RenderDoc Python API objects sufficient
for testing daemon replay lifecycle, action tree traversal, pipeline state
queries, and structured data access.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, IntFlag
from typing import Any

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ResultCode(IntEnum):
    Succeeded = 0
    InternalError = 1


class ReplaySupport(IntEnum):
    Supported = 0
    Unsupported = 1


class ShaderStage(IntEnum):
    Vertex = 0
    Hull = 1
    Domain = 2
    Geometry = 3
    Pixel = 4
    Compute = 5


class ActionFlags(IntFlag):
    NoFlags = 0
    Drawcall = 0x0001
    Indexed = 0x0002
    Dispatch = 0x0010
    Clear = 0x0020
    Copy = 0x0040
    PassBoundary = 0x1000
    BeginPass = 0x2000
    EndPass = 0x4000


class ResourceType(IntEnum):
    Unknown = 0
    Buffer = 1
    Texture1D = 2
    Texture2D = 3
    Texture3D = 4


class FileType(IntEnum):
    PNG = 0
    JPG = 1


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ResourceId:
    value: int = 0

    def __eq__(self, other: object) -> bool:
        if isinstance(other, ResourceId):
            return self.value == other.value
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.value)

    @classmethod
    def Null(cls) -> ResourceId:
        return cls(0)


@dataclass
class ResourceFormat:
    name: str = "R8G8B8A8_UNORM"


@dataclass
class ResourceDescription:
    resourceId: ResourceId = field(default_factory=ResourceId)
    name: str = ""
    type: ResourceType = ResourceType.Unknown
    width: int = 0
    height: int = 0
    depth: int = 0
    mips: int = 1
    arraysize: int = 1
    format: ResourceFormat = field(default_factory=ResourceFormat)
    creationFlags: int = 0


@dataclass
class APIEvent:
    eventId: int = 0
    chunkIndex: int = 0


@dataclass
class ActionDescription:
    eventId: int = 0
    actionId: int = 0
    flags: ActionFlags = ActionFlags.NoFlags
    numIndices: int = 0
    numInstances: int = 1
    indexOffset: int = 0
    baseVertex: int = 0
    instanceOffset: int = 0
    children: list[ActionDescription] = field(default_factory=list)
    parent: ActionDescription | None = None
    previous: ActionDescription | None = None
    next: ActionDescription | None = None
    events: list[APIEvent] = field(default_factory=list)
    _name: str = ""

    def GetName(self, sf: Any) -> str:
        return self._name


@dataclass
class BoundResource:
    resource: ResourceId = field(default_factory=ResourceId)


@dataclass
class Viewport:
    x: float = 0.0
    y: float = 0.0
    width: float = 1920.0
    height: float = 1080.0


@dataclass
class Scissor:
    x: int = 0
    y: int = 0
    width: int = 1920
    height: int = 1080


@dataclass
class SigParameter:
    varName: str = ""
    semanticName: str = ""
    semanticIndex: int = 0
    regIndex: int = 0
    compType: int = 0
    compCount: int = 0


@dataclass
class ShaderDebugInfo:
    files: list[Any] = field(default_factory=list)
    encoding: int = 0
    entrypoint: str = "main"


@dataclass
class ConstantBlock:
    name: str = ""
    byteSize: int = 0
    variables: list[Any] = field(default_factory=list)
    bindPoint: int = 0


@dataclass
class ShaderResource:
    name: str = ""
    resType: int = 0
    isTexture: bool = False
    bindPoint: int = 0


@dataclass
class ShaderReflection:
    resourceId: ResourceId = field(default_factory=ResourceId)
    inputSignature: list[SigParameter] = field(default_factory=list)
    outputSignature: list[SigParameter] = field(default_factory=list)
    readOnlyResources: list[ShaderResource] = field(default_factory=list)
    readWriteResources: list[ShaderResource] = field(default_factory=list)
    constantBlocks: list[ConstantBlock] = field(default_factory=list)
    debugInfo: ShaderDebugInfo = field(default_factory=ShaderDebugInfo)


@dataclass
class SDBasic:
    value: Any = None


@dataclass
class SDData:
    basic: SDBasic = field(default_factory=SDBasic)


@dataclass
class SDObject:
    name: str = ""
    data: SDData = field(default_factory=SDData)
    children: list[SDObject] = field(default_factory=list)


@dataclass
class SDChunk:
    name: str = ""
    children: list[SDObject] = field(default_factory=list)


@dataclass
class StructuredFile:
    chunks: list[SDChunk] = field(default_factory=list)


# ---------------------------------------------------------------------------
# API Properties
# ---------------------------------------------------------------------------


@dataclass
class APIProperties:
    pipelineType: str = "Vulkan"
    degraded: bool = False


# ---------------------------------------------------------------------------
# Mock PipeState
# ---------------------------------------------------------------------------


class MockPipeState:
    """Mock for controller.GetPipelineState()."""

    def __init__(self) -> None:
        self._shaders: dict[ShaderStage, ResourceId] = {}
        self._reflections: dict[ShaderStage, ShaderReflection | None] = {}
        self._entry_points: dict[ShaderStage, str] = {}
        self._output_targets: list[BoundResource] = []
        self._depth_target: BoundResource = BoundResource()
        self._viewport: Viewport = Viewport()
        self._scissor: Scissor = Scissor()

    def GetShader(self, stage: ShaderStage) -> ResourceId:
        return self._shaders.get(stage, ResourceId.Null())

    def GetShaderReflection(self, stage: ShaderStage) -> ShaderReflection | None:
        return self._reflections.get(stage)

    def GetShaderEntryPoint(self, stage: ShaderStage) -> str:
        return self._entry_points.get(stage, "main")

    def GetOutputTargets(self) -> list[BoundResource]:
        return self._output_targets

    def GetDepthTarget(self) -> BoundResource:
        return self._depth_target

    def GetViewport(self, index: int) -> Viewport:
        return self._viewport

    def GetScissor(self, index: int) -> Scissor:
        return self._scissor

    def GetGraphicsPipelineObject(self) -> ResourceId:
        return ResourceId(1)

    def GetComputePipelineObject(self) -> ResourceId:
        return ResourceId(2)

    def GetPrimitiveTopology(self) -> str:
        return "TriangleList"

    def IsCaptureVK(self) -> bool:
        return True

    def IsCaptureD3D11(self) -> bool:
        return False

    def IsCaptureD3D12(self) -> bool:
        return False

    def IsCaptureGL(self) -> bool:
        return False


# ---------------------------------------------------------------------------
# Mock ReplayController
# ---------------------------------------------------------------------------


class MockReplayController:
    """Mock for renderdoc.ReplayController."""

    def __init__(self) -> None:
        self._actions: list[ActionDescription] = []
        self._resources: list[ResourceDescription] = []
        self._api_props: APIProperties = APIProperties()
        self._pipe_state: MockPipeState = MockPipeState()
        self._current_eid: int = 0
        self._set_frame_event_calls: list[tuple[int, bool]] = []
        self._shutdown_called: bool = False
        self._structured_file: StructuredFile = StructuredFile()

    def GetRootActions(self) -> list[ActionDescription]:
        return self._actions

    def GetResources(self) -> list[ResourceDescription]:
        return self._resources

    def GetAPIProperties(self) -> APIProperties:
        return self._api_props

    def GetPipelineState(self) -> MockPipeState:
        return self._pipe_state

    def SetFrameEvent(self, eid: int, force: bool) -> None:
        self._current_eid = eid
        self._set_frame_event_calls.append((eid, force))

    def GetStructuredFile(self) -> StructuredFile:
        return self._structured_file

    def Shutdown(self) -> None:
        self._shutdown_called = True


# ---------------------------------------------------------------------------
# Mock CaptureFile
# ---------------------------------------------------------------------------


class MockCaptureFile:
    """Mock for renderdoc.CaptureFile."""

    def __init__(self) -> None:
        self._structured_data: StructuredFile = StructuredFile()
        self._path: str = ""
        self._shutdown_called: bool = False

    def OpenFile(self, path: str, filetype: str, progress: Any) -> ResultCode:
        self._path = path
        return ResultCode.Succeeded

    def LocalReplaySupport(self) -> ReplaySupport:
        return ReplaySupport.Supported

    def OpenCapture(self, options: Any, progress: Any) -> tuple[ResultCode, MockReplayController]:
        return ResultCode.Succeeded, MockReplayController()

    def GetStructuredData(self) -> StructuredFile:
        return self._structured_data

    def Shutdown(self) -> None:
        self._shutdown_called = True


# ---------------------------------------------------------------------------
# Module-level functions (mimic renderdoc module)
# ---------------------------------------------------------------------------

_initialised = False


def InitialiseReplay(env: Any, args: list[str]) -> None:
    global _initialised  # noqa: PLW0603
    _initialised = True


def ShutdownReplay() -> None:
    global _initialised  # noqa: PLW0603
    _initialised = False


def OpenCaptureFile() -> MockCaptureFile:
    return MockCaptureFile()


def GlobalEnvironment() -> object:
    return object()


def GetVersionString() -> str:
    return "v1.33"


def GetCommitHash() -> str:
    return "abc123"


class ReplayOptions:
    pass
