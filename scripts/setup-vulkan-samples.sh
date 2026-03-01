#!/usr/bin/env bash
set -euo pipefail

# Clone and build Vulkan-Samples for full e2e capture testing.
# The built binary is used by tests/e2e/test_capture.py.
TARGET=".local/vulkan-samples"

if [[ -x "${TARGET}/vulkan_samples" ]]; then
    echo "vulkan_samples already built at ${TARGET}/vulkan_samples"
    exit 0
fi

mkdir -p "$(dirname "${TARGET}")"

if [[ ! -d "${TARGET}/src" ]]; then
    echo "Cloning Vulkan-Samples..."
    git clone --depth 1 https://github.com/KhronosGroup/Vulkan-Samples.git "${TARGET}/src"
fi

echo "Building Vulkan-Samples..."
cd "${TARGET}/src"
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --parallel "$(nproc)" --target vulkan_samples

# Symlink binary to expected location
cd -
ln -sf "src/build/app/bin/vulkan_samples" "${TARGET}/vulkan_samples"
echo "Done: ${TARGET}/vulkan_samples"
