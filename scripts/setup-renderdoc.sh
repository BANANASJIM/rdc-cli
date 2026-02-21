#!/usr/bin/env bash
# Build renderdoc v1.41 Python module for the pixi dev environment.
# Usage: pixi run setup-renderdoc
# Output: .local/renderdoc/renderdoc.so + librenderdoc.so
# Only needs to run once (or after Python version change).
set -euo pipefail

RDOC_TAG="v1.41"
SWIG_URL="https://github.com/baldurk/swig/archive/renderdoc-modified-7.zip"
BUILD_DIR=".local/renderdoc-build"
OUT_DIR=".local/renderdoc"

if [ -f "$OUT_DIR/renderdoc.so" ]; then
  echo "renderdoc.so already exists at $OUT_DIR/"
  echo "To rebuild: rm -rf .local/renderdoc* && pixi run setup-renderdoc"
  exit 0
fi

echo "=== Building renderdoc $RDOC_TAG Python module ==="

mkdir -p "$BUILD_DIR" "$OUT_DIR"

# Clone renderdoc
if [ ! -d "$BUILD_DIR/renderdoc" ]; then
  echo "--- Cloning renderdoc $RDOC_TAG ---"
  git clone --depth 1 --branch "$RDOC_TAG" \
    https://github.com/baldurk/renderdoc.git "$BUILD_DIR/renderdoc"
fi

# Download SWIG fork
if [ ! -d "$BUILD_DIR/renderdoc-swig" ]; then
  echo "--- Downloading SWIG fork ---"
  curl -sL "$SWIG_URL" -o "$BUILD_DIR/swig.zip"
  unzip -q "$BUILD_DIR/swig.zip" -d "$BUILD_DIR"
  mv "$BUILD_DIR/swig-renderdoc-modified-7" "$BUILD_DIR/renderdoc-swig"
  rm "$BUILD_DIR/swig.zip"
fi

# Strip LTO flags (breaks SWIG bindings on Arch)
export CFLAGS="${CFLAGS:-}"
export CXXFLAGS="${CXXFLAGS:-}"
export LDFLAGS="${LDFLAGS:-}"
CFLAGS="${CFLAGS//-flto=auto/}"
CXXFLAGS="${CXXFLAGS//-flto=auto/}"
LDFLAGS="${LDFLAGS//-flto=auto/}"

# Build
echo "--- cmake configure ---"
cmake -B "$BUILD_DIR/renderdoc/build" -S "$BUILD_DIR/renderdoc" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DENABLE_PYRENDERDOC=ON \
  -DENABLE_QRENDERDOC=OFF \
  -DENABLE_RENDERDOCCMD=OFF \
  -DENABLE_GL=OFF \
  -DENABLE_GLES=OFF \
  -DENABLE_VULKAN=ON \
  -DRENDERDOC_SWIG_PACKAGE="$(pwd)/$BUILD_DIR/renderdoc-swig"

echo "--- cmake build ---"
cmake --build "$BUILD_DIR/renderdoc/build" -j "$(nproc)"

# Copy artifacts
cp "$BUILD_DIR/renderdoc/build/lib/renderdoc.so" "$OUT_DIR/"
cp "$BUILD_DIR/renderdoc/build/lib/librenderdoc.so" "$OUT_DIR/"

echo ""
echo "=== Done: $OUT_DIR/ ==="
ls -lh "$OUT_DIR/"
