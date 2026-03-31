#!/usr/bin/env python3
"""
Export YOLO .pt weights to TensorRT .engine for Jetson deployment.

Usage:
    python3 export_tensorrt.py --weights best.pt --precision fp32
    python3 export_tensorrt.py --weights best.pt --precision fp16
    python3 export_tensorrt.py --weights best.pt --precision int8
    python3 export_tensorrt.py --help
"""

import argparse
import sys
from pathlib import Path

PRECISION_INFO = {
    "fp32": {
        "half": False,
        "int8": False,
        "description": "Full 32-bit floating point. Maximum accuracy, no loss whatsoever. Slowest of the three.",
    },
    "fp16": {
        "half": True,
        "int8": False,
        "description": "Half 16-bit floating point. Negligible accuracy loss (<0.1% mAP typical). ~2x faster than FP32. Recommended for most use cases.",
    },
    "int8": {
        "half": False,
        "int8": True,
        "description": "8-bit integer quantization. Small accuracy loss (~0.5-1% mAP typical). ~4x faster than FP32. Requires calibration data.",
    },
}


class PrecisionHelpAction(argparse.Action):
    """Custom action to print detailed precision info when --precision help is used."""
    def __call__(self, parser, namespace, values, option_string=None):
        if values == "help":
            print("\n=== TensorRT Precision Options (Max → Min Accuracy) ===\n")
            for i, (name, info) in enumerate(PRECISION_INFO.items(), 1):
                print(f"  {i}. {name.upper()}")
                print(f"     {info['description']}")
                print()
            print("Usage example: python3 export_tensorrt.py --weights best.pt --precision fp32")
            sys.exit(0)
        setattr(namespace, self.dest, values)


def main():
    parser = argparse.ArgumentParser(
        description="Export YOLO .pt weights to TensorRT .engine for Jetson deployment.",
        epilog="Use '--precision help' for detailed info on each precision level.",
    )
    parser.add_argument(
        "--weights",
        type=str,
        required=True,
        help="Path to the .pt weights file (e.g. best.pt)",
    )
    parser.add_argument(
        "--precision",
        type=str,
        default="fp32",
        action=PrecisionHelpAction,
        choices=list(PRECISION_INFO.keys()) + ["help"],
        help="Precision level: fp32 (max accuracy), fp16 (balanced), int8 (max speed). Use 'help' for details.",
    )
    parser.add_argument(
        "--imgsz",
        type=int,
        default=640,
        help="Input image size for the engine (default: 640)",
    )

    args = parser.parse_args()

    weights_path = Path(args.weights)
    if not weights_path.exists():
        print(f"❌ Weights not found: {args.weights}")
        sys.exit(1)

    precision = PRECISION_INFO[args.precision]

    print("=" * 50)
    print("  YOLO → TensorRT Export")
    print("=" * 50)
    print(f"  Weights:   {args.weights}")
    print(f"  Precision: {args.precision.upper()}")
    print(f"  Image Size: {args.imgsz}x{args.imgsz}")
    print(f"  Info: {precision['description']}")
    print("=" * 50)
    print()

    from ultralytics import YOLO

    model = YOLO(str(weights_path))

    print("🚀 Starting TensorRT export (this may take 2-5 minutes)...")
    export_path = model.export(
        format="engine",
        half=precision["half"],
        int8=precision["int8"],
        imgsz=args.imgsz,
    )

    print()
    print("=" * 50)
    print("  ✅ Export Complete!")
    print(f"  Engine saved to: {export_path}")
    print()
    print("  To test, run:")
    print(f"  python3 kalman_histo.py --weights {export_path}")
    print("=" * 50)


if __name__ == "__main__":
    main()
