#!/bin/bash
# =================================================
#   Jetson Orin Nano - Phase 2 Environment Setup
#   Tested: March 16, 2026
# =================================================
# This script:
#   1. Removes any existing Conda/Anaconda/Miniconda installations
#   2. Installs Miniforge (ARM64-native Conda) from scratch
#   3. Creates a Python 3.10 "buggy" environment
#   4. Downloads NVIDIA's JetPack 6 PyTorch wheel directly
#   5. Installs PyTorch, Ultralytics (YOLO), and all Phase 2 dependencies
#
# WHY MINIFORGE?
#   Standard Anaconda/Miniconda channels don't reliably serve ARM64 (aarch64)
#   packages. Miniforge is identical to Miniconda but defaults to conda-forge,
#   which has full ARM64 support.
#
# WHY PYTHON 3.10?
#   NVIDIA only compiles JetPack 6 PyTorch wheels for Python 3.10 (cp310).
#   Any other Python version will fail with "no matching distribution."
#
# WHY DIRECT WGET INSTEAD OF --index-url?
#   NVIDIA's download server is NOT a PEP 503 compliant pip index.
#   Using --index-url with it silently fails. Downloading the .whl file
#   directly and installing it locally is the only reliable method.
# =================================================

set -e

echo "================================================="
echo "   Jetson Orin Nano - Phase 2 Environment Setup  "
echo "================================================="

# ---------------------------
# Step 1: Clean slate
# ---------------------------
echo ""
echo "Step 1: Removing existing Conda/Anaconda installations..."
rm -rf ~/miniconda3
rm -rf ~/anaconda3
rm -rf ~/miniforge3
rm -rf ~/.conda

# Remove old conda init blocks from .bashrc
sed -i '/>>> conda initialize >>>/,/<<< conda initialize <<</d' ~/.bashrc
echo "Done. Old conda paths and environments cleared."

# ---------------------------
# Step 2: Install Miniforge
# ---------------------------
echo ""
echo "Step 2: Downloading and installing Miniforge (ARM64)..."
cd /tmp
wget -O Miniforge3.sh "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-aarch64.sh"
bash Miniforge3.sh -b -p ~/miniforge3
echo "Done. Miniforge installed to ~/miniforge3."

# ---------------------------
# Step 3: Initialize Miniforge
# ---------------------------
echo ""
echo "Step 3: Initializing Miniforge for bash..."
~/miniforge3/bin/conda init bash
source ~/miniforge3/etc/profile.d/conda.sh
echo "Done."

# ---------------------------
# Step 4: Create Python 3.10 environment
# ---------------------------
echo ""
echo "Step 4: Creating Python 3.10 environment ('buggy')..."
conda create -n buggy python=3.10 -y
conda activate buggy
echo "Done. Active environment: $(python3 --version)"

# ---------------------------
# Step 5: Install NVIDIA PyTorch (direct download)
# ---------------------------
echo ""
echo "Step 5: Downloading NVIDIA-optimized PyTorch for JetPack 6..."
TORCH_WHL="torch-2.4.0a0+3bcc3cddb5.nv24.07.16234504-cp310-cp310-linux_aarch64.whl"
TORCH_URL="https://developer.download.nvidia.com/compute/redist/jp/v60/pytorch/${TORCH_WHL}"

cd /tmp
if [ ! -f "$TORCH_WHL" ]; then
    wget "$TORCH_URL"
else
    echo "PyTorch wheel already downloaded, skipping."
fi

echo "Installing PyTorch from local wheel..."
pip install "/tmp/${TORCH_WHL}"
echo "Done. PyTorch installed."

# ---------------------------
# Step 6: Install remaining dependencies
# ---------------------------
echo ""
echo "Step 6: Installing Ultralytics (YOLO) and Phase 2 dependencies..."
pip install torchvision
pip install ultralytics
pip install albumentations PyYAML tqdm
echo "Done."

# ---------------------------
# Complete
# ---------------------------
echo ""
echo "================================================="
echo "              ✅ Setup Complete!                  "
echo "================================================="
echo ""
echo "IMPORTANT: Close this terminal and open a new one."
echo ""
echo "To run your YOLO test:"
echo "  conda activate buggy"
echo "  cd ~/Desktop/buggy-1/phase-2/YOLO_testing/kalman_histo_scaffolding/"
echo "  python3 kalman_histo.py --weights ../../best.pt"
echo "================================================="
