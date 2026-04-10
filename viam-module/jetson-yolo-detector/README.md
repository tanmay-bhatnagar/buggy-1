# jetson-yolo-detector

High-performance YOLO object detection on **NVIDIA Jetson** using **TensorRT**, packaged as a [Viam Vision Service](https://docs.viam.com/operate/reference/services/vision/) module.

> **Why this exists:** Getting YOLO + TensorRT + PyTorch + torchvision working together on a Jetson is painful — mismatched CUDA wheels, 2-hour torchvision compiles, broken TensorRT symlinks. This module handles all of that automatically so you can focus on your robot.

## Requirements

- **Hardware:** NVIDIA Jetson Orin Nano (or any Jetson with JetPack 6.2)
- **Software:** JetPack 6.2, Python 3.10
- **Model:** A YOLO `.engine` file (exported via `yolo export format=engine`)

## Installation

Add this module from the [Viam Registry](https://app.viam.com/module/tanmay-bhatnagar/jetson-yolo-detector):

1. In the [Viam app](https://app.viam.com), go to your machine's **CONFIGURE** tab
2. Click **+** → **Service** → **Vision** → search for `jetson-yolo-detector`
3. Configure your model path (see below)
4. Click **Save**

The first deploy runs `setup.sh` which automatically:
- Installs NVIDIA-optimised PyTorch (from the official JetPack 6.2 index)
- Installs torchvision with CUDA support
- Symlinks system TensorRT libraries into the module's virtualenv

## Configuration

```json
{
  "model_path": "/absolute/path/to/your/best.engine",
  "confidence": 0.5,
  "labels": ["person", "car", "dog"]
}
```

| Attribute | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `model_path` | string | **Yes** | — | Absolute path to your YOLO TensorRT `.engine` file on the Jetson |
| `confidence` | float | No | `0.5` | Minimum detection confidence threshold (0.0–1.0) |
| `labels` | list | No | Model's built-in names | Override class label names |

## Exporting a YOLO model to TensorRT

On your Jetson, with ultralytics installed:

```bash
yolo export model=best.pt format=engine
```

This creates `best.engine` optimised for your specific GPU. Use the absolute path to this file as `model_path`.

For FP16 precision (faster, slightly less accurate):

```bash
yolo export model=best.pt format=engine half=True
```

## API

This module implements the [Viam Vision Service API](https://docs.viam.com/dev/reference/apis/services/vision/):

| Method | Supported | Description |
|--------|-----------|-------------|
| `GetDetections` | ✅ | Returns bounding boxes with class names and confidence scores |
| `GetProperties` | ✅ | Reports that detections are supported |
| `GetClassifications` | ❌ | Not applicable for object detection |
| `GetObjectPointClouds` | ❌ | Requires depth camera |

## Performance

Tested on **Jetson Orin Nano** with a custom YOLOv8n model:

| Metric | Value |
|--------|-------|
| Inference speed | **~60+ FPS** (TensorRT FP32) |
| Camera-limited | 30 FPS (USB camera bottleneck) |
| Model load time | ~3 seconds |

## What `setup.sh` automates

If you've tried running YOLO on a Jetson before, you know the pain. Here's what this module handles for you:

1. **PyTorch** — Installs the correct NVIDIA-compiled wheel from the JetPack 6.2 index (not the broken CPU-only pip version)
2. **torchvision** — Installs the CUDA-enabled build (falls back to source compile if needed)
3. **TensorRT** — Symlinks the system-installed TensorRT Python packages into the module's virtualenv (they ship with JetPack but aren't pip-installable)

## Credits

Built by [Tanmay Bhatnagar](https://twitter.com/imnottanmay) as part of the [Follow-Me Buggy](https://github.com/tbhatnagar/follow-me-buggy) project — an autonomous follow-me robot powered by computer vision on Jetson Orin Nano.
