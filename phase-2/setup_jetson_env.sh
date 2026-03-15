#!/bin/bash
# Stop on any error
set -e

echo "================================================="
echo "   Jetson Orin Nano - Phase 2 Environment Setup  "
echo "================================================="

echo ""
echo "Step 1: Removing existing Conda/Anaconda installations to start fresh..."
# Force remove the most common default installation paths
rm -rf ~/miniconda3
rm -rf ~/anaconda3
rm -rf ~/miniforge3
rm -rf ~/.conda

# Clean up .bashrc to remove old conda initialization blocks
# This prevents the old broken base environment from loading when you open a terminal
sed -i '/>>> conda initialize >>>/,/<<< conda initialize <<</d' ~/.bashrc
echo "Old paths and environments cleared."

echo ""
echo "Step 2: Downloading and Installing Miniforge (ARM64)..."
cd /tmp
wget -O Miniforge3.sh "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-aarch64.sh"
# -b runs it in batch mode (no manual "yes" needed), -p sets the path
bash Miniforge3.sh -b -p ~/miniforge3

echo ""
echo "Step 3: Initializing Miniforge..."
# Initialize it so it adds the new correct block to your .bashrc
~/miniforge3/bin/conda init bash
# Source it directly for this script so we can use the 'conda' command immediately
source ~/miniforge3/etc/profile.d/conda.sh

echo ""
echo "Step 4: Creating Python 3.10 environment ('buggy')..."
# Python 3.10 is MANDATORY for NVIDIA's PyTorch wheels
conda create -n buggy python=3.10 -y
conda activate buggy

echo ""
echo "Step 5: Installing NVIDIA-optimized PyTorch for JetPack 6..."
pip install torch --index-url https://developer.download.nvidia.com/compute/redist/jp/v60

echo ""
echo "Step 6: Installing Ultralytics (YOLO) and Phase 2 Dependencies..."
# Ultralytics will install standard opencv-python, numpy, pillow, tqdm, etc.
pip install ultralytics
# Adding explicit dependencies from your requirements.txt just in case! 
pip install albumentations PyYAML tqdm

echo ""
echo "================================================="
echo "                 Setup Complete!                 "
echo "================================================="
echo "1. Because we modified your .bashrc, you MUST close this terminal."
echo "2. Open a BRAND NEW terminal."
echo "3. You should see (base) next to your name. Your clean slate is ready!"
echo ""
echo "To run your test, execute:"
echo "conda activate buggy"
echo "cd ~/Desktop/buggy-1/phase-2/YOLO_testing/kalman_histo_scaffolding/"
echo "python3 kalman_histo.py --weights ../../best.pt"
echo "================================================="
