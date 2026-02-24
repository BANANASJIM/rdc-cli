"""Mock renderdoc module for testing without GPU.

Provides fake implementations of RenderDoc Python API objects sufficient
for testing daemon replay lifecycle, action tree traversal, pipeline state
queries, and structured data access.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, IntFlag
from pathlib import Path
from typing import Any, ClassVar

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


class DescriptorType(IntEnum):
    Unknown = 0
    ConstantBuffer = 1
    Sampler = 2
    ImageSampler = 3
    Image = 4
    Buffer = 5
    TypedBuffer = 6
    ReadWriteImage = 7
    ReadWriteTypedBuffer = 8
    ReadWriteBuffer = 9
    AccelerationStructure = 10


class AddressMode(IntEnum):
    Wrap = 0
    Mirror = 1
    MirrorOnce = 2
    ClampEdge = 3
    ClampBorder = 4


class FilterMode(IntEnum):
    NoFilter = 0
    Point = 1
    Linear = 2
    Cubic = 3
    Anisotropic = 4


class CompareFunction(IntEnum):
    Never = 0
    AlwaysTrue = 1
    Less = 2
    LessEqual = 3
    Greater = 4
    GreaterEqual = 5
    Equal = 6
    NotEqual = 7


class ChromaSampleLocation(IntEnum):
    CositedEven = 0
    Midpoint = 1


class YcbcrConversion(IntEnum):
    Raw = 0
    RangeOnly = 1
    BT709 = 2
    BT601 = 3
    BT2020 = 4


class YcbcrRange(IntEnum):
    ITUFull = 0
    ITUNarrow = 1


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


class ResourceUsage(IntEnum):
    Unused = 0
    VertexBuffer = 1
    IndexBuffer = 2
    VS_Constants = 3
    HS_Constants = 4
    DS_Constants = 5
    GS_Constants = 6
    PS_Constants = 7
    CS_Constants = 8
    TS_Constants = 9
    MS_Constants = 10
    All_Constants = 11
    StreamOut = 12
    VS_Resource = 13
    HS_Resource = 14
    DS_Resource = 15
    GS_Resource = 16
    PS_Resource = 17
    CS_Resource = 18
    TS_Resource = 19
    MS_Resource = 20
    All_Resource = 21
    VS_RWResource = 22
    HS_RWResource = 23
    DS_RWResource = 24
    GS_RWResource = 25
    PS_RWResource = 26
    CS_RWResource = 27
    TS_RWResource = 28
    MS_RWResource = 29
    All_RWResource = 30
    InputTarget = 31
    ColorTarget = 32
    DepthStencilTarget = 33
    Indirect = 34
    Clear = 35
    Discard = 36
    GenMips = 37
    Resolve = 38
    ResolveSrc = 39
    ResolveDst = 40
    Copy = 41
    CopySrc = 42
    CopyDst = 43
    Barrier = 44
    CPUWrite = 45


@dataclass
class EventUsage:
    eventId: int = 0
    usage: ResourceUsage = ResourceUsage.Unused
    view: int = 0


class GPUCounter(IntEnum):
    EventGPUDuration = 1
    InputVerticesRead = 2
    IAPrimitives = 3
    GSPrimitives = 4
    RasterizerInvocations = 5
    RasterizedPrimitives = 6
    SamplesPassed = 7
    VSInvocations = 8
    HSInvocations = 9
    DSInvocations = 10
    GSInvocations = 11
    PSInvocations = 12
    CSInvocations = 13
    ASInvocations = 14
    MSInvocations = 15
    Count = 16
    FirstAMD = 1000000
    FirstIntel = 2000000
    LastAMD = 1999999
    FirstNvidia = 3000000
    LastIntel = 2999999
    FirstVulkanExtended = 4000000
    LastNvidia = 3999999
    FirstARM = 5000000
    LastVulkanExtended = 4999999
    LastARM = 6000000


class CounterUnit(IntEnum):
    Absolute = 0
    Seconds = 1
    Percentage = 2
    Ratio = 3
    Bytes = 4
    Cycles = 5
    Hertz = 6
    Volt = 7
    Celsius = 8


class CompType(IntEnum):
    Typeless = 0
    Float = 1
    UNorm = 2
    SNorm = 3
    UInt = 4
    SInt = 5
    UScaled = 6
    SScaled = 7
    Depth = 8
    UNormSRGB = 9


class MeshDataStage(IntEnum):
    VSIn = 0
    VSOut = 1
    GSOut = 2


class ShaderEncoding(IntEnum):
    Unknown = 0
    DXBC = 1
    GLSL = 2
    SPIRV = 3
    SPIRVAsm = 4  # noqa: E702
    HLSL = 5
    DXIL = 6
    OpenGLSPIRV = 7
    OpenGLSPIRVAsm = 8
    Slang = 9  # noqa: E702


class DebugOverlay(IntEnum):
    NoOverlay = 0
    Drawcall = 1
    Wireframe = 2
    Depth = 3
    Stencil = 4
    BackfaceCull = 5
    ViewportScissor = 6
    NaN = 7
    Clipping = 8
    ClearBeforePass = 9
    ClearBeforeDraw = 10
    QuadOverdrawPass = 11
    QuadOverdrawDraw = 12
    TriangleSizePass = 13
    TriangleSizeDraw = 14


class ReplayOutputType(IntEnum):
    Texture = 1
    Mesh = 2


class ShaderEvents(IntFlag):
    NoEvent = 0
    SampleLoadGather = 1
    GeneratedNanOrInf = 2


class TargetControlMessageType(IntEnum):
    Unknown = 0
    Disconnected = 1
    Busy = 2
    Noop = 3
    NewCapture = 4
    CaptureCopied = 5
    RegisterAPI = 6
    NewChild = 7
    CaptureProgress = 8
    CapturableWindowCount = 9
    RequestShow = 10


class SectionType(IntEnum):
    Unknown = 0
    FrameCapture = 1
    ResolveDatabase = 2
    Bookmarks = 3
    Notes = 4
    ResourceRenames = 5
    AMDRGPProfile = 6
    ExtendedThumbnail = 7


class SectionFlags(IntFlag):
    NoFlags = 0
    ASCIIStored = 1
    LZ4Compressed = 2
    ZstdCompressed = 4


@dataclass
class CounterValue:
    d: float = 0.0
    f: float = 0.0
    u32: int = 0
    u64: int = 0


@dataclass
class CounterDescription:
    name: str = ""
    category: str = ""
    description: str = ""
    counter: GPUCounter = GPUCounter.EventGPUDuration
    resultByteWidth: int = 8
    resultType: CompType = CompType.Float
    unit: CounterUnit = CounterUnit.Absolute
    uuid: str = ""


@dataclass
class CounterResult:
    eventId: int = 0
    counter: GPUCounter = GPUCounter.EventGPUDuration
    value: CounterValue = field(default_factory=CounterValue)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ResourceId:
    _id: int = 0

    def __int__(self) -> int:
        return self._id

    def __eq__(self, other: object) -> bool:
        if isinstance(other, ResourceId):
            return self._id == other._id
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._id)

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
class TextureDisplay:
    resourceId: Any = None
    overlay: Any = None
    rangeMin: float = 0.0
    rangeMax: float = 1.0
    scale: float = 1.0
    red: bool = True
    green: bool = True
    blue: bool = True
    alpha: bool = False
    flipY: bool = False
    hdrMultiplier: float = -1.0
    subresource: Any = None

    def __post_init__(self) -> None:
        if self.resourceId is None:
            self.resourceId = ResourceId(0)


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


class FillMode:
    """Stub for fill mode enum with .name attribute."""

    def __init__(self, name: str = "Solid") -> None:
        self.name = name


class CullMode:
    """Stub for cull mode enum with .name attribute."""

    def __init__(self, name: str = "None") -> None:
        self.name = name


class CompFunc:
    """Stub for comparison function enum with .name attribute."""

    def __init__(self, name: str = "LessEqual") -> None:
        self.name = name


@dataclass
class RasterizerState:
    fillMode: FillMode | None = None
    cullMode: CullMode | None = None
    frontCCW: bool | None = None
    depthBiasEnable: bool | None = None
    depthBiasConstantFactor: float | None = None
    depthBiasClamp: float | None = None
    depthBiasSlopeFactor: float | None = None
    lineWidth: float | None = None


@dataclass
class DepthStencilState:
    depthTestEnable: bool | None = None
    depthWriteEnable: bool | None = None
    depthFunction: CompFunc | None = None
    depthBoundsEnable: bool | None = None
    minDepthBounds: float | None = None
    maxDepthBounds: float | None = None
    stencilTestEnable: bool | None = None


@dataclass
class MultisampleState:
    rasterSamples: int = 1
    sampleShadingEnable: bool = False
    minSampleShading: float = 0.0
    sampleMask: int = 0xFFFFFFFF


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
class PixelValue:
    """Stub for PixelValue (SWIG opaque type)."""

    floatValue: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])


@dataclass
class ModificationValue:
    """Mock for ModificationValue in PixelModification."""

    col: PixelValue = field(default_factory=PixelValue)
    depth: float = -1.0
    stencil: int = -1

    def IsValid(self) -> bool:
        return True


@dataclass
class PixelModification:
    """Mock for PixelModification from PixelHistory."""

    eventId: int = 0
    fragIndex: int = 0
    primitiveID: int = 0
    preMod: ModificationValue = field(default_factory=ModificationValue)
    shaderOut: ModificationValue = field(default_factory=ModificationValue)
    postMod: ModificationValue = field(default_factory=ModificationValue)
    directShaderWrite: bool = False
    unboundPS: bool = False
    sampleMasked: bool = False
    backfaceCulled: bool = False
    depthClipped: bool = False
    scissorClipped: bool = False
    shaderDiscarded: bool = False
    depthTestFailed: bool = False
    stencilTestFailed: bool = False
    depthBoundsFailed: bool = False
    predicationSkipped: bool = False
    viewClipped: bool = False

    def Passed(self) -> bool:
        return not any(
            [
                self.sampleMasked,
                self.backfaceCulled,
                self.depthClipped,
                self.scissorClipped,
                self.shaderDiscarded,
                self.depthTestFailed,
                self.stencilTestFailed,
                self.depthBoundsFailed,
                self.predicationSkipped,
                self.viewClipped,
            ]
        )


@dataclass
class TextureFilter:
    """Stub for TextureFilter (SWIG opaque type)."""

    minify: FilterMode = FilterMode.Linear
    magnify: FilterMode = FilterMode.Linear
    mip: FilterMode = FilterMode.Linear


@dataclass
class SamplerDescriptor:
    """Mock for SamplerDescriptor from GetAllUsedDescriptors."""

    addressU: AddressMode = AddressMode.Wrap
    addressV: AddressMode = AddressMode.Wrap
    addressW: AddressMode = AddressMode.Wrap
    borderColorType: CompType = CompType.Float
    borderColorValue: PixelValue = field(default_factory=PixelValue)
    chromaFilter: FilterMode = FilterMode.NoFilter
    compareFunction: CompareFunction = CompareFunction.AlwaysTrue
    creationTimeConstant: bool = False
    filter: TextureFilter = field(default_factory=TextureFilter)
    forceExplicitReconstruction: bool = False
    maxAnisotropy: float = 0.0
    maxLOD: float = 0.0
    minLOD: float = 0.0
    mipBias: float = 0.0
    object: ResourceId = field(default_factory=ResourceId)
    seamlessCubemaps: bool = True
    srgbBorder: bool = False
    swizzle: TextureSwizzle4 = field(default_factory=TextureSwizzle4)
    type: DescriptorType = DescriptorType.Unknown
    unnormalized: bool = False
    xChromaOffset: ChromaSampleLocation = ChromaSampleLocation.CositedEven
    yChromaOffset: ChromaSampleLocation = ChromaSampleLocation.CositedEven
    ycbcrModel: YcbcrConversion = YcbcrConversion.Raw
    ycbcrRange: YcbcrRange = YcbcrRange.ITUFull
    ycbcrSampler: ResourceId = field(default_factory=ResourceId)


@dataclass
class DescriptorAccess:
    """Mock for DescriptorAccess from GetAllUsedDescriptors."""

    NoShaderBinding: ClassVar[int] = 65535
    stage: ShaderStage = ShaderStage.Vertex
    type: DescriptorType = DescriptorType.ConstantBuffer
    index: int = 0
    arrayElement: int = 0
    descriptorStore: ResourceId = field(default_factory=ResourceId)
    byteOffset: int = 0
    byteSize: int = 0
    staticallyUnused: bool = False


@dataclass
class UsedDescriptor:
    """Mock for UsedDescriptor from GetAllUsedDescriptors."""

    access: DescriptorAccess = field(default_factory=DescriptorAccess)
    descriptor: Descriptor = field(default_factory=Descriptor)
    sampler: SamplerDescriptor = field(default_factory=SamplerDescriptor)


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
    pushConstantRangeByteOffset: int = 0
    pushConstantRangeByteSize: int = 0


@dataclass
class DebugPixelInputs:
    sample: int = 0xFFFFFFFF
    primitive: int = 0xFFFFFFFF
    view: int = 0xFFFFFFFF


@dataclass
class ShaderCompileFlags:
    flags: list[Any] = field(default_factory=list)


@dataclass
class LineColumnInfo:
    fileIndex: int = 0
    lineStart: int = 0
    lineEnd: int = 0
    colStart: int = 0
    colEnd: int = 0


@dataclass
class InstructionSourceInfo:
    instruction: int = 0
    lineInfo: LineColumnInfo = field(default_factory=LineColumnInfo)


@dataclass
class SourceVariableMapping:
    name: str = ""
    type: int = 0
    rows: int = 0
    columns: int = 0
    offset: int = 0
    signatureIndex: int = -1
    variables: list[Any] = field(default_factory=list)


@dataclass
class ShaderVariableChange:
    before: ShaderVariable = field(default_factory=ShaderVariable)
    after: ShaderVariable = field(default_factory=ShaderVariable)


@dataclass
class ShaderDebugState:
    stepIndex: int = 0
    nextInstruction: int = 0
    flags: int = 0
    changes: list[ShaderVariableChange] = field(default_factory=list)
    callstack: list[str] = field(default_factory=lambda: ["main"])


@dataclass
class SourceFile:
    filename: str = ""
    contents: str = ""


@dataclass
class ShaderDebugTrace:
    debugger: Any = None
    stage: ShaderStage = ShaderStage.Pixel
    inputs: list[ShaderVariable] = field(default_factory=list)
    sourceVars: list[SourceVariableMapping] = field(default_factory=list)
    instInfo: list[InstructionSourceInfo] = field(default_factory=list)
    sourceFiles: list[SourceFile] = field(default_factory=list)
    constantBlocks: list[Any] = field(default_factory=list)
    readOnlyResources: list[Any] = field(default_factory=list)
    readWriteResources: list[Any] = field(default_factory=list)
    samplers: list[Any] = field(default_factory=list)


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

    def NumChildren(self) -> int:
        return len(self.children)

    def GetChild(self, index: int) -> SDObject:
        return self.children[index]

    def AsString(self) -> str:
        if self.data and self.data.basic and self.data.basic.value is not None:
            return str(self.data.basic.value)
        return ""

    def AsInt(self) -> int:
        if self.data and self.data.basic and self.data.basic.value is not None:
            return int(self.data.basic.value)
        return 0


@dataclass
class SDChunk:
    name: str = ""
    children: list[SDObject] = field(default_factory=list)

    def NumChildren(self) -> int:
        return len(self.children)

    def GetChild(self, index: int) -> SDObject:
        return self.children[index]


@dataclass
class StructuredFile:
    chunks: list[SDChunk] = field(default_factory=list)


@dataclass
class CaptureOptions:
    allowFullscreen: bool = False
    allowVSync: bool = False
    apiValidation: bool = False
    captureCallstacks: bool = False
    captureCallstacksOnlyActions: bool = False
    delayForDebugger: int = 0
    verifyBufferAccess: bool = False
    hookIntoChildren: bool = False
    refAllResources: bool = False
    captureAllCmdLists: bool = False
    debugOutputMute: bool = False
    softMemoryLimit: int = 0


@dataclass
class ExecuteResult:
    result: int = 0
    ident: int = 0


@dataclass
class Thumbnail:
    data: bytes = b""
    width: int = 0
    height: int = 0


@dataclass
class GPUDevice:
    name: str = ""
    vendor: int = 0
    deviceID: int = 0
    driver: str = ""


@dataclass
class SectionProperties:
    name: str = ""
    type: SectionType = SectionType.Unknown
    version: str = ""
    compressedSize: int = 0
    uncompressedSize: int = 0
    flags: SectionFlags = SectionFlags.NoFlags


@dataclass
class NewCaptureData:
    captureId: int = 0
    frameNumber: int = 0
    path: str = ""
    byteSize: int = 0
    timestamp: int = 0
    thumbnail: bytes = b""
    thumbWidth: int = 0
    thumbHeight: int = 0
    title: str = ""
    api: str = ""
    local: bool = True


@dataclass
class TargetControlMessage:
    type: TargetControlMessageType = TargetControlMessageType.Noop
    newCapture: NewCaptureData | None = None


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
        self._used_descriptors: list[UsedDescriptor] = []
        self.rasterizer: RasterizerState | None = None
        self.depthStencil: DepthStencilState | None = None
        self.multisample: MultisampleState = MultisampleState()

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

    def GetAllUsedDescriptors(self, only_used: bool = True) -> list[UsedDescriptor]:
        """Mock GetAllUsedDescriptors — returns configured used descriptors."""
        if only_used:
            return [d for d in self._used_descriptors if not d.access.staticallyUnused]
        return list(self._used_descriptors)

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
        self._usage_map: dict[int, list[EventUsage]] = {}
        self._counter_descriptions: dict[int, CounterDescription] = {}
        self._counter_results: list[CounterResult] = []
        self._pixel_history_map: dict[tuple[int, int], list[PixelModification]] = {}
        self._pick_pixel_map: dict[tuple[int, int], PixelValue] = {}
        self._debug_pixel_map: dict[tuple[int, int], ShaderDebugTrace] = {}
        self._debug_vertex_map: dict[int, ShaderDebugTrace] = {}
        self._debug_thread_map: dict[tuple[int, int, int, int, int, int], ShaderDebugTrace] = {}
        self._debug_states: dict[int, list[list[ShaderDebugState]]] = {}
        self._mesh_data: dict[int, MeshFormat] = {}
        self._min_max_map: dict[int, tuple[PixelValue, PixelValue]] = {}
        self._histogram_map: dict[tuple[int, int], list[int]] = {}
        self._target_encodings: list[int] = [3, 2]
        self._built_counter: int = 1000
        self._replacements: dict[int, int] = {}
        self._freed: set[int] = set()
        self._save_texture_fails: bool = False
        self._texture_data: dict[int, bytes] = {}
        self._buffer_data: dict[int, bytes] = {}
        self._raise_on_texture_id: set[int] = set()
        self._raise_on_buffer_id: set[int] = set()
        self._debug_step_index: dict[int, int] = {}
        self._freed_traces: set[int] = set()

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
        if self._save_texture_fails:
            return False
        Path(path).write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        return True

    def GetTextureData(self, resource_id: Any, sub: Any) -> bytes:
        """Mock GetTextureData -- returns per-resource or default bytes."""
        rid = int(resource_id)
        if rid in self._raise_on_texture_id:
            raise RuntimeError(f"simulated error for texture {rid}")
        return self._texture_data.get(rid, b"\x00\xff" * 512)

    def GetBufferData(self, resource_id: Any, offset: int, length: int) -> bytes:
        """Mock GetBufferData -- returns per-resource or default bytes with slicing."""
        rid = int(resource_id)
        if rid in self._raise_on_buffer_id:
            raise RuntimeError(f"simulated error for buffer {rid}")
        data = self._buffer_data.get(rid, b"\xab\xcd" * 256)
        return data[offset : offset + length] if length > 0 else data[offset:]

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
        """Mock GetPostVSData -- returns configured or empty mesh format."""
        return self._mesh_data.get(int(stage), MeshFormat())

    def GetDisassemblyTargets(self, with_pipeline: bool) -> list[str]:
        """Mock GetDisassemblyTargets -- returns default target list."""
        return ["SPIR-V"]

    def DisassembleShader(self, pipeline: Any, refl: Any, target: str) -> str:
        """Mock DisassembleShader -- returns cached disasm text by shader id."""
        rid = int(getattr(refl, "resourceId", 0))
        return self._disasm_text.get(rid, "")

    def GetUsage(self, resource_id: Any) -> list[EventUsage]:
        """Mock GetUsage -- returns event usage list for a resource."""
        rid = int(resource_id) if not isinstance(resource_id, int) else resource_id
        return self._usage_map.get(rid, [])

    def EnumerateCounters(self) -> list[Any]:
        """Mock EnumerateCounters -- returns counter ids from description keys.

        Uses GPUCounter enum when the value is a known member, otherwise returns raw int.
        This mirrors real API behaviour where vendor counters have non-standard ids.
        """
        result: list[Any] = []
        for k in self._counter_descriptions:
            try:
                result.append(GPUCounter(k))
            except ValueError:
                result.append(k)
        return result

    def DescribeCounter(self, counter_id: Any) -> CounterDescription:
        """Mock DescribeCounter -- returns CounterDescription by id."""
        return self._counter_descriptions.get(int(counter_id), CounterDescription())

    def FetchCounters(self, counter_ids: list[Any]) -> list[CounterResult]:
        """Mock FetchCounters -- returns results filtered by requested counter ids."""
        id_set = {int(c) for c in counter_ids}
        return [r for r in self._counter_results if int(r.counter) in id_set]

    def PixelHistory(
        self, texture: Any, x: int, y: int, sub: Any, type_cast: Any
    ) -> list[PixelModification]:
        """Mock PixelHistory -- returns modifications keyed by (x, y)."""
        return self._pixel_history_map.get((x, y), [])

    def PickPixel(self, texture: Any, x: int, y: int, sub: Any, comp_type: Any) -> PixelValue:
        """Mock PickPixel -- returns PixelValue keyed by (x, y)."""
        return self._pick_pixel_map.get((int(x), int(y)), PixelValue())

    def DebugPixel(self, x: int, y: int, inputs: Any) -> ShaderDebugTrace:
        return self._debug_pixel_map.get((x, y), ShaderDebugTrace())

    def DebugVertex(self, vtx: int, inst: int, idx: int, view: int) -> ShaderDebugTrace:
        return self._debug_vertex_map.get(vtx, ShaderDebugTrace())

    def DebugThread(
        self, group: tuple[int, int, int], thread: tuple[int, int, int]
    ) -> ShaderDebugTrace:
        return self._debug_thread_map.get((*group, *thread), ShaderDebugTrace())

    def ContinueDebug(self, debugger: Any) -> list[ShaderDebugState]:
        key = id(debugger)
        batches = self._debug_states.get(key, [])
        idx = self._debug_step_index.get(key, 0)
        if idx < len(batches):
            self._debug_step_index[key] = idx + 1
            return batches[idx]
        return []

    def FreeTrace(self, trace: Any) -> None:
        tid = id(trace)
        if tid in self._freed_traces:
            raise RuntimeError("double-free of trace")
        self._freed_traces.add(tid)

    def GetTargetShaderEncodings(self) -> list[int]:
        return list(self._target_encodings)

    def BuildTargetShader(
        self, entry: str, encoding: Any, source: bytes, flags: Any, stage: Any
    ) -> tuple[Any, str]:
        rid = self._built_counter
        self._built_counter += 1
        return (ResourceId(rid), "")

    def ReplaceResource(self, original: Any, replacement: Any) -> None:
        self._replacements[int(original)] = int(replacement)

    def RemoveReplacement(self, original: Any) -> None:
        self._replacements.pop(int(original), None)

    def FreeTargetResource(self, rid: Any) -> None:
        self._freed.add(int(rid))

    def GetMinMax(self, tex_id: Any, sub: Any, comp_type: Any) -> tuple[PixelValue, PixelValue]:
        rid = int(tex_id)
        return self._min_max_map.get(rid, (PixelValue(), PixelValue()))

    def GetHistogram(
        self, tex_id: Any, sub: Any, comp_type: Any, min_val: float, max_val: float, channels: Any
    ) -> list[int]:
        rid = int(tex_id)
        ch = next((i for i, c in enumerate(channels) if c), 0)
        return self._histogram_map.get((rid, ch), [0] * 256)

    def CreateOutput(self, windowing: Any, output_type: Any) -> MockReplayOutput:
        return MockReplayOutput()

    def Shutdown(self) -> None:
        self._shutdown_called = True


# ---------------------------------------------------------------------------
# Mock ReplayOutput
# ---------------------------------------------------------------------------


class MockReplayOutput:
    """Mock for renderdoc ReplayOutput."""

    def __init__(self) -> None:
        self._overlay_tex_id = ResourceId(900)

    def SetTextureDisplay(self, display: Any) -> None:
        pass

    def Display(self) -> None:
        pass

    def GetDebugOverlayTexID(self) -> ResourceId:
        return self._overlay_tex_id

    def ReadbackOutputTexture(self) -> bytes:
        return b"\x00" * (256 * 256 * 3)

    def Shutdown(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Mock TargetControl
# ---------------------------------------------------------------------------


class MockTargetControl:
    """Mock for renderdoc TargetControl."""

    def __init__(
        self,
        *,
        messages: list[TargetControlMessage] | None = None,
        copy_result: str = "",
        target: str = "mock-target",
        pid: int = 1234,
        api: str = "Vulkan",
    ) -> None:
        self._connected = True
        self._messages = list(messages) if messages else []
        self._msg_idx = 0
        self._copy_result = copy_result
        self._target = target
        self._pid = pid
        self._api = api
        self.shutdown_count: int = 0

    def Connected(self) -> bool:
        return self._connected

    def GetTarget(self) -> str:
        return self._target

    def GetPID(self) -> int:
        return self._pid

    def GetAPI(self) -> str:
        return self._api

    def TriggerCapture(self, numFrames: int = 1) -> None:
        pass

    def QueueCapture(self, frameNumber: int, numFrames: int = 1) -> None:
        pass

    def CopyCapture(self, captureId: int, localpath: str) -> str:
        return self._copy_result or localpath

    def DeleteCapture(self, captureId: int) -> None:
        pass

    def ReceiveMessage(self, progress: Any = None) -> TargetControlMessage:
        if self._msg_idx < len(self._messages):
            msg = self._messages[self._msg_idx]
            self._msg_idx += 1
            return msg
        return TargetControlMessage(type=TargetControlMessageType.Noop)

    def CycleActiveWindow(self) -> None:
        pass

    def Shutdown(self) -> None:
        self.shutdown_count += 1
        self._connected = False


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

    def GetThumbnail(self, fileType: int = 0, maxsize: int = 0) -> Thumbnail:
        return Thumbnail(data=b"\x00" * 16, width=4, height=4)

    def GetAvailableGPUs(self) -> list[GPUDevice]:
        return [GPUDevice(name="Mock GPU", vendor=0, deviceID=0, driver="0.0")]

    def GetSectionCount(self) -> int:
        return 1

    def GetSectionProperties(self, idx: int) -> SectionProperties:
        return SectionProperties(name="FrameCapture", type=SectionType.FrameCapture)

    def GetSectionContents(self, idx: int) -> bytes:
        return b"mock-section-data"

    def FindSectionByName(self, name: str) -> int:
        return 0 if name == "FrameCapture" else -1

    def HasCallstacks(self) -> bool:
        return False

    def RecordedMachineIdent(self) -> str:
        return "mock-machine-ident"

    def TimestampBase(self) -> int:
        return 0

    def HasPendingDependencies(self) -> bool:
        return False

    def EmbedDependenciesIntoCapture(self) -> None:
        pass

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


def CreateHeadlessWindowingData(width: int, height: int) -> Any:
    from types import SimpleNamespace

    return SimpleNamespace(width=width, height=height)


class ReplayOptions:
    pass


def ExecuteAndInject(
    app: str,
    workingDir: str,
    cmdLine: str,
    envList: list[str],
    capturefile: str,
    opts: CaptureOptions,
    waitForExit: bool = False,
) -> ExecuteResult:
    return ExecuteResult(result=0, ident=12345)


def CreateTargetControl(
    URL: str,
    ident: int,
    clientName: str,
    forceConnection: bool,
) -> MockTargetControl:
    return MockTargetControl()


def GetDefaultCaptureOptions() -> CaptureOptions:
    opts = CaptureOptions()
    opts.allowFullscreen = True
    opts.allowVSync = True
    opts.debugOutputMute = True
    return opts
