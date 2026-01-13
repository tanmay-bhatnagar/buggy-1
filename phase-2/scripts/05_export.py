#!/usr/bin/env python3
"""
Export trained YOLO model to ONNX format for Jetson deployment.

Usage:
  python scripts/05_export.py [--weights path/to/best.pt]
  
On Jetson (after copying ONNX file):
  trtexec --onnx=best.onnx --saveEngine=best.engine --fp16
"""

import argparse
import glob
from pathlib import Path

# Paths relative to script location
SCRIPT_DIR = Path(__file__).parent.resolve()
BASE_DIR = SCRIPT_DIR.parent
RUNS_DIR = BASE_DIR / "training" / "runs"
MODELS_DIR = BASE_DIR / "models"


def find_latest_weights() -> Path | None:
    """Find the most recent best.pt from training runs."""
    weight_files = list(RUNS_DIR.glob("*/weights/best.pt"))
    if not weight_files:
        return None
    # Sort by modification time, newest first
    weight_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    return weight_files[0]


def export_model(weights: Path, export_format: str = "onnx", imgsz: int = 640):
    """Export model to specified format."""
    
    from ultralytics import YOLO
    
    print("=" * 50)
    print("Model Export")
    print("=" * 50)
    print(f"📦 Weights: {weights}")
    print(f"📤 Format: {export_format}")
    print(f"📐 Image size: {imgsz}")
    print()
    
    # Load model
    model = YOLO(str(weights))
    
    # Export
    export_path = model.export(
        format=export_format,
        imgsz=imgsz,
        simplify=True,
        opset=12,
    )
    
    # Copy to models directory
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    export_file = Path(export_path)
    final_path = MODELS_DIR / f"best.{export_format}"
    
    import shutil
    shutil.copy2(export_file, final_path)
    
    print()
    print("=" * 50)
    print("✅ Export complete!")
    print(f"📁 Exported to: {final_path}")
    print()
    print("Next steps for Jetson deployment:")
    print(f"  1. Copy to Jetson:")
    print(f"     scp {final_path} jetson@<jetson-ip>:~/buggy/models/")
    print()
    print(f"  2. Convert to TensorRT (on Jetson):")
    print(f"     trtexec --onnx=best.onnx --saveEngine=best.engine --fp16")
    
    return final_path


def main():
    parser = argparse.ArgumentParser(description="Export YOLO model for deployment")
    parser.add_argument("--weights", "-w", type=Path, default=None,
                        help="Path to weights file (default: auto-detect latest)")
    parser.add_argument("--format", "-f", type=str, default="onnx",
                        choices=["onnx", "engine", "torchscript"],
                        help="Export format (default: onnx)")
    parser.add_argument("--imgsz", type=int, default=640,
                        help="Image size (default: 640)")
    args = parser.parse_args()
    
    # Auto-detect weights if not specified
    if args.weights is None:
        args.weights = find_latest_weights()
        if args.weights is None:
            print("❌ No trained weights found!")
            print("   Run 04_train.py first, or specify --weights path")
            return
        print(f"🔍 Auto-detected: {args.weights}")
    
    if not args.weights.exists():
        print(f"❌ Weights not found: {args.weights}")
        return
    
    export_model(args.weights, args.format, args.imgsz)


if __name__ == "__main__":
    main()
