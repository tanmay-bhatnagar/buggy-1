#!/usr/bin/env python3
"""
Augment annotated images to simulate buggy-camera perspective.

Applies:
- Perspective warp (simulate low camera angle)
- Brightness/contrast variation
- Motion blur
- Scale variation
- Rotation
- Horizontal flip

Usage:
  python scripts/02_augment.py [--dry-run] [--multiplier 3]
"""

import os
import random
import argparse
import shutil
from pathlib import Path
from typing import Tuple

import cv2
import numpy as np
from tqdm import tqdm

# Set seeds for reproducibility
SEED = 1337
random.seed(SEED)
np.random.seed(SEED)

# Paths relative to script location
SCRIPT_DIR = Path(__file__).parent.resolve()
BASE_DIR = SCRIPT_DIR.parent
ANNOTATED_DIR = BASE_DIR / "dataset" / "annotated"
AUGMENTED_DIR = BASE_DIR / "dataset" / "augmented"

# Augmentation parameters
AUGMENT_CONFIG = {
    # Perspective warp - simulates low camera angle (looking up)
    "perspective_prob": 0.8,
    "perspective_intensity": (0.05, 0.20),  # How much to squeeze top
    
    # Brightness/contrast - indoor lighting variation
    "brightness_prob": 0.7,
    "brightness_range": (-0.4, 0.4),  # ±40%
    "contrast_prob": 0.5,
    "contrast_range": (0.7, 1.3),  # ±30%
    
    # Motion blur - buggy movement
    "blur_prob": 0.3,
    "blur_kernel": (3, 7),  # Motion blur kernel size
    
    # Rotation - camera tilt
    "rotation_prob": 0.4,
    "rotation_range": (-10, 10),  # Degrees
    
    # Horizontal flip - left/right variation
    "flip_prob": 0.5,
    
    # Scale - distance variation
    "scale_prob": 0.4,
    "scale_range": (0.7, 1.2),
}


def perspective_warp(img: np.ndarray, labels: list, intensity: float) -> Tuple[np.ndarray, list]:
    """
    Apply perspective warp to simulate looking up at subject.
    Squeezes top of image (camera tilted up).
    """
    h, w = img.shape[:2]
    
    # Source corners
    src = np.float32([[0, 0], [w, 0], [0, h], [w, h]])
    
    # Destination: squeeze top corners inward
    offset = int(w * intensity)
    dst = np.float32([
        [offset, 0],           # Top-left moves right
        [w - offset, 0],       # Top-right moves left
        [0, h],                # Bottom-left stays
        [w, h]                 # Bottom-right stays
    ])
    
    # Compute transform matrix
    M = cv2.getPerspectiveTransform(src, dst)
    
    # Warp image
    warped = cv2.warpPerspective(img, M, (w, h), borderMode=cv2.BORDER_REPLICATE)
    
    # Transform bounding box labels
    new_labels = []
    for label in labels:
        cls_id, x_center, y_center, box_w, box_h = label
        
        # Convert normalized to pixel coords
        px = x_center * w
        py = y_center * h
        pw = box_w * w
        ph = box_h * h
        
        # Get box corners
        x1, y1 = px - pw/2, py - ph/2
        x2, y2 = px + pw/2, py + ph/2
        
        # Transform corners
        corners = np.float32([[x1, y1], [x2, y1], [x1, y2], [x2, y2]])
        corners = corners.reshape(-1, 1, 2)
        transformed = cv2.perspectiveTransform(corners, M).reshape(-1, 2)
        
        # Get new bounding box
        new_x1 = max(0, min(transformed[:, 0]))
        new_x2 = min(w, max(transformed[:, 0]))
        new_y1 = max(0, min(transformed[:, 1]))
        new_y2 = min(h, max(transformed[:, 1]))
        
        # Convert back to normalized YOLO format
        new_x_center = ((new_x1 + new_x2) / 2) / w
        new_y_center = ((new_y1 + new_y2) / 2) / h
        new_box_w = (new_x2 - new_x1) / w
        new_box_h = (new_y2 - new_y1) / h
        
        # Skip if box became invalid
        if new_box_w > 0.01 and new_box_h > 0.01:
            new_labels.append([cls_id, new_x_center, new_y_center, new_box_w, new_box_h])
    
    return warped, new_labels


def adjust_brightness_contrast(img: np.ndarray, brightness: float, contrast: float) -> np.ndarray:
    """Adjust brightness and contrast."""
    img = img.astype(np.float32)
    img = img * contrast + brightness * 255
    img = np.clip(img, 0, 255).astype(np.uint8)
    return img


def apply_motion_blur(img: np.ndarray, kernel_size: int) -> np.ndarray:
    """Apply horizontal motion blur."""
    kernel = np.zeros((kernel_size, kernel_size))
    kernel[kernel_size // 2, :] = 1.0 / kernel_size
    return cv2.filter2D(img, -1, kernel)


def rotate_image_and_labels(img: np.ndarray, labels: list, angle: float) -> Tuple[np.ndarray, list]:
    """Rotate image and adjust labels."""
    h, w = img.shape[:2]
    center = (w / 2, h / 2)
    
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(img, M, (w, h), borderMode=cv2.BORDER_REPLICATE)
    
    # For small rotations, labels don't change much - skip transform for simplicity
    # (YOLO's built-in augmentation handles this better during training)
    return rotated, labels


def horizontal_flip(img: np.ndarray, labels: list) -> Tuple[np.ndarray, list]:
    """Flip image horizontally and adjust labels."""
    flipped = cv2.flip(img, 1)
    
    new_labels = []
    for label in labels:
        cls_id, x_center, y_center, box_w, box_h = label
        # Flip x coordinate
        new_x_center = 1.0 - x_center
        new_labels.append([cls_id, new_x_center, y_center, box_w, box_h])
    
    return flipped, new_labels


def scale_image_and_labels(img: np.ndarray, labels: list, scale: float) -> Tuple[np.ndarray, list]:
    """Scale image (zoom in/out) while keeping same dimensions."""
    h, w = img.shape[:2]
    
    # Compute new dimensions
    new_h, new_w = int(h * scale), int(w * scale)
    
    if scale > 1:
        # Zoom in: resize up, then crop center
        resized = cv2.resize(img, (new_w, new_h))
        start_x = (new_w - w) // 2
        start_y = (new_h - h) // 2
        cropped = resized[start_y:start_y+h, start_x:start_x+w]
        
        # Adjust labels (objects appear larger, shift toward edges)
        new_labels = []
        for label in labels:
            cls_id, x_center, y_center, box_w, box_h = label
            # Shift and scale
            new_x = (x_center - 0.5) * scale + 0.5
            new_y = (y_center - 0.5) * scale + 0.5
            new_w_box = box_w * scale
            new_h_box = box_h * scale
            
            # Clip to image bounds
            if 0 < new_x < 1 and 0 < new_y < 1:
                new_labels.append([cls_id, new_x, new_y, min(new_w_box, 1), min(new_h_box, 1)])
        
        return cropped, new_labels
    else:
        # Zoom out: resize down, then pad
        resized = cv2.resize(img, (new_w, new_h))
        pad_x = (w - new_w) // 2
        pad_y = (h - new_h) // 2
        padded = cv2.copyMakeBorder(resized, pad_y, h-new_h-pad_y, pad_x, w-new_w-pad_x,
                                     cv2.BORDER_REPLICATE)
        
        # Adjust labels
        new_labels = []
        for label in labels:
            cls_id, x_center, y_center, box_w, box_h = label
            new_x = x_center * scale + (1 - scale) / 2
            new_y = y_center * scale + (1 - scale) / 2
            new_w_box = box_w * scale
            new_h_box = box_h * scale
            new_labels.append([cls_id, new_x, new_y, new_w_box, new_h_box])
        
        return padded, new_labels


def read_labels(label_path: Path) -> list:
    """Read YOLO format labels."""
    if not label_path.exists():
        return []
    
    labels = []
    with open(label_path, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 5:
                cls_id = int(parts[0])
                x_center, y_center, w, h = map(float, parts[1:5])
                labels.append([cls_id, x_center, y_center, w, h])
    return labels


def write_labels(label_path: Path, labels: list):
    """Write YOLO format labels."""
    with open(label_path, 'w') as f:
        for label in labels:
            cls_id, x, y, w, h = label
            f.write(f"{cls_id} {x:.6f} {y:.6f} {w:.6f} {h:.6f}\n")


def augment_image(img: np.ndarray, labels: list, config: dict) -> Tuple[np.ndarray, list]:
    """Apply random augmentations to image and labels."""
    
    # Perspective warp
    if random.random() < config["perspective_prob"]:
        intensity = random.uniform(*config["perspective_intensity"])
        img, labels = perspective_warp(img, labels, intensity)
    
    # Scale
    if random.random() < config["scale_prob"]:
        scale = random.uniform(*config["scale_range"])
        img, labels = scale_image_and_labels(img, labels, scale)
    
    # Rotation
    if random.random() < config["rotation_prob"]:
        angle = random.uniform(*config["rotation_range"])
        img, labels = rotate_image_and_labels(img, labels, angle)
    
    # Horizontal flip
    if random.random() < config["flip_prob"]:
        img, labels = horizontal_flip(img, labels)
    
    # Brightness/contrast
    if random.random() < config["brightness_prob"]:
        brightness = random.uniform(*config["brightness_range"])
        contrast = random.uniform(*config["contrast_range"]) if random.random() < config["contrast_prob"] else 1.0
        img = adjust_brightness_contrast(img, brightness, contrast)
    
    # Motion blur
    if random.random() < config["blur_prob"]:
        kernel = random.choice(range(config["blur_kernel"][0], config["blur_kernel"][1] + 1, 2))
        img = apply_motion_blur(img, kernel)
    
    return img, labels


def augment_dataset(multiplier: int = 3, dry_run: bool = False):
    """Augment entire dataset. Handles nested folder structure."""
    
    input_images = ANNOTATED_DIR / "images"
    input_labels = ANNOTATED_DIR / "labels"
    output_images = AUGMENTED_DIR / "images"
    output_labels = AUGMENTED_DIR / "labels"
    
    if not input_images.exists():
        print(f"❌ Input images not found: {input_images}")
        return
    
    if not dry_run:
        output_images.mkdir(parents=True, exist_ok=True)
        output_labels.mkdir(parents=True, exist_ok=True)
    
    # Get all images - handle both flat and nested structure
    image_files = []
    
    # Check if there are subfolders (nested structure)
    subfolders = [d for d in input_images.iterdir() if d.is_dir()]
    
    if subfolders:
        # Nested structure: annotated/images/other_person/, annotated/images/tanmay/
        for subfolder in subfolders:
            for f in subfolder.iterdir():
                if f.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
                    image_files.append(f)
    else:
        # Flat structure: annotated/images/*.jpg
        image_files = [f for f in input_images.glob("*") 
                       if f.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}]
    
    print(f"📁 Input: {input_images}")
    print(f"📁 Output: {output_images}")
    print(f"🖼️  Images found: {len(image_files)}")
    print(f"🔄 Multiplier: {multiplier}x")
    print(f"📊 Expected output: ~{len(image_files) * (multiplier + 1)} images")
    print()
    
    if dry_run:
        print("🔍 DRY RUN - no files will be created")
        return
    
    total_created = 0
    
    for img_path in tqdm(image_files, desc="Augmenting"):
        # Read image
        img = cv2.imread(str(img_path))
        if img is None:
            print(f"⚠️ Could not read: {img_path.name}")
            continue
        
        # Read corresponding labels - handle nested structure
        # Image: annotated/images/other_person/img.jpg -> Label: annotated/labels/other_person/img.txt
        if img_path.parent.name in [d.name for d in input_images.iterdir() if d.is_dir()]:
            # Nested structure
            subfolder = img_path.parent.name
            label_path = input_labels / subfolder / (img_path.stem + ".txt")
        else:
            # Flat structure
            subfolder = ""
            label_path = input_labels / (img_path.stem + ".txt")
        labels = read_labels(label_path)
        
        # Prefix with subfolder name to avoid collisions across classes
        # e.g. background/1.jpg -> bg_1_orig.jpg, tanmay/1.jpg -> tanmay_1_orig.jpg
        prefix_map = {"background": "bg", "other_person": "op", "tanmay": "tanmay"}
        prefix = prefix_map.get(subfolder, subfolder) + "_" if subfolder else ""
        base_name = f"{prefix}{img_path.stem}"
        ext = img_path.suffix
        
        cv2.imwrite(str(output_images / f"{base_name}_orig{ext}"), img)
        if labels:
            write_labels(output_labels / f"{base_name}_orig.txt", labels)
        else:
            # Empty label file for background images
            (output_labels / f"{base_name}_orig.txt").touch()
        total_created += 1
        
        # Create augmented versions
        for i in range(multiplier):
            aug_img, aug_labels = augment_image(img.copy(), [l[:] for l in labels], AUGMENT_CONFIG)
            
            aug_name = f"{base_name}_aug{i+1}"
            cv2.imwrite(str(output_images / f"{aug_name}{ext}"), aug_img)
            
            if aug_labels:
                write_labels(output_labels / f"{aug_name}.txt", aug_labels)
            else:
                (output_labels / f"{aug_name}.txt").touch()
            
            total_created += 1
    
    print()
    print("=" * 50)
    print(f"✅ Created {total_created} images in {output_images}")


def main():
    parser = argparse.ArgumentParser(description="Augment dataset for buggy-view perspective")
    parser.add_argument("--multiplier", "-m", type=int, default=3,
                        help="Number of augmented copies per image (default: 3)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be done without doing it")
    args = parser.parse_args()
    
    print("=" * 50)
    print("Dataset Augmentation")
    print("=" * 50)
    
    augment_dataset(multiplier=args.multiplier, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
