#!/usr/bin/env python3
"""
Prepare background (negative) images for training.

Copies background images from dataset/raw/background/ into
dataset/annotated/images/background/ and creates corresponding
empty label files in dataset/annotated/labels/background/.

Empty label files tell YOLO "nothing to detect in this image",
which reduces false positives during inference.

Usage:
  python scripts/01b_prep_backgrounds.py [--dry-run]
"""

import argparse
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
BASE_DIR = SCRIPT_DIR.parent

RAW_BG_DIR = BASE_DIR / "dataset" / "raw" / "background"
ANNOTATED_IMAGES_DIR = BASE_DIR / "dataset" / "annotated" / "images" / "background"
ANNOTATED_LABELS_DIR = BASE_DIR / "dataset" / "annotated" / "labels" / "background"

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".avif"}


def prep_backgrounds(dry_run: bool = False):
    """Copy background images and create empty label files."""

    print("=" * 50)
    print("Prepare Background Images (Negative Examples)")
    print("=" * 50)

    if not RAW_BG_DIR.exists():
        print(f"❌ Raw background folder not found: {RAW_BG_DIR}")
        return

    # Find all image files
    bg_files = sorted([
        f for f in RAW_BG_DIR.iterdir()
        if f.suffix.lower() in IMAGE_EXTENSIONS
    ])

    print(f"📁 Source: {RAW_BG_DIR}")
    print(f"📁 Dest images: {ANNOTATED_IMAGES_DIR}")
    print(f"📁 Dest labels: {ANNOTATED_LABELS_DIR}")
    print(f"🖼️  Background images found: {len(bg_files)}")
    print()

    if not bg_files:
        print("⚠️  No background images found")
        return

    if dry_run:
        print("🔍 DRY RUN - no files will be created")
        for f in bg_files[:5]:
            print(f"  📝 Would copy: {f.name}")
            print(f"     Would create empty label: {f.stem}.txt")
        if len(bg_files) > 5:
            print(f"  ... and {len(bg_files) - 5} more")
        return

    # Create directories
    ANNOTATED_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    ANNOTATED_LABELS_DIR.mkdir(parents=True, exist_ok=True)

    copied = 0
    skipped = 0

    for bg_path in bg_files:
        dest_img = ANNOTATED_IMAGES_DIR / bg_path.name
        dest_label = ANNOTATED_LABELS_DIR / f"{bg_path.stem}.txt"

        # Skip if already exists
        if dest_img.exists():
            skipped += 1
            continue

        # Copy image
        import shutil
        shutil.copy2(bg_path, dest_img)

        # Create empty label file (= no objects to detect)
        dest_label.touch()

        copied += 1

    print(f"✅ Copied {copied} background images")
    if skipped:
        print(f"⏭️  Skipped {skipped} (already exist)")
    print(f"📝 Created {copied} empty label files")

    print()
    print("=" * 50)
    print(f"Total background images in annotated: "
          f"{len(list(ANNOTATED_IMAGES_DIR.glob('*')))}")
    print("=" * 50)


def main():
    parser = argparse.ArgumentParser(
        description="Prepare background images as negative examples"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be done without doing it")
    args = parser.parse_args()

    prep_backgrounds(dry_run=args.dry_run)

    if not args.dry_run:
        print()
        print("Next step: python scripts/02_augment.py")


if __name__ == "__main__":
    main()
