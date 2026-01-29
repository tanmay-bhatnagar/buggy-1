#!/usr/bin/env python3
"""
Split augmented dataset into train/val sets (80/20).

Usage:
  python scripts/03_split_dataset.py [--dry-run] [--split 0.8]
"""

import os
import random
import argparse
import shutil
from pathlib import Path
from collections import defaultdict

# Set seed for reproducibility
SEED = 1337
random.seed(SEED)

# Paths relative to script location
SCRIPT_DIR = Path(__file__).parent.resolve()
BASE_DIR = SCRIPT_DIR.parent
AUGMENTED_DIR = BASE_DIR / "dataset" / "augmented"
TRAIN_DIR = BASE_DIR / "dataset" / "train"
VAL_DIR = BASE_DIR / "dataset" / "val"


def get_class_from_label(label_path: Path) -> str:
    """Determine class from label file content."""
    if not label_path.exists() or label_path.stat().st_size == 0:
        return "background"
    
    with open(label_path, 'r') as f:
        first_line = f.readline().strip()
        if first_line:
            cls_id = int(first_line.split()[0])
            # Class mapping: tanmay=0, other_person=1 (matches training config)
            return {0: "tanmay", 1: "other_person"}.get(cls_id, "unknown")
    return "background"


def split_dataset(train_ratio: float = 0.8, dry_run: bool = False):
    """Split dataset into train/val with stratification by class."""
    
    input_images = AUGMENTED_DIR / "images"
    input_labels = AUGMENTED_DIR / "labels"
    
    if not input_images.exists():
        print(f"❌ Augmented images not found: {input_images}")
        print(f"   Run 02_augment.py first!")
        return
    
    # Get all images
    image_files = list(input_images.glob("*"))
    image_files = [f for f in image_files if f.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}]
    
    if not image_files:
        print(f"❌ No images found in {input_images}")
        return
    
    # Group by class for stratified split
    by_class = defaultdict(list)
    for img_path in image_files:
        label_path = input_labels / (img_path.stem + ".txt")
        cls = get_class_from_label(label_path)
        by_class[cls].append(img_path)
    
    print("=" * 50)
    print("Dataset Split")
    print("=" * 50)
    print(f"📁 Input: {input_images}")
    print(f"📁 Train output: {TRAIN_DIR}")
    print(f"📁 Val output: {VAL_DIR}")
    print(f"📊 Split ratio: {train_ratio:.0%} train / {1-train_ratio:.0%} val")
    print()
    print("Class distribution:")
    for cls, files in sorted(by_class.items()):
        print(f"  {cls}: {len(files)} images")
    print()
    
    if dry_run:
        print("🔍 DRY RUN - no files will be copied")
        
        for cls, files in sorted(by_class.items()):
            n_train = int(len(files) * train_ratio)
            n_val = len(files) - n_train
            print(f"  {cls}: {n_train} train, {n_val} val")
        return
    
    # Create output directories
    (TRAIN_DIR / "images").mkdir(parents=True, exist_ok=True)
    (TRAIN_DIR / "labels").mkdir(parents=True, exist_ok=True)
    (VAL_DIR / "images").mkdir(parents=True, exist_ok=True)
    (VAL_DIR / "labels").mkdir(parents=True, exist_ok=True)
    
    train_count = 0
    val_count = 0
    
    # Stratified split
    for cls, files in by_class.items():
        random.shuffle(files)
        split_idx = int(len(files) * train_ratio)
        
        train_files = files[:split_idx]
        val_files = files[split_idx:]
        
        # Copy train files
        for img_path in train_files:
            label_path = input_labels / (img_path.stem + ".txt")
            shutil.copy2(img_path, TRAIN_DIR / "images" / img_path.name)
            if label_path.exists():
                shutil.copy2(label_path, TRAIN_DIR / "labels" / label_path.name)
            train_count += 1
        
        # Copy val files
        for img_path in val_files:
            label_path = input_labels / (img_path.stem + ".txt")
            shutil.copy2(img_path, VAL_DIR / "images" / img_path.name)
            if label_path.exists():
                shutil.copy2(label_path, VAL_DIR / "labels" / label_path.name)
            val_count += 1
    
    print("=" * 50)
    print(f"✅ Split complete!")
    print(f"   Train: {train_count} images")
    print(f"   Val: {val_count} images")


def main():
    parser = argparse.ArgumentParser(description="Split dataset into train/val")
    parser.add_argument("--split", "-s", type=float, default=0.8,
                        help="Train split ratio (default: 0.8 = 80%% train)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be done without doing it")
    args = parser.parse_args()
    
    split_dataset(train_ratio=args.split, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
