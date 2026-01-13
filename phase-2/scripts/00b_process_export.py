#!/usr/bin/env python3
"""
Process Label Studio YOLO export: strip hash prefixes from label filenames.

Before (Label Studio export):
  labels/abc123-tanmay_001.txt
  
After:
  labels/tanmay_001.txt

Usage:
  python scripts/00b_process_export.py [export_folder] [--dry-run]
  
Example:
  python scripts/00b_process_export.py
  python scripts/00b_process_export.py dataset/annotated/project-2-at-2026-01-13-21-16-0050a933
"""

import os
import re
import shutil
import argparse
from pathlib import Path

# Paths relative to script location
SCRIPT_DIR = Path(__file__).parent.resolve()
BASE_DIR = SCRIPT_DIR.parent
ANNOTATED_DIR = BASE_DIR / "dataset" / "annotated"
# Output goes into annotated/ with clean names (images + labels subfolders)
DEFAULT_OUTPUT = ANNOTATED_DIR


def strip_hash_prefix(filename: str) -> str:
    """
    Remove Label Studio's hash prefix from filename.
    'abc123-tanmay_001.txt' -> 'tanmay_001.txt'
    """
    # Pattern: 8 hex chars + hyphen at start
    pattern = r'^[a-f0-9]{8}-(.+)$'
    match = re.match(pattern, filename, re.IGNORECASE)
    if match:
        return match.group(1)
    return filename


def find_latest_export() -> Path | None:
    """Find the most recent Label Studio export folder."""
    if not ANNOTATED_DIR.exists():
        return None
    
    exports = [d for d in ANNOTATED_DIR.iterdir() if d.is_dir() and d.name.startswith("project-")]
    if not exports:
        return None
    
    # Sort by modification time, newest first
    exports.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    return exports[0]


def process_export(export_folder: Path, output_folder: Path, dry_run: bool = False):
    """Process Label Studio export folder."""
    
    labels_dir = export_folder / "labels"
    classes_file = export_folder / "classes.txt"
    
    if not labels_dir.exists():
        print(f"❌ Labels folder not found: {labels_dir}")
        return False
    
    output_labels = output_folder / "labels"
    output_images = output_folder / "images"
    
    if not dry_run:
        output_labels.mkdir(parents=True, exist_ok=True)
        output_images.mkdir(parents=True, exist_ok=True)
    
    # CRITICAL: Check class order and build remap if needed
    # Expected order: tanmay=0, other_person=1
    expected_order = ["tanmay", "other_person"]
    remap = None
    
    if classes_file.exists():
        with open(classes_file, 'r') as f:
            exported_classes = [line.strip() for line in f if line.strip()]
        
        if exported_classes != expected_order:
            print(f"⚠️  Class order mismatch detected!")
            print(f"    Label Studio: {exported_classes}")
            print(f"    Expected:     {expected_order}")
            
            # Build remap: exported_idx -> correct_idx
            remap = {}
            for exp_idx, cls_name in enumerate(exported_classes):
                if cls_name in expected_order:
                    correct_idx = expected_order.index(cls_name)
                    if exp_idx != correct_idx:
                        remap[exp_idx] = correct_idx
            
            if remap:
                print(f"    Remapping: {remap}")
            print()
        else:
            print(f"✅ Class order correct: {exported_classes}")
        
        if dry_run:
            print(f"📋 Would copy classes.txt → {output_folder}/classes.txt")
        else:
            # Write corrected classes.txt
            with open(output_folder / "classes.txt", 'w') as f:
                for cls in expected_order:
                    f.write(f"{cls}\n")
            print(f"📋 Wrote corrected classes.txt")
    
    # Process label files
    label_files = list(labels_dir.glob("*.txt"))
    print(f"\n📁 Processing {len(label_files)} label files...")
    
    for label_file in sorted(label_files):
        old_name = label_file.name
        new_name = strip_hash_prefix(old_name)
        
        if dry_run:
            print(f"  → {old_name} → {new_name}")
        else:
            # Read, remap if needed, and write
            if remap:
                with open(label_file, 'r') as f:
                    lines = f.readlines()
                
                remapped_lines = []
                for line in lines:
                    parts = line.strip().split()
                    if len(parts) >= 5:
                        cls_id = int(parts[0])
                        if cls_id in remap:
                            parts[0] = str(remap[cls_id])
                        remapped_lines.append(' '.join(parts) + '\n')
                
                with open(output_labels / new_name, 'w') as f:
                    f.writelines(remapped_lines)
            else:
                shutil.copy2(label_file, output_labels / new_name)
            
            print(f"  ✓ {old_name} → {new_name}")
    
    return True


def main():
    parser = argparse.ArgumentParser(description="Process Label Studio YOLO export")
    parser.add_argument("export_folder", type=Path, nargs="?", default=None,
                        help="Path to Label Studio export folder (default: auto-detect latest)")
    parser.add_argument("--output", "-o", type=Path, default=DEFAULT_OUTPUT,
                        help=f"Output folder (default: {DEFAULT_OUTPUT})")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be done without doing it")
    args = parser.parse_args()
    
    # Auto-detect export folder if not provided
    if args.export_folder is None:
        args.export_folder = find_latest_export()
        if args.export_folder is None:
            print(f"❌ No export folders found in: {ANNOTATED_DIR}")
            return
        print(f"🔍 Auto-detected latest export: {args.export_folder.name}")
    
    if not args.export_folder.exists():
        print(f"❌ Export folder not found: {args.export_folder}")
        return
    
    print("=" * 50)
    print("Label Studio Export Processor")
    print("=" * 50)
    print(f"Input:  {args.export_folder}")
    print(f"Output: {args.output}")
    
    if args.dry_run:
        print("\n🔍 DRY RUN MODE\n")
    
    success = process_export(args.export_folder, args.output, args.dry_run)
    
    print("\n" + "=" * 50)
    if success:
        if args.dry_run:
            print("Dry run complete.")
        else:
            print("✅ Export processed!")
            print(f"\nNext steps:")
            print(f"  1. Copy your images to: {args.output}/images/")
            print(f"  2. Ensure image names match label names (without .txt)")
    else:
        print("❌ Processing failed")


if __name__ == "__main__":
    main()
