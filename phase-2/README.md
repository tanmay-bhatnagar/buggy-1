# Phase 2: YOLO Follow-Me

Train a custom YOLO model to detect and follow you specifically, deployed on Jetson Orin Nano.

---

## ⚠️ Current Status

| Component | Status |
|-----------|--------|
| **Mac Pipeline** | ✅ Ready (Not Tested) |
| **Jetson Pipeline** | ⏳ Pending (awaiting model weights) |

---

## Overview

| Component | Details |
|-----------|---------|
| **Model** | YOLO11n |
| **Classes** | `tanmay` (0), `other_person` (1) |
| **Training** | Mac M3 (MPS) |
| **Deployment** | Jetson Orin Nano (TensorRT) |

---

## ⚠️ Important: Class Order

> [!CAUTION]
> **Label Studio exports classes in alphabetical order**, which differs from our expected order.
> 
> | Source | Order |
> |--------|-------|
> | Label Studio export | `other_person=0`, `tanmay=1` |
> | Our `data.yaml` | `tanmay=0`, `other_person=1` |
> 
> **The `00b_process_export.py` script automatically fixes this** by:
> 1. Detecting the mismatch
> 2. Remapping class IDs in all label files
> 3. Writing a corrected `classes.txt`
> 
> **Always run `00b_process_export.py` after exporting from Label Studio!**

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
# Export from Label Studio → YOLO format → extract to dataset/annotated/

# CRITICAL: Process export (fixes class order!)
python scripts/00b_process_export.py --dry-run  # Preview
python scripts/00b_process_export.py             # Apply
```

### 2.5 Copy Images
Copy your raw images to match the labels:
```bash
cp dataset/raw/tanmay/*.jpg dataset/annotated/images/
cp dataset/raw/other_person/*.jpg dataset/annotated/images/
cp dataset/raw/background/*.jpg dataset/annotated/images/
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

## Step 7: Jetson Deployment (TODO)

```bash
# Copy to Jetson
scp models/best.onnx jetson@<ip>:~/buggy/models/

# Convert to TensorRT (on Jetson)
trtexec --onnx=best.onnx --saveEngine=best.engine --fp16

# Run (TODO: jetson app not yet created)
python jetson/app/main.py
```

---

## Scripts Status

| Script | Status | Description |
|--------|--------|-------------|
| `00_add_prefixes.py` | ✅ Ready | Rename images with class prefixes |
| `00b_process_export.py` | ✅ Ready | Process Label Studio export (fixes class order!) |
| `start_label_studio.sh` | ✅ Ready | Launch annotation tool |
| `02_augment.py` | ✅ Ready | Perspective + augmentation |
| `03_split_dataset.py` | ✅ Ready | 80/20 train/val split |
| `04_train.py` | ✅ Ready | YOLO11n training |
| `05_export.py` | ✅ Ready | ONNX export |
| `jetson/app/main.py` | ⏳ TODO | Jetson inference + follow logic |

---

## Folder Structure

```
phase-2/
├── README.md
├── requirements.txt
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
└── jetson/                      # Jetson deployment (TODO)
```
