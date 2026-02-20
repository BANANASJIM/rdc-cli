"""Mock renderdoc module for testing without GPU.

Provides fake implementations of RenderDoc Python API objects sufficient
for testing daemon replay lifecycle, action tree traversal, pipeline state
queries, and structured data access.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, IntFlag
from pathlib import Path
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
    Task = 6
    Mesh = 7
    RayGen = 8
    Intersection = 9
    AnyHit = 10
    ClosestHit = 11
    Miss = 12
    Callable = 13
    Count = 14


class ActionFlags(IntFlag):
    NoFlags = 0
    Clear = 0x0001
    Drawcall = 0x0002
    Dispatch = 0x0004
    MeshDispatch = 0x0008
    CmdList = 0x0010
    SetMarker = 0x0020
    PushMarker = 0x0040
    PopMarker = 0x0080
    Present = 0x0100
    MultiAction = 0x0200
    Copy = 0x0400
    Resolve = 0x0800
    GenMips = 0x1000
    PassBoundary = 0x2000
    DispatchRay = 0x4000
    BuildAccStruct = 0x8000
    Indexed = 0x10000
    Instanced = 0x20000
    Auto = 0x40000
    Indirect = 0x80000
    ClearColor = 0x100000
    ClearDepthStencil = 0x200000
    BeginPass = 0x400000
    EndPass = 0x800000
    CommandBufferBoundary = 0x1000000


class ResourceType(IntEnum):
    Unknown = 0
    Device = 1
    Queue = 2
    CommandBuffer = 3
    Texture = 4
    Buffer = 5
    View = 6
    Sampler = 7
    SwapchainImage = 8
    Memory = 9
    Shader = 10
    ShaderBinding = 11
    PipelineState = 12
    StateObject = 13
    RenderPass = 14
    Query = 15
    Sync = 16
    Pool = 17
    AccelerationStructure = 18
    DescriptorStore = 19


class TextureType(IntEnum):
    Unknown = 0
    Buffer = 1
    Texture1D = 2
    Texture1DArray = 3
    Texture2D = 4
    TextureRect = 5
    Texture2DArray = 6
    Texture2DMS = 7
    Texture2DMSArray = 8
    Texture3D = 9
    TextureCube = 10
    TextureCubeArray = 11
    Count = 12


class TextureCategory(IntFlag):
    NoFlags = 0
    ShaderRead = 1
    ColorTarget = 2
    DepthTarget = 4
    ShaderReadWrite = 8
    SwapBuffer = 16


class BufferCategory(IntFlag):
    NoFlags = 0
    Vertex = 1
    Index = 2
    Constants = 4
    ReadWrite = 8
    Indirect = 16


class FileType(IntEnum):
    DDS = 0
    PNG = 1
    JPG = 2
    BMP = 3
    TGA = 4
    HDR = 5
    EXR = 6
    Raw = 7
    Count = 8


class MessageSeverity(IntEnum):
    High = 0
    Medium = 1
    Low = 2
    Info = 3


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ResourceId:
    value: int = 0

    def __int__(self) -> int:
        return self.value

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
    compByteWidth: int = 1
    compCount: int = 4
    compType: int = 0
    type: int = 0

    def Name(self) -> str:
        return self.name

    def ElementSize(self) -> int:
        return self.compByteWidth * self.compCount

    def BGRAOrder(self) -> bool:
        return self.name.startswith("B")

    def SRGBCorrected(self) -> bool:
        return "SRGB" in self.name

    def Special(self) -> bool:
        return self.type != 0

    def BlockFormat(self) -> bool:
        return self.name.startswith("BC")


@dataclass
class DebugMessage:
    eventId: int = 0
    severity: MessageSeverity = MessageSeverity.Info
    description: str = ""


@dataclass
class TextureSliceMapping:
    sliceIndex: int = -1
    slicesAsGrid: bool = False
    sliceGridWidth: int = 1
    cubeCruciform: bool = False


@dataclass
class Subresource:
    mip: int = 0
    slice: int = 0
    sample: int = 0


@dataclass
class TextureComponentMapping:
    blackPoint: float = 0.0
    whitePoint: float = 1.0


@dataclass
class FloatVector:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    w: float = 1.0


class AlphaMapping(IntEnum):
    Discard = 0
    BlendToColor = 1
    BlendToCheckerboard = 2
    Preserve = 3


@dataclass
class TextureSampleMapping:
    mapToArray: bool = False
    sampleIndex: int = -1


@dataclass
class TextureSave:
    resourceId: ResourceId = field(default_factory=ResourceId)
    mip: int = -1
    slice: TextureSliceMapping = field(default_factory=TextureSliceMapping)
    destType: FileType = FileType.DDS
    comp: TextureComponentMapping = field(default_factory=TextureComponentMapping)
    alpha: AlphaMapping = AlphaMapping.Preserve
    alphaCol: FloatVector = field(default_factory=FloatVector)
    channelExtract: int = -1
    jpegQuality: int = 90
    sample: TextureSampleMapping = field(default_factory=TextureSampleMapping)
    typeCast: int = 0


@dataclass
class ResourceDescription:
    resourceId: ResourceId = field(default_factory=ResourceId)
    name: str = ""
    type: ResourceType = ResourceType.Unknown
    autogeneratedName: bool = True
    derivedResources: list[ResourceId] = field(default_factory=list)
    parentResources: list[ResourceId] = field(default_factory=list)
    initialisationChunks: list[int] = field(default_factory=list)


@dataclass
class TextureDescription:
    resourceId: ResourceId = field(default_factory=ResourceId)
    width: int = 0
    height: int = 0
    depth: int = 1
    mips: int = 1
    arraysize: int = 1
    dimension: int = 2
    format: ResourceFormat = field(default_factory=ResourceFormat)
    type: TextureType = TextureType.Texture2D
    byteSize: int = 0
    creationFlags: TextureCategory = TextureCategory.ShaderRead
    cubemap: bool = False
    msQual: int = 0
    msSamp: int = 1


@dataclass
class BufferDescription:
    resourceId: ResourceId = field(default_factory=ResourceId)
    length: int = 0
    creationFlags: BufferCategory = BufferCategory.NoFlags
    gpuAddress: int = 0


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
class TextureSwizzle4:
    red: int = 0
    green: int = 1
    blue: int = 2
    alpha: int = 3


@dataclass
class Descriptor:
    resource: ResourceId = field(default_factory=ResourceId)
    view: ResourceId = field(default_factory=ResourceId)
    secondary: ResourceId = field(default_factory=ResourceId)
    format: ResourceFormat = field(default_factory=ResourceFormat)
    firstMip: int = 0
    numMips: int = 1
    firstSlice: int = 0
    numSlices: int = 1
    flags: int = 0
    textureType: int = 0
    type: int = 0
    bufferStructCount: int = 0
    byteOffset: int = 0
    byteSize: int = 0
    elementByteSize: int = 0
    counterByteOffset: int = 0
    minLODClamp: float = 0.0
    swizzle: TextureSwizzle4 = field(default_factory=TextureSwizzle4)


BoundResource = Descriptor


@dataclass
class Viewport:
    x: float = 0.0
    y: float = 0.0
    width: float = 1920.0
    height: float = 1080.0
    minDepth: float = 0.0
    maxDepth: float = 1.0
    enabled: bool = True


@dataclass
class Scissor:
    x: int = 0
    y: int = 0
    width: int = 1920
    height: int = 1080
    enabled: bool = True


@dataclass
class BlendEquation:
    source: str = "One"
    destination: str = "Zero"
    operation: str = "Add"


@dataclass
class ColorBlend:
    enabled: bool = False
    colorBlend: BlendEquation = field(default_factory=BlendEquation)
    alphaBlend: BlendEquation = field(default_factory=BlendEquation)
    logicOperationEnabled: bool = False
    logicOperation: str = "NoOp"
    writeMask: int = 0xF


@dataclass
class StencilFace:
    failOperation: str = "Keep"
    depthFailOperation: str = "Keep"
    passOperation: str = "Keep"
    function: str = "AlwaysTrue"
    reference: int = 0
    compareMask: int = 0xFF
    writeMask: int = 0xFF


@dataclass
class BoundVBuffer:
    resourceId: ResourceId = field(default_factory=ResourceId)
    byteOffset: int = 0
    byteSize: int = 0
    byteStride: int = 0


@dataclass
class VertexInputAttribute:
    name: str = ""
    vertexBuffer: int = 0
    byteOffset: int = 0
    perInstance: bool = False
    instanceRate: int = 0
    format: ResourceFormat = field(default_factory=ResourceFormat)
    genericEnabled: bool = False
    used: bool = True


@dataclass
class SamplerData:
    addressU: str = "Wrap"
    addressV: str = "Wrap"
    addressW: str = "Wrap"
    borderColor: FloatVector = field(default_factory=FloatVector)
    compareFunction: str = ""
    filter: str = "Linear"
    maxAnisotropy: int = 1
    maxLOD: float = 1000.0
    minLOD: float = 0.0
    mipBias: float = 0.0
    seamlessCubeMap: bool = False


@dataclass
class UsedSampler:
    """Mimics UsedDescriptor wrapping a SamplerDescriptor."""

    sampler: SamplerData = field(default_factory=SamplerData)


@dataclass
class MeshFormat:
    allowRestart: bool = False
    baseVertex: int = 0
    dispatchSize: tuple[int, int, int] = (0, 0, 0)
    farPlane: float = 1.0
    flipY: bool = False
    format: ResourceFormat = field(default_factory=ResourceFormat)
    indexByteOffset: int = 0
    indexByteSize: int = 0
    indexByteStride: int = 0
    indexResourceId: ResourceId = field(default_factory=ResourceId)
    instStepRate: int = 1
    instanced: bool = False
    meshColor: FloatVector = field(default_factory=FloatVector)
    meshletIndexOffset: int = 0
    meshletOffset: int = 0
    meshletSizes: tuple[int, int, int] = (0, 0, 0)
    nearPlane: float = 0.1
    numIndices: int = 0
    perPrimitiveOffset: int = 0
    perPrimitiveStride: int = 0
    restartIndex: int = 0xFFFFFFFF
    showAlpha: bool = False
    status: str = ""
    taskSizes: tuple[int, int, int] = (0, 0, 0)
    topology: str = "TriangleList"
    unproject: bool = False
    vertexByteOffset: int = 0
    vertexByteSize: int = 0
    vertexByteStride: int = 0
    vertexResourceId: ResourceId = field(default_factory=ResourceId)


@dataclass
class ShaderValue:
    """Mock for ShaderValue union (real API has f32v, u32v, s32v, f64v)."""

    f32v: list[float] = field(default_factory=lambda: [0.0] * 16)
    u32v: list[int] = field(default_factory=lambda: [0] * 16)
    s32v: list[int] = field(default_factory=lambda: [0] * 16)


@dataclass
class ShaderVariable:
    name: str = ""
    type: str = ""
    rows: int = 0
    columns: int = 0
    flags: int = 0
    value: Any = None
    members: list[ShaderVariable] = field(default_factory=list)


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
    fixedBindNumber: int = 0
    fixedBindSetOrSpace: int = 0
    bindArraySize: int = 1
    bufferBacked: bool = True
    compileConstants: bool = False
    inlineDataBytes: bool = False

    @property
    def bindPoint(self) -> int:
        return self.fixedBindNumber


@dataclass
class ShaderResource:
    name: str = ""
    fixedBindNumber: int = 0
    fixedBindSetOrSpace: int = 0
    descriptorType: int = 0
    bindArraySize: int = 1
    isTexture: bool = False
    isReadOnly: bool = True
    isInputAttachment: bool = False
    hasSampler: bool = False
    textureType: int = 0
    variableType: Any = None


@dataclass
class ShaderReflection:
    resourceId: ResourceId = field(default_factory=ResourceId)
    inputSignature: list[SigParameter] = field(default_factory=list)
    outputSignature: list[SigParameter] = field(default_factory=list)
    readOnlyResources: list[ShaderResource] = field(default_factory=list)
    readWriteResources: list[ShaderResource] = field(default_factory=list)
    constantBlocks: list[ConstantBlock] = field(default_factory=list)
    debugInfo: ShaderDebugInfo = field(default_factory=ShaderDebugInfo)
    samplers: list[Any] = field(default_factory=list)
    stage: ShaderStage = ShaderStage.Vertex
    encoding: int = 0
    entryPoint: str = "main"
    rawBytes: bytes = b""
    interfaces: list[Any] = field(default_factory=list)
    pointerTypes: list[Any] = field(default_factory=list)
    outputTopology: int = 0
    dispatchThreadsDimension: tuple[int, int, int] = (0, 0, 0)
    rayPayload: Any = None
    rayAttributes: Any = None
    taskPayload: Any = None


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

    def __init__(
        self,
        *,
        output_targets: list[Descriptor] | None = None,
        depth_target: Descriptor | None = None,
    ) -> None:
        self._shaders: dict[ShaderStage, ResourceId] = {}
        self._reflections: dict[ShaderStage, ShaderReflection | None] = {}
        self._entry_points: dict[ShaderStage, str] = {}
        self._output_targets: list[Descriptor] = output_targets or []
        self._depth_target: Descriptor = depth_target or Descriptor()
        self._viewport: Viewport = Viewport()
        self._scissor: Scissor = Scissor()
        self._color_blends: list[ColorBlend] = [ColorBlend()]
        self._stencil: tuple[StencilFace, StencilFace] = (StencilFace(), StencilFace())
        self._vertex_inputs: list[VertexInputAttribute] = []
        self._samplers: dict[ShaderStage, list[SamplerData]] = {}
        self._vbuffers: list[BoundVBuffer] = []
        self._ibuffer: BoundVBuffer = BoundVBuffer()
        self._cbuffer_descriptors: dict[tuple[int, int], Descriptor] = {}

    def GetShader(self, stage: ShaderStage) -> ResourceId:
        return self._shaders.get(stage, ResourceId.Null())

    def GetShaderReflection(self, stage: ShaderStage) -> ShaderReflection | None:
        return self._reflections.get(stage)

    def GetShaderEntryPoint(self, stage: ShaderStage) -> str:
        return self._entry_points.get(stage, "main")

    def GetOutputTargets(self) -> list[Descriptor]:
        return self._output_targets

    def GetDepthTarget(self) -> Descriptor:
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

    def GetColorBlends(self) -> list[ColorBlend]:
        return self._color_blends

    def GetStencilFaces(self) -> tuple[StencilFace, StencilFace]:
        return self._stencil

    def GetVertexInputs(self) -> list[VertexInputAttribute]:
        return self._vertex_inputs

    def GetSamplers(self, stage: ShaderStage, only_used: bool = True) -> list[UsedSampler]:
        return [UsedSampler(sampler=s) for s in self._samplers.get(stage, [])]

    def GetVBuffers(self) -> list[BoundVBuffer]:
        return self._vbuffers

    def GetIBuffer(self) -> BoundVBuffer:
        return self._ibuffer

    def GetConstantBlock(
        self,
        stage: int,
        slot: int,
        array_idx: int,
    ) -> Descriptor:
        """Mock GetConstantBlock — returns descriptor with cbuffer resource."""
        return self._cbuffer_descriptors.get((stage, slot), Descriptor())

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
        self._textures: list[TextureDescription] = []
        self._buffers: list[BufferDescription] = []
        self._api_props: APIProperties = APIProperties()
        self._pipe_state: MockPipeState = MockPipeState()
        self._current_eid: int = 0
        self._set_frame_event_calls: list[tuple[int, bool]] = []
        self._shutdown_called: bool = False
        self._structured_file: StructuredFile = StructuredFile()
        self._debug_messages: list[DebugMessage] = []
        self._cbuffer_variables: dict[tuple[int, int], list[ShaderVariable]] = {}
        self._disasm_text: dict[int, str] = {}

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

    def GetTextures(self) -> list[TextureDescription]:
        return self._textures

    def GetBuffers(self) -> list[BufferDescription]:
        return self._buffers

    def GetDebugMessages(self) -> list[DebugMessage]:
        return self._debug_messages

    def SaveTexture(self, texsave: Any, path: str) -> bool:
        """Mock SaveTexture -- writes dummy PNG-like bytes to path."""
        assert hasattr(texsave, "resourceId"), "texsave must have resourceId"
        Path(path).write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        return True

    def GetTextureData(self, resource_id: Any, sub: Any) -> bytes:
        """Mock GetTextureData -- returns dummy raw bytes."""
        return b"\x00\xff" * 512

    def GetBufferData(self, resource_id: Any, offset: int, length: int) -> bytes:
        """Mock GetBufferData -- returns dummy buffer bytes."""
        return b"\xab\xcd" * 256

    def GetCBufferVariableContents(
        self,
        pipeline: Any,
        shader: Any,
        stage: Any,
        entry: str,
        idx: int,
        resource: Any,
        offset: int,
        size: int,
    ) -> list[ShaderVariable]:
        """Mock GetCBufferVariableContents."""
        return self._cbuffer_variables.get((int(stage), idx), [])

    def GetPostVSData(self, instance: int, view: int, stage: Any) -> MeshFormat:
        """Mock GetPostVSData -- returns dummy mesh format."""
        return MeshFormat()

    def GetDisassemblyTargets(self, with_pipeline: bool) -> list[str]:
        """Mock GetDisassemblyTargets -- returns default target list."""
        return ["SPIR-V"]

    def DisassembleShader(self, pipeline: Any, refl: Any, target: str) -> str:
        """Mock DisassembleShader -- returns cached disasm text by shader id."""
        rid = int(getattr(refl, "resourceId", 0))
        return self._disasm_text.get(rid, "")

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
    return "v1.41"


def GetCommitHash() -> str:
    return "abc123"


class ReplayOptions:
    pass
