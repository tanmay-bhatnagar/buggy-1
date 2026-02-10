#!/usr/bin/env python3
"""
Convert HEIC images to PNG format.

Usage:
  python scripts/convert_heic.py [--dry-run]
"""

import os
import subprocess
import argparse
from pathlib import Path

# Paths relative to script location
SCRIPT_DIR = Path(__file__).parent.resolve()
BASE_DIR = SCRIPT_DIR.parent
RAW_TANMAY_DIR = BASE_DIR / "dataset" / "raw" / "tanmay"
BACKUP_DIR = BASE_DIR / "dataset" / "Tanmay_HEIC_Originals"


def convert_heic_to_png(dry_run: bool = False):
    """Convert all HEIC files to PNG and move originals to backup."""
    
    print("=" * 50)
    print("HEIC to PNG Converter")
    print("=" * 50)
    
    if dry_run:
        print("\n🔍 DRY RUN MODE\n")
    
    # Find all HEIC files
    heic_files = list(RAW_TANMAY_DIR.glob("*.HEIC")) + list(RAW_TANMAY_DIR.glob("*.heic"))
    
    if not heic_files:
        print("✅ No HEIC files found. Nothing to convert.")
        return
    
    print(f"📁 Source: {RAW_TANMAY_DIR}")
    print(f"📁 Backup: {BACKUP_DIR}")
    print(f"🖼️  HEIC files found: {len(heic_files)}")
    print()
    
    # Create backup directory
    if not dry_run:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    
    converted = 0
    errors = 0
    
    for heic_path in sorted(heic_files):
        png_name = heic_path.stem + ".png"
        png_path = RAW_TANMAY_DIR / png_name
        backup_path = BACKUP_DIR / heic_path.name
        
        if dry_run:
            print(f"  📝 Would convert: {heic_path.name} → {png_name}")
            print(f"     Would backup: {heic_path.name} → {BACKUP_DIR.name}/")
            converted += 1
        else:
            try:
                # Use sips (macOS built-in) to convert
                result = subprocess.run(
                    ["sips", "-s", "format", "png", str(heic_path), "--out", str(png_path)],
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0:
                    # Move original to backup
                    heic_path.rename(backup_path)
                    print(f"  ✅ {heic_path.name} → {png_name}")
                    converted += 1
                else:
                    print(f"  ❌ Failed: {heic_path.name} - {result.stderr}")
                    errors += 1
                    
            except Exception as e:
                print(f"  ❌ Error: {heic_path.name} - {e}")
                errors += 1
    
    # Summary
    print()
    print("=" * 50)
    print("Summary:")
    print(f"  Converted: {converted}")
    print(f"  Errors: {errors}")
    
    if not dry_run and converted > 0:
        print(f"\n✅ Originals backed up to: {BACKUP_DIR}")
        print("\n🎉 Conversion complete!")


def main():
    parser = argparse.ArgumentParser(description="Convert HEIC images to PNG")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be done without doing it")
    args = parser.parse_args()
    
    convert_heic_to_png(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
