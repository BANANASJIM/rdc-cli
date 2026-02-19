FROM ubuntu:24.04

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl git python3 python3-venv python3-pip \
    && rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

WORKDIR /workspace

# Usage:
#   docker build -t rdc-cli-dev -f docker/Dockerfile .
#   docker run --rm -it -v "$PWD":/workspace rdc-cli-dev bash
