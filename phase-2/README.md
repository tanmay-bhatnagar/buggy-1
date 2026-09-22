# Phase 2 — Personal YOLO Follow-Me Perception

Phase 2 develops the perception layer for the buggy: a custom YOLO11n detector distinguishes `tanmay` from `other_person`, with a Mac training pipeline, Jetson/TensorRT export tooling, and tracker experiments.

## Status

| Component | Status |
| --- | --- |
| Mac data and training pipeline | Implemented; recorded as tested with MPS training. |
| YOLO11n V1 | Trained and validated on the private project dataset. |
| Jetson/TensorRT export tooling | Implemented; requires local weights and a Jetson runtime. |
| Tracking experiments | Prototype implementations; not a deployed motor-control loop. |
| Closed-loop follow-me control | In progress. |

## Recorded V1 result

The V1 validation snapshot was recorded on 12 February 2026. It uses a private dataset and must not be interpreted as a general-purpose person-recognition benchmark.

| Metric | All classes | `tanmay` | `other_person` |
| --- | ---: | ---: | ---: |
| Validation images / instances | 342 / 550 | 224 / 224 | 164 / 326 |
| Precision | 0.964 | 0.983 | 0.945 |
| Recall | 0.966 | 1.000 | 0.933 |
| mAP50 | 0.979 | 0.995 | 0.964 |
| mAP50-95 | 0.805 | 0.864 | 0.746 |

The recorded dataset contained 426 raw images expanded to 1,704 images after augmentation. Source images, labels, training runs, and weights are intentionally excluded from Git because they are private and/or large.

## Pipeline

```text
private images → Label Studio export → label processing → backgrounds / augmentation
→ train / validation split → YOLO11n training → ONNX or TensorRT export → Jetson experiments
```

## Setup

The scripts target Python with Ultralytics, OpenCV, Albumentations, and Label Studio. On the Mac:

```bash
cd phase-2
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Supply a dataset with this high-level shape (do not commit personal images):

```text
dataset/
  annotated/images/ and annotated/labels/
  backgrounds/
  processed/
  split/
```

## Training workflow

1. Export annotated YOLO labels from Label Studio and place them under the local `dataset/annotated/` tree.
2. Run `scripts/01_process_labels.py`; use `--dry-run` first where offered.
3. Prepare backgrounds with `scripts/01b_prep_backgrounds.py`, then augment with `scripts/02_augment.py`.
4. Create the training split with `scripts/03_split_dataset.py`.
5. Train on an Apple-silicon Mac, for example:

   ```bash
   python scripts/04_train.py --device mps
   ```

6. Export ONNX with `scripts/05_export.py`. TensorRT generation belongs on the target Jetson, using `export_tensorrt.py` or a compatible `trtexec` command.

Inspect each script's CLI help before using it: paths and local data layouts are intentionally not committed as a universal default.

## Label integrity: verify class IDs

Label Studio can assign IDs based on label-interface order rather than the expected mapping. This project expects `tanmay=0` and `other_person=1`. After processing an export, inspect label counts and render a sample before training:

```bash
python scripts/visualize_annotations.py
cat dataset/annotated/labels/tanmay/*.txt | awk '{print $1}' | sort | uniq -c
cat dataset/annotated/labels/other_person/*.txt | awk '{print $1}' | sort | uniq -c
```

Do not train until the visualized boxes and class IDs are correct.

## Jetson and TensorRT

`setup_jetson_env.sh` captures a Jetson setup path for Miniforge, NVIDIA PyTorch, and a Python 3.10 environment. It removes prior Conda installation as part of setup, so inspect it and back up any existing environment before running it. The repository also contains:

- [export_tensorrt.py](export_tensorrt.py) for target-side TensorRT export
- [YOLO testing experiments](YOLO_testing/README.md)
- an experimental [Viam TensorRT vision-service module](../viam-module/jetson-yolo-detector/README.md)

TensorRT engines are hardware- and environment-specific. Build them on the intended Jetson and keep `.pt`, `.onnx`, and `.engine` artifacts outside Git.

## Limitations

- The V1 model can produce duplicate or phantom boxes during rapid motion and can miss extreme poses.
- Validation metrics do not validate safety, identity reliability under every lighting condition, or motor-control integration.
- Tracker variants are research prototypes; their quality and speed depend on camera, model, and tuning choices.

For tracker-specific setups and limitations, start with [YOLO_testing/README.md](YOLO_testing/README.md) and [tracking_readme.md](tracking_readme.md).
