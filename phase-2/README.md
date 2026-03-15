# Phase 2: YOLO Follow-Me

Train a custom YOLO model to detect and follow you specifically, deployed on Jetson Orin Nano.

---

## ⚠️ Current Status

| Component | Status |
|-----------|--------|
| **Mac Pipeline** | ✅ Ready & Tested |
| **Model V1** | ✅ Trained & Validated (mAP50: 0.98) |
| **Jetson Pipeline** | ✅ Deployed & Tested (March 16, 2026) |

---

## Overview

| Component | Details |
|-----------|---------|
| **Model** | YOLO11n |
| **Classes** | `tanmay` (0), `other_person` (1) |
| **Training** | Mac M3 (MPS) |
| **Deployment** | Jetson Orin Nano (TensorRT) |

---

## YOLO Model V1 (Feb 12, 2026)

The first production-ready model for the follow-me buggy.

### Performance (Validation Set)
| Class | Images | Instances | Box (P) | R | mAP50 | mAP50-95 |
|-------|--------|-----------|---------|---|-------|----------|
| **All** | 342 | 550 | 0.964 | 0.966 | **0.979** | **0.805** |
| **tanmay** | 224 | 224 | 0.983 | 1.000 | **0.995** | 0.864 |
| **other_person** | 164 | 326 | 0.945 | 0.933 | **0.964** | 0.746 |

**Speed:** ~25ms inference per frame on M3 Pro (via `mps`).

### Dataset Details
Total images: **1,704** (Augmented 4x from 426 raw images)

| Class | Annotated (Raw) | ×4 Augmented | Train (80%) | Val (20%) |
|-------|-----------------|--------------|-------------|-----------|
| `tanmay` | 276 | 1,104* | 826 | 207 |
| `other_person` | 100 | 400* | 376 | 95 |
| `background` | 50 | 200 | 160 | 40 |
| **Total** | **426** | **1,704** | **1,362** | **342** |
*\*Note: Augmented counts show folder source. Split script logic classifies based on the first label entry, explaining minor distribution shifts in split report.*

### User Feedback & Observations
- **Overall:** Highly workable and accurate detection.
- **Hallucinations:** Rapid movement can occasionally cause a second "phantom" bounding box (`tanmay` + `other_person`).
- **Edge Cases:** Certain extreme poses can sometimes result in failed recognition of the `tanmay` class.
- **Stability:** Very stable during walking and stationary positions.

## ⚠️ Important: Class ID Reversal (Known Issue)

> [!CAUTION]
> **Label Studio exports class IDs based on the label order in the project config**, NOT based on our `classes.txt` or `data.yaml`.
> 
> ### The Problem
> Our expected class mapping is `tanmay=0, other_person=1`. However, Label Studio assigns IDs based on the order labels appear in the labeling interface config. If `other_person` appears first in the config, the export produces **reversed IDs**:
> 
> | Source | tanmay | other_person |
> |--------|--------|--------------|
> | Our `data.yaml` / `classes.txt` | **0** | **1** |
> | Label Studio export (tanmay project) | 1 | 0 |
> | Label Studio export (other_person project) | — | 0 |
> 
> ### Root Cause
> `01_process_labels.py` has a `build_class_remap()` function that relies on `notes.json` (from Label Studio export) to detect and fix the mismatch. However, **Label Studio does not always include `notes.json` in YOLO exports**, so the remap silently does nothing (`Labels remapped: 0`).
> 
> ### Manual Fix Required After Processing
> After running `01_process_labels.py`, you must manually remap class IDs:
> - **tanmay labels**: swap `0↔1` (tanmay was exported as 1, other_person as 0)
> - **other_person labels**: remap `0→1` (other_person was exported as 0)
> 
> ### How to Verify
> ```bash
> # Check class distribution — tanmay(0) should be majority in tanmay/, other_person(1) in other_person/
> cat dataset/annotated/labels/tanmay/*.txt | awk '{print $1}' | sort | uniq -c
> cat dataset/annotated/labels/other_person/*.txt | awk '{print $1}' | sort | uniq -c
> ```
> 
> ### Visualization Check
> Run `python scripts/visualize_annotations.py` to draw boxes on images (red=tanmay, blue=other_person) and visually confirm classes are correct.

---

## Pipeline

```
raw/ → annotated/ → augmented/ → train/ + val/ → model → Jetson
```

---

## Step 1: Data Collection

### 1.1 Gather Raw Images
Place images in `dataset/raw/`:
```
dataset/raw/
├── tanmay/        # 150-200 images of yourself (prioritize full-body)
├── other_person/  # 50-100 images of 10-20 different people
└── background/    # 30-50 empty scenes (no people)
```

### 1.2 Rename with Prefixes
```bash
conda activate buggy
python scripts/00_add_prefixes.py --dry-run  # Preview
python scripts/00_add_prefixes.py             # Apply
```
Result: `tanmay_001.jpg`, `other_001.jpg`, `bg_001.jpg`

---

## Step 2: Annotation

### 2.1 Start Label Studio
```bash
./scripts/start_label_studio.sh
# Or: conda activate buggy && label-studio start --port 8080
```
Open http://localhost:8080

### 2.2 Create Project
1. Sign up (local account)
2. Create Project → "Tanmay Detection"
3. Settings → Labeling Interface → paste config from `dataset/label_studio_config.xml`
4. Import images from `dataset/raw/`

### 2.3 Annotate
- Press `1` → draw box around yourself → `tanmay`
- Press `2` → draw box around other people → `other_person`
- Background images: no boxes needed
- Press `D` to submit and move to next

**Annotation Rules:**
- Box full visible body (head to feet when possible)
- Tight fit, minimal padding
- For partial visibility, box what's visible

### 2.4 Export & Process
```bash
# Export from Label Studio → YOLO format
# Place labels in dataset/annotated/labels/<class>/
# Place images in dataset/annotated/images/<class>/

# Process labels (strip hash prefixes, move orphans)
python scripts/01_process_labels.py --dry-run  # Preview
python scripts/01_process_labels.py             # Apply

# ⚠️ IMPORTANT: Manually verify/fix class IDs after processing!
# See "Class ID Reversal" section above
```

### 2.5 Prepare Background Images (Negative Examples)
```bash
# Copies background images from raw/ to annotated/ with empty label files
# These teach the model "no people here" → reduces false positives
python scripts/01b_prep_backgrounds.py --dry-run  # Preview
python scripts/01b_prep_backgrounds.py             # Apply
```

---

## Step 3: Augmentation

```bash
python scripts/02_augment.py --dry-run
python scripts/02_augment.py
```

**Augmentations applied:**
- Perspective warp (simulate low camera angle)
- Brightness/contrast variation
- Motion blur
- Scale variation

Result: `dataset/augmented/` with 4x images (1 orig + 3 augmented per image)

---

## Step 4: Train/Val Split

```bash
python scripts/03_split_dataset.py --dry-run
python scripts/03_split_dataset.py
```

Result: 80% train, 20% val (stratified by class)

---

## Step 5: Training

```bash
python scripts/04_train.py
# Or with options:
python scripts/04_train.py --epochs 50 --batch 8
```

Training time: ~10-20 minutes on M3

---

## Step 6: Export for Jetson

```bash
python scripts/05_export.py
# Creates: models/best.onnx
```

---

## Step 7: Jetson Deployment ✅

### 7.1 Jetson Environment Setup (One-Time)

The Jetson Orin Nano requires a specific Python environment to run PyTorch. See the
"Conda → Miniforge Migration" section below for full context.

```bash
# Run the automated setup script (wipes old conda, installs miniforge + dependencies)
chmod +x setup_jetson_env.sh
./setup_jetson_env.sh

# After script completes, close terminal and open a new one.
```

### 7.2 Copy Weights to Jetson

The `.pt` weights are gitignored (too large). Transfer them directly from Mac → Jetson:
```bash
# From your Mac terminal:
scp phase-2/training/runs/tanmay_detector_20260212_164033/weights/best.pt \
    tanmay-jetson@<jetson-ip>:~/Desktop/buggy-1/phase-2/best.pt
```

### 7.3 Run Live Inference Test

```bash
conda activate buggy
cd ~/Desktop/buggy-1/phase-2/YOLO_testing/kalman_histo_scaffolding/
python3 kalman_histo.py --weights ../../best.pt
```

Press `X` to exit. Expected behavior:
- **Red box** (`TANMAY LOCKED`) around you with green "Visual ID Locked" dot
- **Blue boxes** around other people
- **Orange box** (`GHOSTING`) if you briefly leave the frame — Kalman filter predicts your trajectory

### 7.4 TensorRT Optimization (Future)

For production framerate (20-30 FPS), export to TensorRT:
```bash
# Export to ONNX (on Mac)
python scripts/05_export.py

# Convert to TensorRT engine (on Jetson)
trtexec --onnx=best.onnx --saveEngine=best.engine --fp16
```

---

## Conda → Miniforge Migration (Jetson)

> [!IMPORTANT]
> **Standard Anaconda/Miniconda does not work reliably on the Jetson Orin Nano for PyTorch.**
> This section documents why and what we did about it.

### The Problem
Three things conspired against us:
1. **ARM64 architecture**: The Jetson uses an ARM processor (aarch64), not Intel/AMD (x86_64). Standard Conda channels (`defaults`) have limited ARM64 packages.
2. **Python version lock**: NVIDIA only compiles JetPack 6 PyTorch wheels for **Python 3.10** (`cp310`). Our Conda `base` environment was running Python 3.12, making every NVIDIA wheel incompatible.
3. **NVIDIA's server is not a pip index**: NVIDIA hosts `.whl` files at `developer.download.nvidia.com/compute/redist/jp/v60/pytorch/`, but this is a plain file listing, NOT a PEP 503 compliant pip index. Using `pip install torch --index-url <nvidia-url>` silently fails.

### The Solution
1. **Replaced Conda with Miniforge**: Miniforge is functionally identical to Miniconda, but defaults to the `conda-forge` channel which has full ARM64 support.
2. **Created a Python 3.10 environment**: `conda create -n buggy python=3.10` gives us the exact Python version NVIDIA requires.
3. **Direct `.whl` download**: Instead of using `--index-url`, we `wget` the PyTorch wheel file directly from NVIDIA's server and `pip install` the local file.

### Automated Setup
All of this is handled by `setup_jetson_env.sh`. See the script comments for details.

---

## Scripts Status

| Script | Status | Description |
|--------|--------|-------------|
| `00_add_prefixes.py` | ✅ Ready | Rename images with class prefixes |
| `01_process_labels.py` | ✅ Ready | Strip hash prefixes, move orphans |
| `01b_prep_backgrounds.py` | ✅ Ready | Copy background images + create empty labels |
| `start_label_studio.sh` | ✅ Ready | Launch annotation tool |
| `02_augment.py` | ✅ Ready | Perspective + augmentation |
| `03_split_dataset.py` | ✅ Ready | 80/20 train/val split |
| `04_train.py` | ✅ Ready | YOLO11n training |
| `05_export.py` | ✅ Ready | ONNX export |
| `visualize_annotations.py` | ✅ Ready | Draw bboxes on images for visual QA |
| `test_yolo.py` | ✅ Ready | Live webcam inference test |
| `setup_jetson_env.sh` | ✅ Tested | Jetson environment setup (Miniforge + PyTorch) |
| `test_camera.py` | ✅ Ready | Simple OpenCV camera test |
| `jetson/app/main.py` | ⏳ TODO | Jetson inference + follow logic |

---

## Folder Structure

```
phase-2/
├── README.md
├── requirements.txt
├── setup_jetson_env.sh          # Jetson environment setup script
├── test_camera.py               # Simple OpenCV camera test
├── best.pt                      # YOLO weights (gitignored, scp to Jetson)
├── dataset/
│   ├── raw/                     # Original images
│   ├── annotated/               # After Label Studio
│   ├── augmented/               # After augmentation
│   ├── train/                   # Training split
│   ├── val/                     # Validation split
│   ├── data.yaml                # YOLO config
│   └── label_studio_config.xml  # Label Studio config
├── scripts/                     # All pipeline scripts
├── training/runs/               # Training outputs
├── models/                      # Exported models
├── YOLO_testing/                # Live inference test scripts
│   ├── vanilla/                 # Basic YOLO test
│   ├── simple_scaffolding/      # NMS + ghosting
│   └── kalman_histo_scaffolding/ # Advanced: Kalman + color fingerprint
└── jetson/                      # Jetson deployment app (TODO)
```
