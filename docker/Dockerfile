# rdc-cli dev image with RenderDoc python module
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl git make cmake g++ pkg-config \
    bison flex autoconf automake libtool m4 \
    python3.11 python3.11-dev python3.11-venv \
    libx11-dev libxcb1-dev libgl-dev libxcb-keysyms1-dev \
    && rm -rf /var/lib/apt/lists/*

ARG RENDERDOC_VERSION=v1.33
RUN git clone --depth 1 --branch ${RENDERDOC_VERSION} https://github.com/baldurk/renderdoc.git /renderdoc \
    && cd /renderdoc \
    && cmake -B build -DCMAKE_BUILD_TYPE=Release \
        -DENABLE_PYRENDERDOC=ON \
        -DENABLE_QRENDERDOC=OFF \
        -DPython3_EXECUTABLE=/usr/bin/python3.11 \
        -DPython3_INCLUDE_DIR=/usr/include/python3.11 \
        -DPython3_LIBRARY=/usr/lib/x86_64-linux-gnu/libpython3.11.so \
    && cmake --build build -j2

ENV RENDERDOC_PYTHON_PATH=/renderdoc/build/lib
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1

RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

WORKDIR /workspace

RUN python3 -c "import sys; sys.path.insert(0, '/renderdoc/build/lib'); import renderdoc; print('renderdoc module OK')"
