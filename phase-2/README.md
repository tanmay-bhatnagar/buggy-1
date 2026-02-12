# Phase 2: YOLO Follow-Me

Train a custom YOLO model to detect and follow you specifically, deployed on Jetson Orin Nano.

---

## ⚠️ Current Status

| Component | Status |
|-----------|--------|
| **Mac Pipeline** | ✅ Ready & Tested |
| **Model V1** | ✅ Trained & Validated (mAP50: 0.98) |
| **Jetson Pipeline** | ⏳ Pending (deployment testing) |

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
| `01_process_labels.py` | ✅ Ready | Strip hash prefixes, move orphans |
| `01b_prep_backgrounds.py` | ✅ Ready | Copy background images + create empty labels |
| `start_label_studio.sh` | ✅ Ready | Launch annotation tool |
| `02_augment.py` | ✅ Ready | Perspective + augmentation |
| `03_split_dataset.py` | ✅ Ready | 80/20 train/val split |
| `04_train.py` | ✅ Ready | YOLO11n training |
| `05_export.py` | ✅ Ready | ONNX export |
| `visualize_annotations.py` | ✅ Ready | Draw bboxes on images for visual QA |
| `test_yolo.py` | ✅ Ready | Live webcam inference test |
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
