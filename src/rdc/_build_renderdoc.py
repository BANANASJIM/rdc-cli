#!/usr/bin/env python3
"""Cross-platform RenderDoc Python bindings build script.

Replaces build-renderdoc.sh and setup-renderdoc.sh.
Standalone -- requires only Python 3.10+ stdlib. `pixi run setup-renderdoc`
invokes this script and installs the required macOS build toolchain (cmake,
ninja, autoconf/automake/libtool, pkg-config, m4) automatically.

Recommended invocation (requires pixi)::

    pixi run setup-renderdoc

Direct usage::

    python scripts/build_renderdoc.py [INSTALL_DIR] [--build-dir DIR] [--jobs N]
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import stat
import struct
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path
from urllib.request import urlretrieve

RDOC_TAG = "v1.41"
RDOC_REPO = "https://github.com/baldurk/renderdoc.git"
SWIG_URL = "https://github.com/baldurk/swig/archive/renderdoc-modified-7.zip"
SWIG_SHA256 = "9d7e5013ada6c42ec95ab167a34db52c1cc8c09b89c8e9373631b1f10596c648"
SWIG_SUBDIR = "swig-renderdoc-modified-7"

CMAKE_COMMON_FLAGS = [
    "-DCMAKE_BUILD_TYPE=Release",
    "-DENABLE_PYRENDERDOC=ON",
    "-DENABLE_QRENDERDOC=OFF",
    "-DENABLE_RENDERDOCCMD=OFF",
    "-DENABLE_GL=OFF",
    "-DENABLE_GLES=OFF",
    "-DENABLE_VULKAN=ON",
]


def _log(msg: str) -> None:
    sys.stdout.write(msg + "\n")
    sys.stdout.flush()


def _platform() -> str:
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "linux"


def default_install_dir() -> Path:
    """Default renderdoc artifact directory."""
    if _platform() == "windows":
        base = os.environ.get("LOCALAPPDATA", str(Path.home()))
        return Path(base) / "rdc" / "renderdoc"
    return Path.home() / ".local" / "renderdoc"


_OPTIONAL_ARTIFACTS = frozenset({"renderdoccmd.exe"})


def _artifact_names(plat: str) -> list[str]:
    if plat == "windows":
        return ["renderdoc.pyd", "renderdoc.dll", "renderdoccmd.exe"]
    return ["renderdoc.so", "librenderdoc.so"]


def _artifact_src_dir(build_dir: Path, plat: str) -> Path:
    if plat == "windows":
        return build_dir / "renderdoc" / "x64" / "Release" / "pymodules"
    return build_dir / "renderdoc" / "build" / "lib"


def check_prerequisites(plat: str) -> None:
    """Verify required build tools are available."""
    if plat == "windows":
        required = ["git"]
    elif plat == "macos":
        required = [
            "cmake",
            "git",
            "ninja",
            "autoconf",
            "automake",
            "libtool",
            "pkg-config",
            "m4",
        ]
    else:
        required = ["cmake", "git", "ninja"]

    missing = [cmd for cmd in required if shutil.which(cmd) is None]

    # Check python3 or python
    if shutil.which("python3") is None and shutil.which("python") is None:
        missing.append("python3")

    if missing:
        hint = "Run `pixi run sync` to install the pinned toolchain."
        sys.stderr.write(f"ERROR: missing required tools: {', '.join(missing)}\n{hint}\n")
        raise SystemExit(1)

    if plat == "windows":
        _check_visual_studio()


def verify_tool_versions(plat: str) -> None:
    """Run lightweight --version checks to fail fast when tools are broken."""
    if plat == "windows":
        return
    tools = ["cmake", "ninja"]
    for tool in tools:
        if shutil.which(tool) is None:
            sys.stderr.write(f"ERROR: required tool '{tool}' not found in PATH\n")
            raise SystemExit(1)
        subprocess.run(
            [tool, "--version"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def _find_vswhere() -> str:
    """Locate vswhere.exe on Windows."""
    vswhere = shutil.which("vswhere") or shutil.which("vswhere.exe")
    if not vswhere:
        prog = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
        candidate = prog / "Microsoft Visual Studio" / "Installer" / "vswhere.exe"
        if candidate.exists():
            vswhere = str(candidate)
        else:
            sys.stderr.write("ERROR: vswhere.exe not found; install Visual Studio Build Tools\n")
            raise SystemExit(1)
    return vswhere


def _vs_install_path() -> str:
    """Return Visual Studio installation path via vswhere."""
    vswhere = _find_vswhere()
    result = subprocess.run(
        [
            vswhere,
            "-products",
            "*",
            "-requires",
            "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
            "-format",
            "value",
            "-property",
            "installationPath",
        ],
        capture_output=True,
        text=True,
    )
    path = result.stdout.strip()
    if not path:
        sys.stderr.write("ERROR: Visual Studio C++ Build Tools not found\n")
        raise SystemExit(1)
    return path.splitlines()[0]


def _check_visual_studio() -> None:
    _vs_install_path()


def _find_msbuild() -> str:
    """Locate MSBuild.exe via vswhere."""
    vs_path = _vs_install_path()
    msbuild = Path(vs_path) / "MSBuild" / "Current" / "Bin" / "MSBuild.exe"
    if not msbuild.exists():
        sys.stderr.write(f"ERROR: MSBuild.exe not found at {msbuild}\n")
        raise SystemExit(1)
    return str(msbuild)


def _prepare_win_python(src_dir: Path) -> Path:
    """Prepare Python prefix for MSBuild and return the prefix path.

    RenderDoc's python.props checks for:
    - {prefix}/include/Python.h  (pixi has Include/Python.h -- case-insensitive on Windows, OK)
    - {prefix}/python{ver}.zip   (dummy file, content irrelevant)
    - {prefix}/libs/python{ver}.lib

    Also patches python.props to add current Python version entry if missing.
    """
    # Use base_prefix to find headers/libs (sys.prefix is a venv for uv tool installs)
    prefix = Path(sys.base_prefix)
    ver = f"{sys.version_info[0]}{sys.version_info[1]}"

    # Create dummy python{ver}.zip if missing
    dummy_zip = prefix / f"python{ver}.zip"
    if not dummy_zip.exists():
        _log(f"creating dummy {dummy_zip}")
        with zipfile.ZipFile(dummy_zip, "w") as zf:
            zf.writestr("README", "dummy zip for RenderDoc build")

    # Verify required files
    include = prefix / "include" / "Python.h"
    if not include.exists():
        # Case-insensitive fallback (pixi uses Include/)
        alt = prefix / "Include" / "Python.h"
        if not alt.exists():
            sys.stderr.write(f"ERROR: Python.h not found at {include} or {alt}\n")
            raise SystemExit(1)

    lib = prefix / "libs" / f"python{ver}.lib"
    if not lib.exists():
        sys.stderr.write(f"ERROR: {lib} not found\n")
        raise SystemExit(1)

    # Patch python.props to include current Python version
    props_file = src_dir / "qrenderdoc" / "Code" / "pyrenderdoc" / "python.props"
    if props_file.exists():
        content = props_file.read_text(encoding="utf-8")
        if ver not in content:
            _log(f"patching python.props for Python {ver}")
            entry = (
                f"<PropertyGroup><PythonMajorMinorTest>{ver}</PythonMajorMinorTest></PropertyGroup>\n"
                f"<PropertyGroup Condition=\"'$(CustomPythonUsed)'=='0' AND "
                f"Exists('$(PythonOverride)\\include\\Python.h') AND "
                f"Exists('$(PythonOverride)\\python$(PythonMajorMinorTest).zip') AND "
                f"(Exists('$(PythonOverride)\\python$(PythonMajorMinorTest).lib') OR "
                f"Exists('$(PythonOverride)\\libs\\python$(PythonMajorMinorTest).lib'))\">"
                f"<CustomPythonUsed>$(PythonMajorMinorTest)</CustomPythonUsed></PropertyGroup>\n"
            )
            # Insert before the "313" entry
            marker = "<PythonMajorMinorTest>313</PythonMajorMinorTest>"
            if marker in content:
                idx = content.index(marker)
                # Find the start of the PropertyGroup containing the marker
                pg_start = content.rfind("<PropertyGroup>", 0, idx)
                assert pg_start != -1, f"No <PropertyGroup> before marker in {props_file}"
                content = content[:pg_start] + entry + content[pg_start:]
            else:
                # Fallback: insert before closing </Project>
                content = content.replace("</Project>", entry + "</Project>")
            props_file.write_text(content, encoding="utf-8")

    return prefix


def _run_msbuild(build_dir: Path, python_prefix: Path, jobs: int | None = None) -> None:
    """Build renderdoc.sln with MSBuild."""
    sln = build_dir / "renderdoc" / "renderdoc.sln"
    msbuild = _find_msbuild()
    n = jobs or os.cpu_count() or 4
    env = dict(os.environ)
    env["RENDERDOC_PYTHON_PREFIX64"] = str(python_prefix)
    env["CL"] = (env.get("CL", "") + " /wd4996").strip()
    cmd = [
        msbuild,
        str(sln),
        "/p:Configuration=Release",
        "/p:Platform=x64",
        "/p:PlatformToolset=v143",
        f"/m:{n}",
    ]
    _log("--- MSBuild ---")
    subprocess.run(cmd, check=True, env=env)


def clone_renderdoc(build_dir: Path, version: str = RDOC_TAG) -> None:
    """Clone renderdoc source (idempotent)."""
    src_dir = build_dir / "renderdoc"
    if src_dir.exists():
        _log(f"renderdoc source already exists at {src_dir}")
        return
    _log(f"--- Cloning renderdoc {version} ---")
    build_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "clone", "--depth", "1", "--branch", version, RDOC_REPO, str(src_dir)],
        check=True,
    )


def _safe_extractall(zf: zipfile.ZipFile, dest: Path) -> None:
    """Extract zip archive while rejecting members that would escape dest (zip-slip mitigation)."""
    dest_resolved = dest.resolve()
    for member in zf.infolist():
        target = (dest / member.filename).resolve()
        if not target.is_relative_to(dest_resolved):
            sys.stderr.write(f"ERROR: zip-slip attempt detected: {member.filename}\n")
            raise SystemExit(1)
        zf.extract(member, dest)
        # Restore Unix execute bits that zipfile.extract() drops.
        unix_mode = member.external_attr >> 16
        if unix_mode and (unix_mode & 0o111):
            target.chmod(target.stat().st_mode | (unix_mode & 0o111))


def download_swig(build_dir: Path) -> None:
    """Download and extract the RenderDoc SWIG fork (idempotent)."""
    swig_dir = build_dir / "renderdoc-swig"
    if swig_dir.exists():
        _log(f"SWIG fork already exists at {swig_dir}")
        return

    build_dir.mkdir(parents=True, exist_ok=True)
    archive = build_dir / "swig.zip"

    _log("--- Downloading SWIG fork ---")
    urlretrieve(SWIG_URL, str(archive))

    # SHA256 verification
    sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    if sha != SWIG_SHA256:
        archive.unlink()
        sys.stderr.write(f"ERROR: SWIG archive SHA256 mismatch: {sha}\n")
        raise SystemExit(1)

    try:
        with zipfile.ZipFile(archive) as zf:
            _safe_extractall(zf, build_dir)
        (build_dir / SWIG_SUBDIR).rename(swig_dir)
    except Exception:
        # Clean up partial extraction so next run retries cleanly
        shutil.rmtree(build_dir / SWIG_SUBDIR, ignore_errors=True)
        shutil.rmtree(swig_dir, ignore_errors=True)
        raise
    finally:
        archive.unlink(missing_ok=True)


def _ensure_executable(path: Path) -> None:
    try:
        mode = path.stat().st_mode
    except FileNotFoundError:
        return
    new_mode = mode
    for bit in (stat.S_IXUSR, stat.S_IXGRP, stat.S_IXOTH):
        if not mode & bit:
            new_mode |= bit
    if new_mode != mode:
        path.chmod(new_mode)


def prepare_custom_swig(swig_dir: Path) -> None:
    """Ensure custom SWIG tree is bootstrapped before cmake configure."""
    custom = swig_dir / "custom_swig"
    if not custom.is_dir():
        # Older RenderDoc SWIG zips ship the patched sources at the root.
        return
    autogen = custom / "autogen.sh"
    if autogen.exists():
        _ensure_executable(autogen)
    subprocess.run(["autoreconf", "-fi"], cwd=custom, check=True)


def strip_lto(env: dict[str, str]) -> dict[str, str]:
    """Remove -flto=auto from compiler/linker flags (unconditional on Linux)."""
    env = dict(env)
    for key in ("CFLAGS", "CXXFLAGS", "LDFLAGS"):
        if key in env:
            env[key] = env[key].replace("-flto=auto", "").strip()
    return env


def configure_build(
    build_dir: Path,
    swig_dir: Path,
    plat: str,
) -> None:
    """Run cmake configure (Linux/macOS only)."""
    src_dir = build_dir / "renderdoc"
    cmake_build = src_dir / "build"

    cmd = ["cmake", "-B", str(cmake_build), "-S", str(src_dir), "-G", "Ninja"]
    cmd += CMAKE_COMMON_FLAGS
    cmd.append(f"-DRENDERDOC_SWIG_PACKAGE={swig_dir}")

    # Use base_prefix Python so cmake finds python3.XX-config (venv lacks it)
    base_python = Path(sys.base_prefix) / "bin" / Path(sys.executable).name
    if base_python.exists():
        cmd.append(f"-DPython3_EXECUTABLE={base_python}")
    else:
        _log(f"WARNING: base Python not found at {base_python}, cmake will auto-detect")

    env = dict(os.environ)
    if plat == "linux":
        _log("stripping LTO flags")
        env = strip_lto(env)

    _log("--- cmake configure ---")
    subprocess.run(cmd, check=True, env=env)


def run_build(build_dir: Path, jobs: int | None = None) -> None:
    """Run cmake --build (Linux/macOS only)."""
    cmake_build = build_dir / "renderdoc" / "build"
    n = jobs or os.cpu_count() or 4
    cmd = ["cmake", "--build", str(cmake_build), "-j", str(n)]
    _log("--- cmake build ---")
    subprocess.run(cmd, check=True)


def copy_artifacts(build_dir: Path, install_dir: Path, plat: str) -> None:
    """Copy built artifacts to install directory."""
    src = _artifact_src_dir(build_dir, plat)
    names = _artifact_names(plat)
    install_dir.mkdir(parents=True, exist_ok=True)

    for name in names:
        # On Windows, renderdoc.dll and renderdoccmd.exe live in x64/Release/ (parent of pymodules)
        if plat == "windows" and name in ("renderdoc.dll", "renderdoccmd.exe"):
            artifact = src.parent / name
        else:
            artifact = src / name
        if not artifact.exists():
            if name in _OPTIONAL_ARTIFACTS:
                _log(f"WARNING: {name} not found at {artifact}, skipping")
                continue
            # macOS may produce .dylib instead of .so for librenderdoc
            if plat == "macos" and name == "librenderdoc.so":
                alt = src / "librenderdoc.dylib"
                if alt.exists():
                    artifact = alt
                else:
                    sys.stderr.write(f"ERROR: artifact not found: {artifact} (also tried .dylib)\n")
                    raise SystemExit(1)
            else:
                sys.stderr.write(f"ERROR: artifact not found: {artifact}\n")
                raise SystemExit(1)
        shutil.copy2(artifact, install_dir / name)
        # Preserve original .dylib name for @rpath resolution on macOS
        if plat == "macos" and artifact.suffix == ".dylib" and name.endswith(".so"):
            shutil.copy2(artifact, install_dir / artifact.name)
    _log(f"artifacts copied to {install_dir}")


def _install_vulkan_layer(install_dir: Path, build_dir: Path) -> None:
    """Copy Vulkan layer JSON and register as implicit layer on Windows."""
    src_dir = build_dir / "renderdoc"

    # Find layer JSON from build output
    layer_src: Path | None = None
    for candidate in (
        src_dir / "renderdoc" / "driver" / "vulkan" / "renderdoc.json",
        src_dir / "driver" / "vulkan" / "renderdoc.json",
    ):
        if candidate.is_file():
            layer_src = candidate
            break
    if layer_src is None:
        _log("WARNING: Vulkan layer JSON not found in source tree, skipping layer registration")
        return

    import json

    data = json.loads(layer_src.read_text(encoding="utf-8"))
    data["layer"]["library_path"] = ".\\renderdoc.dll"
    layer_dst = install_dir / "renderdoc.json"
    layer_dst.write_text(json.dumps(data, indent=2), encoding="utf-8")
    _log(f"Vulkan layer JSON installed to {layer_dst}")

    # Register in Windows registry
    import winreg

    key_path = r"SOFTWARE\Khronos\Vulkan\ImplicitLayers"
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:  # type: ignore[attr-defined,unused-ignore]
            winreg.SetValueEx(key, str(layer_dst), 0, winreg.REG_DWORD, 0)  # type: ignore[attr-defined,unused-ignore]
        _log(f"Vulkan implicit layer registered in HKCU\\{key_path}")
    except OSError as exc:
        _log(f"WARNING: failed to register Vulkan layer in registry: {exc}")


def _android_apk_dir(lib_dir: Path) -> Path:
    """Resolve the Android APK destination relative to *lib_dir*."""
    return (lib_dir / ".." / "share" / "renderdoc" / "plugins" / "android").resolve()


def download_android_apks(version: str, lib_dir: Path) -> None:
    """Download official RenderDoc tarball and extract Android APKs.

    Args:
        version: RenderDoc version string (with or without ``v`` prefix).
        lib_dir: The renderdoc Python module directory.
    """
    version = version.lstrip("v")
    url = f"https://renderdoc.org/stable/{version}/renderdoc_{version}.tar.gz"
    dest = _android_apk_dir(lib_dir)
    dest.mkdir(parents=True, exist_ok=True)

    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as f:
        tmp = Path(f.name)
    try:
        _log(f"downloading {url}")
        urlretrieve(url, str(tmp))
        count = 0
        with tarfile.open(str(tmp), "r:gz") as tf:
            for member in tf.getmembers():
                if not member.name.endswith(".apk"):
                    continue
                # Path traversal guard
                resolved = (dest / Path(member.name).name).resolve()
                if not resolved.is_relative_to(dest):
                    continue
                # Use data_filter if available (Python 3.12+)
                if hasattr(tarfile, "data_filter"):
                    member.name = Path(member.name).name
                    tf.extract(member, dest, filter="data")
                else:
                    src_io = tf.extractfile(member)
                    if src_io is None:
                        continue
                    (dest / Path(member.name).name).write_bytes(src_io.read())
                count += 1
        if count == 0:
            sys.stderr.write("ERROR: no APK files found in tarball\n")
            raise SystemExit(1)
        _log(f"extracted {count} APK(s) to {dest}")
    finally:
        tmp.unlink(missing_ok=True)


def patch_arm_studio_elf(arm_path: Path) -> Path:
    """Patch ARM PS qrenderdoc to be loadable as renderdoc.so Python module.

    ARM Performance Studio embeds PyInit_renderdoc in the qrenderdoc PIE
    executable. Patching two ELF fields makes it dlopen-able as a shared
    object:

    1. PT_INTERP program header type -> PT_NULL (allows dlopen of PIE)
    2. DF_1_PIE bit cleared from DT_FLAGS_1 (removes PIE marker)

    Idempotent: skips if renderdoc.so already exists with same size as source.

    Args:
        arm_path: Root of ARM Performance Studio installation.

    Returns:
        Path to the patched renderdoc.so.
    """
    lib = arm_path / "renderdoc_for_arm_gpus" / "lib"
    src = lib / "qrenderdoc"
    dst = lib / "renderdoc.so"

    if not src.exists():
        sys.stderr.write(f"ERROR: qrenderdoc not found at {src}\n")
        raise SystemExit(1)

    if dst.exists() and dst.stat().st_size == src.stat().st_size:
        _log(f"renderdoc.so already patched at {dst}")
        return dst

    data = bytearray(src.read_bytes())

    # Validate ELF magic
    if data[:4] != b"\x7fELF":
        sys.stderr.write(f"ERROR: {src} is not an ELF file\n")
        raise SystemExit(1)

    ei_class = data[4]
    if ei_class == 1:
        phdr_fmt, dyn_fmt = "<IIIIIIII", "<iI"
    elif ei_class == 2:
        phdr_fmt, dyn_fmt = "<IIQQQQQQ", "<qQ"
    else:
        sys.stderr.write(f"ERROR: unknown ELF class {ei_class}\n")
        raise SystemExit(1)

    # ELF header layout is identical for both classes after e_ident;
    # phoff/phentsize/phnum offsets differ by pointer size.
    if ei_class == 2:
        e_phoff = struct.unpack_from("<Q", data, 32)[0]
        e_phentsize = struct.unpack_from("<H", data, 54)[0]
        e_phnum = struct.unpack_from("<H", data, 56)[0]
    else:
        e_phoff = struct.unpack_from("<I", data, 28)[0]
        e_phentsize = struct.unpack_from("<H", data, 42)[0]
        e_phnum = struct.unpack_from("<H", data, 44)[0]

    pt_interp, pt_null, pt_dynamic = 3, 0, 2
    dt_flags_1 = 0x6FFFFFFB
    df_1_pie = 0x08000000

    patched_interp = False
    dyn_offset = 0
    dyn_size = 0

    # Pass 1: patch PT_INTERP and find PT_DYNAMIC
    for i in range(e_phnum):
        off = e_phoff + i * e_phentsize
        phdr = struct.unpack_from(phdr_fmt, data, off)
        p_type = phdr[0]

        if p_type == pt_interp:
            struct.pack_into("<I", data, off, pt_null)
            patched_interp = True
            _log(f"patched PT_INTERP -> PT_NULL at phdr[{i}]")

        if p_type == pt_dynamic:
            if ei_class == 2:
                # 64-bit: type, flags, offset, vaddr, paddr, filesz, memsz, align
                dyn_offset = phdr[2]
                dyn_size = phdr[5]
            else:
                # 32-bit: type, offset, vaddr, paddr, filesz, memsz, flags, align
                dyn_offset = phdr[1]
                dyn_size = phdr[4]

    if not patched_interp:
        _log("warning: no PT_INTERP found (already patched or not a PIE?)")

    # Pass 2: patch DT_FLAGS_1 in .dynamic
    patched_flags = False
    if dyn_offset and dyn_size:
        dyn_entry_size = struct.calcsize(dyn_fmt)
        n_entries = dyn_size // dyn_entry_size
        for j in range(n_entries):
            entry_off = dyn_offset + j * dyn_entry_size
            d_tag, d_val = struct.unpack_from(dyn_fmt, data, entry_off)
            if d_tag == 0:  # DT_NULL — end of .dynamic
                break
            if d_tag == dt_flags_1:
                new_val = d_val & ~df_1_pie
                if ei_class == 2:
                    struct.pack_into("<Q", data, entry_off + 8, new_val)
                else:
                    struct.pack_into("<I", data, entry_off + 4, new_val)
                patched_flags = True
                _log(f"patched DT_FLAGS_1: 0x{d_val:x} -> 0x{new_val:x}")
                break

    if not patched_flags:
        _log("warning: DT_FLAGS_1 not found in .dynamic")

    dst.write_bytes(bytes(data))
    # Preserve executable permission
    _ensure_executable(dst)
    _log(f"patched renderdoc.so written to {dst}")
    return dst


def install_arm_studio(arm_path: Path, lib_dir: Path) -> None:
    """Copy ARM Performance Studio Android APKs into the local install.

    Only APKs are copied — the host-side renderdoc module stays upstream
    (ARM PS bundles Python 3.10 which is ABI-incompatible). The ARM APKs
    contain Mali-optimized remoteserver that runs on the device.

    Args:
        arm_path: Root of ARM Performance Studio installation.
        lib_dir: The renderdoc Python module directory.
    """
    # ARM PS uses "renderdoc_for_arm_gpus" (not "renderdoc")
    for subdir in ("renderdoc_for_arm_gpus", "renderdoc"):
        arm_apk_dir = arm_path / subdir / "share" / "renderdoc" / "plugins" / "android"
        if arm_apk_dir.is_dir():
            break
    else:
        sys.stderr.write(f"ERROR: no renderdoc directory found in {arm_path}\n")
        raise SystemExit(1)

    apks = list(arm_apk_dir.glob("*.apk"))
    if not apks:
        sys.stderr.write(f"ERROR: no APKs found in {arm_apk_dir}\n")
        raise SystemExit(1)

    dest = _android_apk_dir(lib_dir)
    dest.mkdir(parents=True, exist_ok=True)
    for apk in apks:
        shutil.copy2(apk, dest / apk.name)
    _log(f"copied {len(apks)} ARM APK(s) to {dest}")

    patch_arm_studio_elf(arm_path)


_ARM_PS_URLS = {
    "linux": "https://artifacts.tools.arm.com/arm-performance-studio/{v}/Arm_Performance_Studio_{v}_linux_x86-64.tgz",
    "darwin": "https://artifacts.tools.arm.com/arm-performance-studio/{v}/Arm_Performance_Studio_{v}_macos_arm64.dmg",
}
_ARM_PS_VERSION = "2025.7"


def download_arm_studio(dest: Path) -> Path:
    """Download ARM Performance Studio and extract to *dest*.

    Returns the root directory of the extracted ARM PS installation.
    The actual renderdoc directory inside is ``renderdoc_for_arm_gpus/``.
    Idempotent: skips if the APK marker exists.
    Only supports Linux (.tgz). Windows is not supported.

    Args:
        dest: Target directory (e.g. ``.local/arm-performance-studio``).
    """
    marker = dest / "renderdoc_for_arm_gpus" / "share" / "renderdoc" / "plugins" / "android"
    if marker.is_dir() and list(marker.glob("*.apk")):
        _log(f"ARM Performance Studio already present at {dest}")
        return dest

    if sys.platform == "win32":
        sys.stderr.write("ERROR: ARM Performance Studio download not supported on Windows\n")
        raise SystemExit(1)

    key = sys.platform if sys.platform in _ARM_PS_URLS else "linux"
    url = _ARM_PS_URLS[key].format(v=_ARM_PS_VERSION)
    dest.mkdir(parents=True, exist_ok=True)

    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".tgz", delete=False) as f:
        tmp = Path(f.name)
    try:
        _log(f"downloading ARM Performance Studio from {url}")
        urlretrieve(url, str(tmp))
        _log("extracting...")
        with tarfile.open(str(tmp), "r:gz") as tf:
            # Strip top-level directory to extract directly into dest
            for member in tf.getmembers():
                # Path traversal guard
                parts = Path(member.name).parts
                if len(parts) <= 1:
                    continue
                rel = str(Path(*parts[1:]))
                resolved = (dest / rel).resolve()
                if not resolved.is_relative_to(dest.resolve()):
                    continue
                member.name = rel
                if hasattr(tarfile, "data_filter"):
                    tf.extract(member, dest, filter="data")
                else:
                    tf.extract(member, dest)
        if not marker.is_dir() or not list(marker.glob("*.apk")):
            sys.stderr.write(f"ERROR: no APKs found at {marker} after extraction\n")
            raise SystemExit(1)
        _log(f"ARM Performance Studio extracted to {dest}")
    finally:
        tmp.unlink(missing_ok=True)
    return dest


def _artifacts_present(install_dir: Path, plat: str) -> bool:
    required = [n for n in _artifact_names(plat) if n not in _OPTIONAL_ARTIFACTS]
    return all((install_dir / n).exists() for n in required)


def main(argv: list[str] | None = None) -> None:
    """Entry point: parse args and orchestrate the build."""
    parser = argparse.ArgumentParser(description="Build RenderDoc Python bindings from source.")
    parser.add_argument("install_dir", nargs="?", default=None, help="Installation directory")
    parser.add_argument("--build-dir", default=None, help="Build cache directory")
    parser.add_argument("--version", default=RDOC_TAG, help="RenderDoc tag to build")
    parser.add_argument("--jobs", type=int, default=None, help="Parallel build jobs")
    args = parser.parse_args(argv)

    plat = _platform()
    install_dir = Path(args.install_dir).resolve() if args.install_dir else default_install_dir()
    build_dir = (
        Path(args.build_dir).resolve() if args.build_dir else install_dir.parent / "renderdoc-build"
    )

    if _artifacts_present(install_dir, plat):
        _log(f"renderdoc already exists at {install_dir}/")
        _log(f"To rebuild: rm -rf {install_dir} {build_dir} && re-run this script")
        return

    _log(f"=== Building renderdoc {args.version} Python module ===")
    check_prerequisites(plat)
    verify_tool_versions(plat)
    clone_renderdoc(build_dir, args.version)

    if plat == "windows":
        python_prefix = _prepare_win_python(build_dir / "renderdoc")
        _run_msbuild(build_dir, python_prefix, args.jobs)
    else:
        download_swig(build_dir)
        swig_dir = build_dir / "renderdoc-swig"
        if plat == "macos":
            prepare_custom_swig(swig_dir)
        configure_build(build_dir, swig_dir, plat)
        run_build(build_dir, args.jobs)

    copy_artifacts(build_dir, install_dir, plat)

    if plat == "windows":
        _install_vulkan_layer(install_dir, build_dir)

    _log("=== Done ===")
    _log(f'  export RENDERDOC_PYTHON_PATH="{install_dir}"')
    _log("  rdc doctor   # verify installation")


if __name__ == "__main__":
    main()
