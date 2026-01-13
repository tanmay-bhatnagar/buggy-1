#!/usr/bin/env python3
"""
Rename images in dataset/raw/ folders with class prefixes.

Before:
  dataset/raw/tanmay/photo1.jpg
  dataset/raw/other_person/img.png
  dataset/raw/background/scene.webp

After:
  dataset/raw/tanmay/tanmay_001.jpg
  dataset/raw/other_person/other_001.png
  dataset/raw/background/bg_001.webp

Usage:
  python scripts/00_add_prefixes.py [--dry-run]
"""

import os
import argparse
from pathlib import Path

# Configuration - Paths relative to script location
SCRIPT_DIR = Path(__file__).parent.resolve()
RAW_DIR = SCRIPT_DIR.parent / "dataset" / "raw"
PREFIXES = {
    "tanmay": "tanmay",
    "other_person": "other",
    "background": "bg"
}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}


def get_images(folder: Path) -> list[Path]:
    """Get all image files in a folder."""
    if not folder.exists():
        return []
    return [f for f in folder.iterdir() 
            if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS]


def rename_files(dry_run: bool = False):
    """Rename all images with class prefixes."""
    
    for class_name, prefix in PREFIXES.items():
        folder = RAW_DIR / class_name
        images = get_images(folder)
        
        if not images:
            print(f"📁 {class_name}/: No images found")
            continue
        
        print(f"\n📁 {class_name}/ ({len(images)} images)")
        
        # Sort for consistent numbering
        images.sort()
        
        for idx, img_path in enumerate(images, start=1):
            ext = img_path.suffix.lower()
            new_name = f"{prefix}_{idx:03d}{ext}"
            new_path = folder / new_name
            
            # Skip if already correctly named
            if img_path.name == new_name:
                print(f"  ✓ {img_path.name} (already correct)")
                continue
            
            # Handle name collision
            if new_path.exists() and new_path != img_path:
                print(f"  ⚠ {img_path.name} → {new_name} (SKIPPED: target exists)")
                continue
            
            if dry_run:
                print(f"  → {img_path.name} → {new_name} (dry-run)")
            else:
                img_path.rename(new_path)
                print(f"  ✓ {img_path.name} → {new_name}")


def main():
    parser = argparse.ArgumentParser(description="Add class prefixes to image filenames")
    parser.add_argument("--dry-run", action="store_true", 
                        help="Show what would be renamed without actually renaming")
    args = parser.parse_args()
    
    print("=" * 50)
    print("Image Prefix Renamer")
    print("=" * 50)
    print(f"Raw folder: {RAW_DIR}")
    
    if args.dry_run:
        print("\n🔍 DRY RUN MODE - No files will be changed\n")
    
    rename_files(dry_run=args.dry_run)
    
    print("\n" + "=" * 50)
    if args.dry_run:
        print("Dry run complete. Run without --dry-run to apply changes.")
    else:
        print("✅ Renaming complete!")


if __name__ == "__main__":
    main()
