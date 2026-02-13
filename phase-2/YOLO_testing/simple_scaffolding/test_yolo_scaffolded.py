#!/usr/bin/env python3
"""
Scaffolded Live YOLO Detection Test.
Uses BuggyTracker to solve overlapping boxes and missed detections.
Exit by pressing 'x'.
"""

import cv2
import argparse
import time
from pathlib import Path
from ultralytics import YOLO
from tracker import BuggyTracker

def main():
    parser = argparse.ArgumentParser(description="Live YOLO Scaffolded Detection")
    parser.add_argument(
        "--weights", 
        type=str, 
        default="../../training/runs/tanmay_detector_20260212_164033/weights/best.pt",
        help="Path to best.pt weights"
    )
    args = parser.parse_args()

    # 1. Load Model & Tracker
    if not Path(args.weights).exists():
        print(f"❌ Weights not found at: {args.weights}")
        return

    print(f"🚀 Loading model: {args.weights}")
    model = YOLO(args.weights)
    tracker = BuggyTracker(
        target_class_id=0,   # tanmay
        conf_threshold_start=0.6,
        conf_threshold_keep=0.35, # Hysteresis
        ghost_limit=15        # ~0.5s at 30fps
    )

    # 2. Setup Camera
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("❌ Cannot open camera")
        return

    print("📸 Camera started with SCAFFOLDING active.")
    print("   Logic: Highlander Rule, Cross-Class NMS, Ghosting (15 frames)")
    print("   Press 'X' to exit.")

    while True:
        ret, frame = cap.read()
        if not ret: break

        # 3. Run Inference
        results = model(frame, verbose=False)[0]
        
        boxes = results.boxes.xyxy.cpu().numpy()
        confs = results.boxes.conf.cpu().numpy()
        classes = results.boxes.cls.cpu().numpy()

        # 4. Apply Scaffolding Logic
        target_box, is_ghost, other_detections = tracker.process_detections(frame, boxes, confs, classes)

        # 5. Drawing (Manual drawing to show Ghosting state)
        # Draw others first
        for box, conf, cls in other_detections:
            x1, y1, x2, y2 = map(int, box)
            cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), 2) # Blue
            cv2.putText(frame, f"other {conf:.2f}", (x1, y1-10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)

        # Draw Target
        if target_box is not None:
            x1, y1, x2, y2 = map(int, target_box)
            color = (128, 128, 128) if is_ghost else (0, 0, 255) # Grey if ghost, Red if active
            label = f"TANMAY (GHOST)" if is_ghost else f"TANMAY {tracker.target_conf:.2f}"
            
            thickness = 1 if is_ghost else 3
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)
            cv2.putText(frame, label, (x1, y1-10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        cv2.namedWindow("Buggy V1 - Scaffolded Detection", cv2.WINDOW_NORMAL); cv2.resizeWindow("Buggy V1 - Scaffolded Detection", 960, 720); cv2.imshow("Buggy V1 - Scaffolded Detection", frame)

        if cv2.waitKey(1) & 0xFF in [ord('x'), ord('X')]:
            break

    cap.release()
    cv2.destroyAllWindows()
    print("👋 Stopped.")

if __name__ == "__main__":
    main()
