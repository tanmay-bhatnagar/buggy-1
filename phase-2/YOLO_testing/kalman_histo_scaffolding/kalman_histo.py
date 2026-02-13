#!/usr/bin/env python3
"""
Advanced Scaffolded Live YOLO Detection Test.
Uses:
- Kalman Filter (Motion Prediction & Smoothing)
- Color Histograms (Visual Fingerprinting)
- Cross-Class NMS (Priority to Tanmay)
- Ghosting (Persistence)

Exit by pressing 'x'.
"""

import cv2
import argparse
import time
from pathlib import Path
from ultralytics import YOLO
from tracker import BuggyTracker

def main():
    parser = argparse.ArgumentParser(description="Live YOLO Advanced Scaffolded Detection")
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
        conf_threshold_keep=0.35, 
        ghost_limit=20,
        use_histogram=True,
        use_kalman=True
    )

    # 2. Setup Camera
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("❌ Cannot open camera")
        return

    print("📸 Camera started with ADVANCED SCAFFOLDING active.")
    print("   Features: Kalman Prediction, Color Fingerprinting, Ghosting.")
    print("   Press 'X' to exit.")

    while True:
        ret, frame = cap.read()
        if not ret: break

        # 3. Run Inference
        results = model(frame, verbose=False)[0]
        
        boxes = results.boxes.xyxy.cpu().numpy()
        confs = results.boxes.conf.cpu().numpy()
        classes = results.boxes.cls.cpu().numpy()

        # 4. Apply Advanced Scaffolding Logic
        # Pass the current frame for histogram extraction
        target_box, is_ghost, other_detections = tracker.process_detections(frame, boxes, confs, classes)

        # 5. Drawing 
        # Draw others first
        for box, conf, cls in other_detections:
            x1, y1, x2, y2 = map(int, box)
            cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), 1) # Thin Blue for others
            cv2.putText(frame, f"other {conf:.2f}", (x1, y1-10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 0, 0), 1)

        # Draw Target
        if target_box is not None:
            x1, y1, x2, y2 = map(int, target_box)
            # Use Red for active, Yellow/Orange for Ghosting
            color = (0, 165, 255) if is_ghost else (0, 0, 255) 
            label = f"TANMAY (GHOSTING)" if is_ghost else f"TANMAY (LOCKED) {tracker.target_conf:.2f}"
            
            thickness = 2 if is_ghost else 4
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)
            
            # Label background for readability
            cv2.rectangle(frame, (x1, y1-25), (x1+210, y1), color, -1)
            cv2.putText(frame, label, (x1+5, y1-7), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
            
            # Visualize the "Visual Fingerprint" lock
            if tracker.target_hist is not None:
                cv2.circle(frame, (x1+10, y1+15), 5, (0, 255, 0), -1)
                cv2.putText(frame, "Visual ID Locked", (x1+20, y1+20),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)

        cv2.namedWindow("Follow-Me V2 - Kalman + Histogram", cv2.WINDOW_NORMAL); cv2.resizeWindow("Follow-Me V2 - Kalman + Histogram", 960, 720); cv2.imshow("Follow-Me V2 - Kalman + Histogram", frame)

        if cv2.waitKey(1) & 0xFF in [ord('x'), ord('X')]:
            break

    cap.release()
    cv2.destroyAllWindows()
    print("👋 Stopped.")

if __name__ == "__main__":
    main()
