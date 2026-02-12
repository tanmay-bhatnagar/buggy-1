#!/usr/bin/env python3
"""
Visualize YOLO bounding box annotations on images.

Reads images and labels from dataset/annotated/ and draws bounding boxes,
saving the results to dataset/test_annotations/.

Colors: Red = tanmay (class 0), Blue = other_person (class 1)
"""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps

SCRIPT_DIR = Path(__file__).parent.resolve()
BASE_DIR = SCRIPT_DIR.parent
ANNOTATED_DIR = BASE_DIR / "dataset" / "annotated"
OUTPUT_DIR = BASE_DIR / "dataset" / "test_annotations"

# Class colors: tanmay=red, other_person=blue
CLASS_COLORS = {
    0: (255, 0, 0),      # Red - tanmay
    1: (0, 100, 255),    # Blue - other_person
}
CLASS_NAMES = {
    0: "tanmay",
    1: "other_person",
}


def draw_yolo_boxes(image_path: Path, label_path: Path, output_path: Path):
    """Draw YOLO bounding boxes on an image and save it."""
    img = ImageOps.exif_transpose(Image.open(image_path)).convert("RGB")
    draw = ImageDraw.Draw(img)
    img_w, img_h = img.size

    # Line thickness scales with image size
    thickness = max(2, min(img_w, img_h) // 200)

    with open(label_path, "r") as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) < 5:
                continue

            cls_id = int(parts[0])
            cx, cy, bw, bh = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])

            # Convert YOLO (center x, center y, width, height) to pixel coords
            x1 = int((cx - bw / 2) * img_w)
            y1 = int((cy - bh / 2) * img_h)
            x2 = int((cx + bw / 2) * img_w)
            y2 = int((cy + bh / 2) * img_h)

            color = CLASS_COLORS.get(cls_id, (0, 255, 0))
            label = CLASS_NAMES.get(cls_id, f"class_{cls_id}")

            # Draw rectangle
            for i in range(thickness):
                draw.rectangle([x1 - i, y1 - i, x2 + i, y2 + i], outline=color)

            # Draw label background + text
            font_size = max(12, min(img_w, img_h) // 40)
            try:
                font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
            except (OSError, IOError):
                font = ImageFont.load_default()

            text_bbox = draw.textbbox((x1, y1), label, font=font)
            text_w = text_bbox[2] - text_bbox[0]
            text_h = text_bbox[3] - text_bbox[1]
            draw.rectangle([x1, y1 - text_h - 6, x1 + text_w + 6, y1], fill=color)
            draw.text((x1 + 3, y1 - text_h - 4), label, fill=(255, 255, 255), font=font)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, quality=90)


def main():
    print("=" * 50)
    print("Annotation Visualizer")
    print("=" * 50)

    images_dir = ANNOTATED_DIR / "images"
    labels_dir = ANNOTATED_DIR / "labels"
    total = 0

    for subfolder in sorted(images_dir.iterdir()):
        if not subfolder.is_dir() or subfolder.name.startswith("."):
            continue

        class_name = subfolder.name
        label_subfolder = labels_dir / class_name
        output_subfolder = OUTPUT_DIR / class_name

        if not label_subfolder.exists():
            print(f"\n⚠️  No labels folder for {class_name}, skipping")
            continue

        # Find all image files
        img_files = sorted([
            f for f in subfolder.iterdir()
            if f.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
        ])

        print(f"\n📁 {class_name}/: {len(img_files)} images")

        count = 0
        for img_path in img_files:
            label_path = label_subfolder / f"{img_path.stem}.txt"
            if not label_path.exists():
                continue

            output_path = output_subfolder / img_path.name
            draw_yolo_boxes(img_path, label_path, output_path)
            count += 1

            if count % 50 == 0:
                print(f"  ✅ Processed {count}/{len(img_files)}")

        print(f"  ✅ Done: {count} images saved to test_annotations/{class_name}/")
        total += count

    print(f"\n{'=' * 50}")
    print(f"Total: {total} annotated images saved to dataset/test_annotations/")
    print("=" * 50)


if __name__ == "__main__":
    main()
