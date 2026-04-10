#!/bin/sh
# =============================================================================
#  setup.sh — Environment bootstrap for jetson-yolo-detector
#  Runs once when viam-server first deploys the module.
#
#  What this does:
#   1. Creates a Python venv
#   2. Installs standard pip packages (viam-sdk, ultralytics, etc.)
#   3. Installs the custom torchvision wheel compiled for JetPack 6.2 + CUDA
#   4. Symlinks system TensorRT libs into the venv so ultralytics can find them
# =============================================================================
set -e
cd "$(dirname "$0")"

VENV_NAME="venv"
PYTHON="$VENV_NAME/bin/python"
PIP="$VENV_NAME/bin/pip"

# ---------------------------------------------------------------------------
# 1. Create virtual environment (Python 3.10 on JetPack 6.2)
# ---------------------------------------------------------------------------
if ! python3 -m venv "$VENV_NAME" > /dev/null 2>&1; then
    echo "[setup] Failed to create venv — installing python3-venv..."
    sudo apt-get install -qqy python3-venv > /dev/null 2>&1
    python3 -m venv "$VENV_NAME"
fi
echo "[setup] Virtual environment ready ✓"

# ---------------------------------------------------------------------------
# 2. Install standard packages (skip if already done)
# ---------------------------------------------------------------------------
if [ ! -f .installed_base ]; then
    echo "[setup] Installing base packages..."
    $PIP install --quiet --upgrade pip
    $PIP install --quiet -r requirements.txt
    touch .installed_base
    echo "[setup] Base packages installed ✓"
fi

# ---------------------------------------------------------------------------
# 3. Install NVIDIA-optimised PyTorch for JetPack 6.2
#    Pre-built wheel from NVIDIA's index — avoids a 2-hour source compile.
# ---------------------------------------------------------------------------
if ! $PYTHON -c "import torch; assert torch.cuda.is_available()" > /dev/null 2>&1; then
    echo "[setup] Installing NVIDIA PyTorch wheel for JetPack 6.2..."
    $PIP install --quiet --no-cache-dir \
        "torch>=2.3.0" \
        --index-url https://developer.download.nvidia.com/compute/redist/jp/v62
    echo "[setup] PyTorch installed ✓"
fi

# ---------------------------------------------------------------------------
# 4. Install torchvision compiled against the above PyTorch + CUDA
#    (standard pip wheel is CPU-only; we need the CUDA build)
# ---------------------------------------------------------------------------
if ! $PYTHON -c "import torchvision" > /dev/null 2>&1; then
    echo "[setup] Installing torchvision (CUDA build)..."
    # Try NVIDIA index first
    $PIP install --quiet --no-deps --no-cache-dir \
        "torchvision" \
        --index-url https://developer.download.nvidia.com/compute/redist/jp/v62 \
        || true

    # Fallback: install from source (only reached if NVIDIA index fails)
    if ! $PYTHON -c "import torchvision" > /dev/null 2>&1; then
        echo "[setup] NVIDIA index failed — building torchvision from source (this takes ~20 min)..."
        sudo apt-get install -qqy libjpeg-dev zlib1g-dev > /dev/null 2>&1
        TORCH_VER=$($PYTHON -c "import torch; print(torch.__version__.split('+')[0])")
        $PIP install --quiet --no-deps \
            "git+https://github.com/pytorch/vision.git@v${TORCH_VER}"
    fi
    echo "[setup] torchvision installed ✓"
fi

# ---------------------------------------------------------------------------
# 5. Symlink system TensorRT libraries into the venv
#    Required because TensorRT ships as system packages on JetPack, not pip.
# ---------------------------------------------------------------------------
SITE_PKGS=$($PYTHON -c "import site; print(site.getsitepackages()[0])")
TRT_SYSTEM_PATH="/usr/lib/python3/dist-packages"

echo "[setup] Linking TensorRT system packages into venv..."
for item in "$TRT_SYSTEM_PATH"/tensorrt*; do
    [ -e "$item" ] || continue
    name=$(basename "$item")
    target="$SITE_PKGS/$name"
    if [ ! -e "$target" ]; then
        ln -sf "$item" "$target"
        echo "[setup]   linked $name"
    fi
done
echo "[setup] TensorRT symlinks done ✓"

echo "[setup] ✅ Setup complete — jetson-yolo-detector is ready"
