#!/usr/bin/env bash
# DEPRECATED: use scripts/build_renderdoc.py instead.
# Kept for curl-pipe users on systems without Python 3.10+.
# Build renderdoc v1.41 Python module from source.
# Usage: bash <(curl -fsSL https://raw.githubusercontent.com/BANANASJIM/rdc-cli/master/scripts/build-renderdoc.sh) [INSTALL_DIR]
# Output: INSTALL_DIR/renderdoc.so + librenderdoc.so (default: ~/.local/renderdoc/)
set -euo pipefail

RDOC_TAG="v1.41"
SWIG_URL="https://github.com/baldurk/swig/archive/renderdoc-modified-7.zip"
SWIG_SHA256="9d7e5013ada6c42ec95ab167a34db52c1cc8c09b89c8e9373631b1f10596c648"
OUT_DIR="${1:-${HOME}/.local/renderdoc}"
BUILD_DIR="${HOME}/.local/renderdoc-build"

if [ -f "$OUT_DIR/renderdoc.so" ]; then
  echo "renderdoc.so already exists at $OUT_DIR/"
  echo "To rebuild: rm -rf $OUT_DIR $BUILD_DIR && re-run this script"
  exit 0
fi

# Check prerequisites
missing=()
for cmd in cmake ninja git curl unzip python3; do
  command -v "$cmd" >/dev/null 2>&1 || missing+=("$cmd")
done
if [ ${#missing[@]} -gt 0 ]; then
  echo "ERROR: missing required tools: ${missing[*]}" >&2
  exit 1
fi

echo "=== Building renderdoc $RDOC_TAG Python module ==="

mkdir -p "$BUILD_DIR" "$OUT_DIR"

# Clone renderdoc (idempotent)
if [ ! -d "$BUILD_DIR/renderdoc" ]; then
  echo "--- Cloning renderdoc $RDOC_TAG ---"
  git clone --depth 1 --branch "$RDOC_TAG" \
    https://github.com/baldurk/renderdoc.git "$BUILD_DIR/renderdoc"
fi

# Download SWIG fork + sha256 verify (idempotent)
if [ ! -d "$BUILD_DIR/renderdoc-swig" ]; then
  echo "--- Downloading SWIG fork ---"
  curl -fsSL "$SWIG_URL" -o "$BUILD_DIR/swig.zip"
  echo "$SWIG_SHA256  $BUILD_DIR/swig.zip" | sha256sum -c - || {
    echo "ERROR: SWIG archive sha256 mismatch" >&2
    rm -f "$BUILD_DIR/swig.zip"
    exit 1
  }
  unzip -q "$BUILD_DIR/swig.zip" -d "$BUILD_DIR"
  mv "$BUILD_DIR/swig-renderdoc-modified-7" "$BUILD_DIR/renderdoc-swig"
  rm "$BUILD_DIR/swig.zip"
fi

# Strip LTO flags (breaks SWIG bindings on Arch)
export CFLAGS="${CFLAGS:-}"; CFLAGS="${CFLAGS//-flto=auto/}"
export CXXFLAGS="${CXXFLAGS:-}"; CXXFLAGS="${CXXFLAGS//-flto=auto/}"
export LDFLAGS="${LDFLAGS:-}"; LDFLAGS="${LDFLAGS//-flto=auto/}"

# Configure
echo "--- cmake configure ---"
cmake -B "$BUILD_DIR/renderdoc/build" -S "$BUILD_DIR/renderdoc" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DENABLE_PYRENDERDOC=ON \
  -DENABLE_QRENDERDOC=OFF \
  -DENABLE_RENDERDOCCMD=OFF \
  -DENABLE_GL=OFF \
  -DENABLE_GLES=OFF \
  -DENABLE_VULKAN=ON \
  -DRENDERDOC_SWIG_PACKAGE="$BUILD_DIR/renderdoc-swig"

# Build
echo "--- cmake build ---"
cmake --build "$BUILD_DIR/renderdoc/build" -j "$(nproc 2>/dev/null || echo 4)"

# Copy artifacts
cp "$BUILD_DIR/renderdoc/build/lib/renderdoc.so" "$OUT_DIR/"
cp "$BUILD_DIR/renderdoc/build/lib/librenderdoc.so" "$OUT_DIR/"

echo ""
echo "=== Done ==="
echo "  export RENDERDOC_PYTHON_PATH=\"$OUT_DIR\""
echo "  rdc doctor   # verify installation"
