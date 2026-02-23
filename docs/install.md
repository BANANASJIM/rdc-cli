# Installation

## Requirements

- Python 3.10 or later
- The [RenderDoc](https://renderdoc.org/) Python module (`renderdoc.cpython-*.so`)

## Install rdc-cli

### PyPI (recommended)

```bash
pipx install rdc-cli
```

Or with pip:

```bash
pip install rdc-cli
```

### AUR (Arch Linux)

The AUR package builds the renderdoc Python module automatically:

```bash
yay -S rdc-cli-git
```

### From source

```bash
git clone https://github.com/BANANASJIM/rdc-cli.git
cd rdc-cli
pixi install && pixi run sync
```

## Setup renderdoc

`rdc` requires the renderdoc Python module, which is **not** included in most
system packages. Your Python version must match the one used to compile renderdoc.

### Build from source

```bash
git clone --depth 1 https://github.com/baldurk/renderdoc.git
cd renderdoc
cmake -B build -DENABLE_PYRENDERDOC=ON -DENABLE_QRENDERDOC=OFF
cmake --build build -j$(nproc)
export RENDERDOC_PYTHON_PATH=$PWD/build/lib
```

### Module discovery order

1. `RENDERDOC_PYTHON_PATH` environment variable
2. `/usr/lib/renderdoc`, `/usr/local/lib/renderdoc`
3. Sibling directory of `renderdoccmd` on PATH

Verify your setup with:

```bash
rdc doctor
```
