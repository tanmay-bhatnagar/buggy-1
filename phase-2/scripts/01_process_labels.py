#!/usr/bin/env python3
"""
Process Label Studio YOLO export:
1. Strip hash prefixes from label filenames
2. Remap class IDs to correct order (tanmay=0, other_person=1)
3. Move orphan images and labels to dataset/orphan/ folder

Handles nested folder structure:
  annotated/images/other_person/
  annotated/labels/other_person/

Usage:
  python scripts/01_process_labels.py [--dry-run]
"""

import os
import re
import json
import argparse
from pathlib import Path

# Paths relative to script location
SCRIPT_DIR = Path(__file__).parent.resolve()
BASE_DIR = SCRIPT_DIR.parent
ANNOTATED_DIR = BASE_DIR / "dataset" / "annotated"
ORPHAN_DIR = BASE_DIR / "dataset" / "orphan"

# Expected class order for training
EXPECTED_CLASSES = ["tanmay", "other_person"]


def strip_hash_prefix(filename: str) -> str:
    """
    Remove Label Studio's hash prefix from filename.
    'abc12345-tanmay_001.txt' -> 'tanmay_001.txt'
    """
    pattern = r'^[a-f0-9]{8}-(.+)$'
    match = re.match(pattern, filename, re.IGNORECASE)
    if match:
        return match.group(1)
    return filename


def load_notes_json(annotated_dir: Path) -> dict | None:
    """Load notes.json if it exists to get class mapping."""
    notes_path = annotated_dir / "notes.json"
    if notes_path.exists():
        with open(notes_path, 'r') as f:
            return json.load(f)
    return None


def build_class_remap(notes: dict | None) -> dict:
    """
    Build remap from exported class IDs to expected class IDs.
    Expected: tanmay=0, other_person=1
    """
    if notes is None:
        return {}
    
    remap = {}
    categories = notes.get("categories", [])
    
    for cat in categories:
        exported_id = cat["id"]
        name = cat["name"]
        if name in EXPECTED_CLASSES:
            expected_id = EXPECTED_CLASSES.index(name)
            if exported_id != expected_id:
                remap[exported_id] = expected_id
    
    return remap


def process_subfolder(images_dir: Path, labels_dir: Path, 
                      orphan_images_dir: Path, orphan_labels_dir: Path,
                      class_remap: dict, dry_run: bool = False) -> dict:
    """Process a single subfolder (e.g., other_person or tanmay)."""
    
    stats = {
        "labels_renamed": 0,
        "labels_remapped": 0,
        "orphan_images_moved": 0,
        "orphan_labels_moved": 0,
        "matched": 0,
    }
    
    # Get all image stems (without extension)
    image_stems = {}
    image_files = {}
    if images_dir.exists():
        for f in images_dir.iterdir():
            if f.suffix.lower() in {'.jpg', '.jpeg', '.png', '.webp'}:
                image_stems[f.stem] = f
                image_files[f.stem] = f
    
    # Get all label stems (after stripping hash prefix)
    label_stems = {}
    label_files_map = {}
    if labels_dir.exists():
        for f in labels_dir.glob("*.txt"):
            new_name = strip_hash_prefix(f.name)
            stem = new_name.replace('.txt', '')
            label_stems[stem] = f
            label_files_map[stem] = (f, new_name)
    
    # Process labels: strip hash prefix, remap classes, handle orphans
    for stem, (label_file, new_name) in label_files_map.items():
        old_name = label_file.name
        needs_rename = old_name != new_name
        needs_remap = bool(class_remap)
        
        # Check if matching image exists
        if stem in image_stems:
            # Matched pair - process the label
            stats["matched"] += 1
            
            if dry_run:
                if needs_rename:
                    print(f"  📝 Would rename: {old_name} → {new_name}")
                    stats["labels_renamed"] += 1
            else:
                # Read content
                with open(label_file, 'r') as f:
                    lines = f.readlines()
                
                # Remap classes if needed
                if needs_remap and lines:
                    new_lines = []
                    for line in lines:
                        parts = line.strip().split()
                        if len(parts) >= 5:
                            cls_id = int(parts[0])
                            if cls_id in class_remap:
                                parts[0] = str(class_remap[cls_id])
                            new_lines.append(' '.join(parts) + '\n')
                        else:
                            new_lines.append(line)
                    lines = new_lines
                    stats["labels_remapped"] += 1
                
                # Write to new location (or same if no rename needed)
                new_path = labels_dir / new_name
                if needs_rename:
                    label_file.unlink()
                    stats["labels_renamed"] += 1
                
                with open(new_path, 'w') as f:
                    f.writelines(lines)
        else:
            # Orphan label - move to orphan folder
            if dry_run:
                print(f"  🏷️  Would move orphan label: {old_name}")
            else:
                orphan_labels_dir.mkdir(parents=True, exist_ok=True)
                dest = orphan_labels_dir / old_name
                label_file.rename(dest)
                print(f"  🏷️  Moved orphan label: {old_name}")
            stats["orphan_labels_moved"] += 1
    
    # Find and move orphan images (images without matching labels)
    for stem, img_path in image_files.items():
        if stem not in label_stems:
            if dry_run:
                print(f"  🖼️  Would move orphan image: {img_path.name}")
            else:
                orphan_images_dir.mkdir(parents=True, exist_ok=True)
                dest = orphan_images_dir / img_path.name
                img_path.rename(dest)
                print(f"  🖼️  Moved orphan image: {img_path.name}")
            stats["orphan_images_moved"] += 1
    
    return stats


def process_all(dry_run: bool = False):
    """Process all subfolders in annotated directory."""
    
    print("=" * 50)
    print("Label Processing & Cleanup")
    print("=" * 50)
    
    if dry_run:
        print("\n🔍 DRY RUN MODE\n")
    
    images_base = ANNOTATED_DIR / "images"
    labels_base = ANNOTATED_DIR / "labels"
    
    if not images_base.exists():
        print(f"❌ Images folder not found: {images_base}")
        return
    
    # Load notes.json for class mapping
    notes = load_notes_json(ANNOTATED_DIR)
    class_remap = build_class_remap(notes)
    
    if class_remap:
        print(f"⚠️  Class remapping detected: {class_remap}")
        print(f"   Exported IDs will be remapped to: {EXPECTED_CLASSES}")
        print()
    
    # Process each subfolder
    subfolders = [d for d in images_base.iterdir() if d.is_dir()]
    
    total_stats = {
        "labels_renamed": 0,
        "labels_remapped": 0,
        "orphan_images_moved": 0,
        "orphan_labels_moved": 0,
        "matched": 0,
    }
    
    if not subfolders:
        # Flat structure - process directly
        print("📁 Processing flat structure...")
        orphan_images = ORPHAN_DIR / "images"
        orphan_labels = ORPHAN_DIR / "labels"
        stats = process_subfolder(images_base, labels_base, 
                                  orphan_images, orphan_labels,
                                  class_remap, dry_run)
        total_stats = stats
    else:
        # Nested structure - process each subfolder
        for subfolder in sorted(subfolders):
            folder_name = subfolder.name
            print(f"\n📁 Processing: {folder_name}/")
            
            images_dir = images_base / folder_name
            labels_dir = labels_base / folder_name
            orphan_images = ORPHAN_DIR / "images" / folder_name
            orphan_labels = ORPHAN_DIR / "labels" / folder_name
            
            stats = process_subfolder(images_dir, labels_dir,
                                      orphan_images, orphan_labels,
                                      class_remap, dry_run)
            
            for key in total_stats:
                total_stats[key] += stats[key]
            
            print(f"   ✓ {stats['matched']} matched, {stats['labels_renamed']} renamed, "
                  f"{stats['orphan_images_moved']} orphan images, {stats['orphan_labels_moved']} orphan labels")
    
    # Write corrected classes.txt
    classes_path = ANNOTATED_DIR / "classes.txt"
    if dry_run:
        print(f"\n📋 Would write classes.txt with: {EXPECTED_CLASSES}")
    else:
        with open(classes_path, 'w') as f:
            for cls in EXPECTED_CLASSES:
                f.write(f"{cls}\n")
        print(f"\n📋 Wrote classes.txt: {EXPECTED_CLASSES}")
    
    # Summary
    print("\n" + "=" * 50)
    print("Summary:")
    print(f"  Matched pairs: {total_stats['matched']}")
    print(f"  Labels renamed: {total_stats['labels_renamed']}")
    print(f"  Labels remapped: {total_stats['labels_remapped']}")
    print(f"  Orphan images moved: {total_stats['orphan_images_moved']}")
    print(f"  Orphan labels moved: {total_stats['orphan_labels_moved']}")
    
    if not dry_run:
        print("\n✅ Processing complete!")
        print("\nNext step: python scripts/02_augment.py")


def main():
    parser = argparse.ArgumentParser(description="Process Label Studio export")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be done without doing it")
    args = parser.parse_args()
    
    process_all(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
