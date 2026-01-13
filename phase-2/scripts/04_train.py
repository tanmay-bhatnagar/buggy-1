#!/usr/bin/env python3
"""
Train YOLO11n model on custom dataset.

Usage:
  python scripts/04_train.py [--epochs 100] [--model yolo11n.pt]
"""

import argparse
from pathlib import Path
from datetime import datetime

# Paths relative to script location
SCRIPT_DIR = Path(__file__).parent.resolve()
BASE_DIR = SCRIPT_DIR.parent
DATA_YAML = BASE_DIR / "dataset" / "data.yaml"
RUNS_DIR = BASE_DIR / "training" / "runs"

# Default training config
DEFAULT_CONFIG = {
    "model": "yolo11n.pt",
    "epochs": 100,
    "imgsz": 640,
    "batch": 16,
    "device": "mps",  # Mac M3 GPU
    "patience": 20,   # Early stopping
    "seed": 1337,
}


def train(
    model: str = DEFAULT_CONFIG["model"],
    epochs: int = DEFAULT_CONFIG["epochs"],
    batch: int = DEFAULT_CONFIG["batch"],
    imgsz: int = DEFAULT_CONFIG["imgsz"],
    device: str = DEFAULT_CONFIG["device"],
    resume: bool = False,
):
    """Train YOLO model."""
    
    # Import here to avoid slow startup for --help
    from ultralytics import YOLO
    
    # Validate data.yaml exists
    if not DATA_YAML.exists():
        print(f"❌ data.yaml not found: {DATA_YAML}")
        print("   Make sure you've run the data pipeline first!")
        return None
    
    print("=" * 50)
    print("YOLO Training")
    print("=" * 50)
    print(f"📦 Model: {model}")
    print(f"📊 Data: {DATA_YAML}")
    print(f"🔄 Epochs: {epochs}")
    print(f"📐 Image size: {imgsz}")
    print(f"📦 Batch size: {batch}")
    print(f"💻 Device: {device}")
    print(f"🎲 Seed: {DEFAULT_CONFIG['seed']}")
    print()
    
    # Create run name with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_name = f"tanmay_detector_{timestamp}"
    
    # Load model
    yolo = YOLO(model)
    
    # Train
    results = yolo.train(
        data=str(DATA_YAML),
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
        device=device,
        patience=DEFAULT_CONFIG["patience"],
        seed=DEFAULT_CONFIG["seed"],
        project=str(RUNS_DIR),
        name=run_name,
        exist_ok=True,
        
        # Augmentation (YOLO built-in)
        hsv_h=0.015,
        hsv_s=0.7,
        hsv_v=0.4,
        degrees=10,
        translate=0.1,
        scale=0.5,
        flipud=0.0,  # No vertical flip
        fliplr=0.5,
        mosaic=1.0,
        mixup=0.1,
        
        # Resume from checkpoint if requested
        resume=resume,
    )
    
    print()
    print("=" * 50)
    print("✅ Training complete!")
    print(f"📁 Results saved to: {RUNS_DIR / run_name}")
    print(f"🏆 Best weights: {RUNS_DIR / run_name / 'weights' / 'best.pt'}")
    print()
    print("Next steps:")
    print(f"  python scripts/05_export.py --weights {RUNS_DIR / run_name / 'weights' / 'best.pt'}")
    
    return results


def main():
    parser = argparse.ArgumentParser(description="Train YOLO model")
    parser.add_argument("--model", "-m", type=str, default=DEFAULT_CONFIG["model"],
                        help=f"Base model (default: {DEFAULT_CONFIG['model']})")
    parser.add_argument("--epochs", "-e", type=int, default=DEFAULT_CONFIG["epochs"],
                        help=f"Number of epochs (default: {DEFAULT_CONFIG['epochs']})")
    parser.add_argument("--batch", "-b", type=int, default=DEFAULT_CONFIG["batch"],
                        help=f"Batch size (default: {DEFAULT_CONFIG['batch']})")
    parser.add_argument("--imgsz", type=int, default=DEFAULT_CONFIG["imgsz"],
                        help=f"Image size (default: {DEFAULT_CONFIG['imgsz']})")
    parser.add_argument("--device", "-d", type=str, default=DEFAULT_CONFIG["device"],
                        help=f"Device: mps, cuda, cpu (default: {DEFAULT_CONFIG['device']})")
    parser.add_argument("--resume", action="store_true",
                        help="Resume training from last checkpoint")
    args = parser.parse_args()
    
    train(
        model=args.model,
        epochs=args.epochs,
        batch=args.batch,
        imgsz=args.imgsz,
        device=args.device,
        resume=args.resume,
    )


if __name__ == "__main__":
    main()
