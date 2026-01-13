# Phase 2: YOLO Follow-Me

Train a custom YOLO model to detect and follow you specifically, deployed on Jetson Orin Nano.

## Overview

| Component | Details |
|-----------|---------|
| **Model** | YOLO11n (or YOLOv8n) |
| **Classes** | `tanmay` (0), `other_person` (1) |
| **Training** | Mac M3 (MPS) |
| **Deployment** | Jetson Orin Nano (TensorRT) |

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

### 2.4 Export
1. Export → YOLO format → Download
2. Extract to `dataset/annotated/`
3. Process export:
```bash
python scripts/00b_process_export.py --dry-run  # Preview
python scripts/00b_process_export.py             # Apply
```

### 2.5 Copy Images
Copy your raw images to match the labels:
```bash
# TODO: Script to automate this (01_copy_images.py)
cp dataset/raw/tanmay/*.jpg dataset/annotated/images/
cp dataset/raw/other_person/*.jpg dataset/annotated/images/
```

---

## Step 3: Augmentation

Augment images to simulate buggy-view perspective:
```bash
python scripts/02_augment.py --dry-run
python scripts/02_augment.py
```

**Augmentations applied:**
- Perspective warp (simulate low camera angle)
- Brightness/contrast variation
- Motion blur
- Scale variation

Result: `dataset/augmented/` with 3-5x more images

---

## Step 4: Train/Val Split

Split data 80/20 for training:
```bash
python scripts/03_split_dataset.py
```

Result:
```
dataset/train/images/  # 80% of data
dataset/train/labels/
dataset/val/images/    # 20% of data
dataset/val/labels/
```

---

## Step 5: Training

### 5.1 Configure
Edit `dataset/data.yaml`:
```yaml
path: /path/to/phase-2/dataset
train: train/images
val: val/images
names:
  0: tanmay
  1: other_person
```

### 5.2 Train
```bash
python scripts/04_train.py
# Or directly:
yolo detect train model=yolo11n.pt data=dataset/data.yaml epochs=100 imgsz=640 device=mps
```

Training time: ~10-20 minutes on M3

### 5.3 Evaluate
Check `training/runs/tanmay_detector/`:
- `results.png` - training curves
- `confusion_matrix.png`
- `weights/best.pt` - best model

Target: mAP50 > 0.85

---

## Step 6: Export for Jetson

### 6.1 Export to ONNX (on Mac)
```bash
python scripts/05_export.py
# Creates: models/best.onnx
```

### 6.2 Copy to Jetson
```bash
scp models/best.onnx jetson@<jetson-ip>:~/buggy/phase-2/models/
```

### 6.3 Convert to TensorRT (on Jetson)
```bash
trtexec --onnx=best.onnx --saveEngine=best.engine --fp16
```

---

## Step 7: Deployment

Run on Jetson:
```bash
python jetson/app/main.py --config config/follow.yaml
```

---

## Folder Structure

```
phase-2/
├── README.md                    # This file
├── requirements.txt
├── dataset/
│   ├── raw/                     # Original images
│   │   ├── tanmay/
│   │   ├── other_person/
│   │   └── background/
│   ├── annotated/               # After Label Studio + export processing
│   │   ├── images/
│   │   └── labels/
│   ├── augmented/               # After augmentation
│   │   ├── images/
│   │   └── labels/
│   ├── train/                   # Training split
│   │   ├── images/
│   │   └── labels/
│   ├── val/                     # Validation split
│   │   ├── images/
│   │   └── labels/
│   ├── data.yaml                # YOLO dataset config
│   └── label_studio_config.xml  # Label Studio interface config
├── scripts/
│   ├── 00_add_prefixes.py       # Rename raw images with class prefixes
│   ├── 00b_process_export.py    # Strip hash from Label Studio export
│   ├── 01_copy_images.py        # Copy images to match labels (TODO)
│   ├── 02_augment.py            # Apply augmentations (TODO)
│   ├── 03_split_dataset.py      # Train/val split (TODO)
│   ├── 04_train.py              # Training wrapper (TODO)
│   ├── 05_export.py             # ONNX export (TODO)
│   └── start_label_studio.sh    # Launch Label Studio
├── training/
│   └── runs/                    # Training outputs (auto-generated)
├── models/
│   ├── best.pt                  # Best PyTorch weights
│   ├── best.onnx                # ONNX export
│   └── best.engine              # TensorRT (on Jetson)
└── jetson/
    ├── app/                     # Deployment code (TODO)
    └── config/
```

---

## Scripts Status

| Script | Status | Description |
|--------|--------|-------------|
| `00_add_prefixes.py` | ✅ Ready | Rename images with class prefixes |
| `00b_process_export.py` | ✅ Ready | Process Label Studio export |
| `start_label_studio.sh` | ✅ Ready | Launch annotation tool |
| `01_copy_images.py` | ⬜ TODO | Copy images to annotated/ |
| `02_augment.py` | ⬜ TODO | Perspective + augmentation |
| `03_split_dataset.py` | ⬜ TODO | 80/20 train/val split |
| `04_train.py` | ⬜ TODO | YOLO training |
| `05_export.py` | ⬜ TODO | ONNX export |
