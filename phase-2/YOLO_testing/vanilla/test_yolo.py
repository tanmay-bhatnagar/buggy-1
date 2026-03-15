#!/usr/bin/env python3
"""
Test the trained YOLO model using the Mac webcam.
Exit by pressing 'x' or 'q'.
"""

import cv2
import argparse
import time
from pathlib import Path
from ultralytics import YOLO

def main():
    parser = argparse.ArgumentParser(description="Live YOLO Detection Test")
    parser.add_argument(
        "--weights", 
        type=str, 
        default="../../training/runs/tanmay_detector_20260212_164033/weights/best.pt",
        help="Path to best.pt weights"
    )
    args = parser.parse_args()

    # 1. Load Model
    if not Path(args.weights).exists():
        print(f"❌ Weights not found at: {args.weights}")
        return

    print(f"🚀 Loading model: {args.weights}")
    model = YOLO(args.weights)

    # 2. Setup Camera
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("❌ Cannot open camera")
        return

    print("📸 Camera started. Press 'X' to exit.")

    # FPS tracking
    prev_time = time.time()
    fps = 0.0

    while True:
        ret, frame = cap.read()
        if not ret:
            print("❌ Failed to grab frame")
            break

        # 3. Run Inference
        # stream=True is more memory efficient for video
        results = model(frame, stream=True)

        # 4. Draw & Display
        for r in results:
            annotated_frame = r.plot()  # Draws boxes and labels

            # FPS calculation
            curr_time = time.time()
            fps = 0.9 * fps + 0.1 * (1.0 / max(curr_time - prev_time, 1e-6))
            prev_time = curr_time
            cv2.putText(annotated_frame, f"FPS: {fps:.1f}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)

            cv2.namedWindow("YOLO Live Detection", cv2.WINDOW_NORMAL); cv2.resizeWindow("YOLO Live Detection", 960, 720); cv2.imshow("YOLO Live Detection", annotated_frame)

        # 5. Exit logic
        key = cv2.waitKey(1) & 0xFF
        if key == ord('x') or key == ord('X'):
            break

    # Cleanup
    cap.release()
    cv2.destroyAllWindows()
    print("👋 Stopped.")

if __name__ == "__main__":
    main()
