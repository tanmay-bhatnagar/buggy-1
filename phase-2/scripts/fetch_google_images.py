#!/usr/bin/env python3
"""
Fetch images from Google Images for dataset collection.
Uses google-images-search library (requires API key setup).

Usage:
    python scripts/fetch_google_images.py --query "person walking" --count 100
    python scripts/fetch_google_images.py --preset other_person --count 100
    python scripts/fetch_google_images.py --preset background --count 50
"""

import argparse
import os
import hashlib
import requests
from pathlib import Path
from urllib.parse import quote_plus
import time
import json
from PIL import Image
import io

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

# ============================================================================
# Simple scraper using requests + parsing (no API key needed)
# ============================================================================

def fetch_image_urls_bing(query: str, count: int = 100) -> list[str]:
    """
    Fetch image URLs from Bing Images (more reliable than Google scraping).
    Returns list of image URLs.
    """
    urls = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    # Bing uses 'first' parameter for pagination (35 per page)
    # filterui:imagesize-large = only large images (>500x500)
    # filterui:photo-photo = only photos (not illustrations)
    for offset in range(0, count, 35):
        search_url = f"https://www.bing.com/images/search?q={quote_plus(query)}&first={offset}&count=35&qft=+filterui:imagesize-large+filterui:photo-photo"
        
        try:
            response = requests.get(search_url, headers=headers, timeout=10)
            response.raise_for_status()
            
            # Extract image URLs from response (simple regex-like parsing)
            html = response.text
            
            # Find murl (media URL) patterns
            import re
            pattern = r'murl&quot;:&quot;(https?://[^&]+?)&quot;'
            matches = re.findall(pattern, html)
            
            for url in matches:
                if url not in urls and len(urls) < count:
                    # Filter for likely image URLs
                    if any(ext in url.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                        urls.append(url)
            
            print(f"  Found {len(urls)} URLs so far...")
            time.sleep(0.5)  # Be nice to servers
            
        except Exception as e:
            print(f"  Warning: Error fetching page {offset}: {e}")
            continue
    
    return urls[:count]


def download_image(url: str, save_path: Path, min_resolution: tuple[int, int] = MIN_RESOLUTION) -> tuple[bool, str]:
    """
    Download a single image. Returns (success, reason).
    Checks minimum resolution before saving.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        # Verify it's an image
        content_type = response.headers.get('content-type', '')
        if 'image' not in content_type:
            return False, "not an image"
        
        # Check image dimensions BEFORE saving
        try:
            img = Image.open(io.BytesIO(response.content))
            width, height = img.size
            if width < min_resolution[0] or height < min_resolution[1]:
                return False, f"too small ({width}x{height})"
        except Exception as e:
            return False, f"can't read image: {e}"
        
        # Verify file is not too small (likely error page)
        if len(response.content) < 5000:  # < 5KB
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
    Fetch images for a single query and save to output directory.
    Returns number of successfully downloaded images.
    """
    print(f"\n{'='*60}")
    print(f"Query: {query}")
    print(f"{'='*60}")
    
    # Create query-specific subdirectory
    safe_query = query.replace(" ", "_").replace("/", "-")[:50]
    query_dir = output_dir / safe_query
    query_dir.mkdir(parents=True, exist_ok=True)
    
    # Fetch URLs
    print(f"Fetching image URLs...")
    urls = fetch_image_urls_bing(query, count)
    print(f"Found {len(urls)} image URLs")
    
    # Download images
    downloaded = 0
    for i, url in enumerate(urls):
        # Create unique filename from URL hash
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        ext = '.jpg'  # Default extension
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
            print(f"  [{downloaded}/{len(urls)}] Downloaded: {filename} ({reason})")
        else:
            print(f"  [SKIP] {reason}: {url[:50]}...")
        
        time.sleep(0.2)  # Rate limiting
    
    print(f"✓ Downloaded {downloaded} images to {query_dir}")
    return downloaded


def main():
    parser = argparse.ArgumentParser(
        description="Fetch images from Bing for dataset collection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single query
  python scripts/fetch_google_images.py --query "person walking" --count 100
  
  # Use preset queries for other_person class
  python scripts/fetch_google_images.py --preset other_person --count 100
  
  # Use preset queries for background class  
  python scripts/fetch_google_images.py --preset background --count 50
  
  # List available presets and their queries
  python scripts/fetch_google_images.py --list-presets
        """
    )
    
    parser.add_argument("--query", "-q", type=str, help="Single search query")
    parser.add_argument("--preset", "-p", type=str, choices=list(QUERIES.keys()),
                        help="Use preset query list (other_person, background)")
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
        parser.error("Either --query or --preset is required. Use --list-presets to see options.")
    
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
    
    # Fetch images
    total_downloaded = 0
    for query in queries:
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
    print("  2. Move good images to dataset/raw/other_person/ or dataset/raw/background/")
    print("  3. Run: python scripts/00_add_prefixes.py")


if __name__ == "__main__":
    main()
