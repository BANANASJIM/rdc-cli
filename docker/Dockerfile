# rdc-cli development image with renderdoc Python module
#
# Build:  docker build -t rdc-cli-dev -f docker/Dockerfile .
# Run:    docker run --rm -it -v "$PWD":/workspace rdc-cli-dev bash
#
# The renderdoc Python module is compiled from source and available via
# RENDERDOC_PYTHON_PATH. Use `rdc doctor` inside the container to verify.

FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl git make cmake g++ pkg-config \
    python3.11 python3.11-dev python3.11-venv \
    libx11-dev libxcb1-dev libgl-dev libxcb-keysyms1-dev \
    && rm -rf /var/lib/apt/lists/*

# Build renderdoc from source with Python module enabled
ARG RENDERDOC_VERSION=v1.33
RUN git clone --depth 1 --branch ${RENDERDOC_VERSION} \
        https://github.com/baldurk/renderdoc.git /renderdoc \
    && cd /renderdoc \
    && cmake -B build -DCMAKE_BUILD_TYPE=Release \
        -DENABLE_PYRENDERDOC=ON \
        -DENABLE_QRENDERDOC=OFF \
        -DPython3_EXECUTABLE=/usr/bin/python3.11 \
        -DPython3_INCLUDE_DIR=/usr/include/python3.11 \
        -DPython3_LIBRARY=/usr/lib/x86_64-linux-gnu/libpython3.11.so \
    && cmake --build build -j$(($(nproc) > 4 ? 4 : $(nproc)))

ENV RENDERDOC_PYTHON_PATH=/renderdoc/build/lib

# Install uv for dependency management
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

# Make python3.11 the default python3
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1

WORKDIR /workspace

# Verify renderdoc module is importable
RUN python3 -c "import sys; sys.path.insert(0, '/renderdoc/build/lib'); import renderdoc; print('renderdoc module OK')"

# Usage:
#   docker build -t rdc-cli-dev -f docker/Dockerfile .
#   docker run --rm -it -v "$PWD":/workspace rdc-cli-dev bash
#   # Inside container:
#   uv sync && uv run rdc doctor
