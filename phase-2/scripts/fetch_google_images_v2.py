#!/usr/bin/env python3
"""
Fetch images using duckduckgo_search library.
This library handles rate limiting and token management automatically.

Usage:
    python scripts/fetch_google_images_v2.py --query "person walking" --count 100
    python scripts/fetch_google_images_v2.py --preset other_person --count 100
"""

import argparse
import os
import hashlib
import requests
import time
from pathlib import Path
from PIL import Image
import io

from duckduckgo_search import DDGS

# Default minimum resolution (width, height)
MIN_RESOLUTION = (640, 480)

# ============================================================================
# PRESET QUERIES - Curated for YOLO training
# ============================================================================

QUERIES = {
    "other_person": [
        # Multiple people (great for more labels per image)
        "group of people walking street",
        "friends walking together outdoors",
        "pedestrians on sidewalk",
        "people walking in park",
        "crowd of people walking",
        "coworkers walking together",
        
        # Single person variety
        "person walking full body",
        "man walking outdoors",
        "woman walking sidewalk", 
        "person standing full body photo",
        "pedestrian crossing street",
        
        # Different angles
        "person walking from behind",
        "person side view walking",
        "person walking towards camera",
        
        # Varied settings (match deployment environment)
        "person in hallway",
        "person walking in parking lot",
        "person in backyard",
        "person walking driveway",
        
        # Clothing/appearance variety
        "person casual clothes walking",
        "person wearing jacket outdoors",
        "person with backpack walking",
    ]
}


def download_image(url: str, save_path: Path, min_resolution: tuple[int, int] = MIN_RESOLUTION) -> tuple[bool, str]:
    """
    Download a single image. Returns (success, reason).
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        # Check image dimensions BEFORE saving
        try:
            img = Image.open(io.BytesIO(response.content))
            width, height = img.size
            if width < min_resolution[0] or height < min_resolution[1]:
                return False, f"too small ({width}x{height})"
        except Exception as e:
            return False, f"can't read image"
        
        # Verify file is not too small
        if len(response.content) < 5000:
            return False, "file too small"
        
        # Save image
        with open(save_path, 'wb') as f:
            f.write(response.content)
            
        return True, f"{width}x{height}"
        
    except Exception as e:
        if save_path.exists():
            save_path.unlink()
        return False, str(e)[:30]


def fetch_images_for_query(query: str, output_dir: Path, count: int = 100) -> int:
    """
    Fetch images for a single query using duckduckgo_search library.
    Returns number of successfully downloaded images.
    """
    print(f"\n{'='*60}")
    print(f"Query: {query}")
    print(f"{'='*60}")
    
    # Create query-specific subdirectory
    safe_query = query.replace(" ", "_").replace("/", "-")[:50]
    query_dir = output_dir / safe_query
    query_dir.mkdir(parents=True, exist_ok=True)
    
    # Use duckduckgo_search library
    print(f"Searching DuckDuckGo Images...")
    
    try:
        with DDGS() as ddgs:
            # Get images - size:Large for high resolution
            results = list(ddgs.images(
                keywords=query,
                max_results=count,
                size="Large",
                type_image="photo",
            ))
        print(f"Found {len(results)} image URLs")
    except Exception as e:
        print(f"Error searching: {e}")
        return 0
    
    if not results:
        print("  No results found, skipping...")
        return 0
    
    # Download images
    downloaded = 0
    for i, result in enumerate(results):
        url = result.get('image')
        if not url:
            continue
            
        # Create unique filename
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        ext = '.jpg'
        for e in ['.png', '.jpeg', '.webp']:
            if e in url.lower():
                ext = e
                break
        
        filename = f"{safe_query}_{i:03d}_{url_hash}{ext}"
        save_path = query_dir / filename
        
        if save_path.exists():
            downloaded += 1
            continue
        
        success, reason = download_image(url, save_path)
        if success:
            downloaded += 1
            print(f"  [{downloaded}/{len(results)}] Downloaded: {filename} ({reason})")
        else:
            print(f"  [SKIP] {reason}")
        
        time.sleep(0.15)  # Small delay between downloads
    
    print(f"✓ Downloaded {downloaded} images to {query_dir}")
    return downloaded


def main():
    parser = argparse.ArgumentParser(
        description="Fetch images from DuckDuckGo Images",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single query
  python scripts/fetch_google_images_v2.py --query "person walking" --count 100
  
  # Use preset queries for other_person class
  python scripts/fetch_google_images_v2.py --preset other_person --count 100
  
  # List available presets
  python scripts/fetch_google_images_v2.py --list-presets
        """
    )
    
    parser.add_argument("--query", "-q", type=str, help="Single search query")
    parser.add_argument("--preset", "-p", type=str, choices=list(QUERIES.keys()),
                        help="Use preset query list (other_person)")
    parser.add_argument("--count", "-c", type=int, default=100,
                        help="Number of images per query (default: 100)")
    parser.add_argument("--output", "-o", type=str, 
                        help="Output directory (default: dataset/raw/<preset or 'custom'>)")
    parser.add_argument("--list-presets", action="store_true",
                        help="List all preset queries and exit")
    
    args = parser.parse_args()
    
    # List presets
    if args.list_presets:
        print("\n" + "="*60)
        print("AVAILABLE PRESETS")
        print("="*60)
        for preset_name, queries in QUERIES.items():
            print(f"\n[{preset_name}] - {len(queries)} queries:")
            for q in queries:
                print(f"  • {q}")
        return
    
    # Validate args
    if not args.query and not args.preset:
        parser.error("Either --query or --preset is required.")
    
    # Determine output directory
    script_dir = Path(__file__).parent.parent
    if args.output:
        output_dir = Path(args.output)
    elif args.preset:
        output_dir = script_dir / "dataset" / "raw" / args.preset
    else:
        output_dir = script_dir / "dataset" / "raw" / "custom"
    
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"\nOutput directory: {output_dir}")
    
    # Collect queries
    if args.preset:
        queries = QUERIES[args.preset]
        print(f"Using preset '{args.preset}' with {len(queries)} queries")
    else:
        queries = [args.query]
    
    # Fetch images (with delay between queries to avoid rate limiting)
    total_downloaded = 0
    for i, query in enumerate(queries):
        if i > 0:
            print(f"\n⏳ Waiting 3 seconds before next query...")
            time.sleep(3)  # Delay between queries
        count = fetch_images_for_query(query, output_dir, args.count)
        total_downloaded += count
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Total queries: {len(queries)}")
    print(f"Total images downloaded: {total_downloaded}")
    print(f"Output directory: {output_dir}")
    print("\nNext steps:")
    print("  1. Review and delete unwanted images")
    print("  2. Move good images to dataset/raw/other_person/")
    print("  3. Run: python scripts/00_add_prefixes.py")


if __name__ == "__main__":
    main()
