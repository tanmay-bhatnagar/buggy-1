# YOLO Vanilla Testing
This directory contains the baseline test script for the YOLO model.

## Contents
- `test_yolo.py`: Runs standard YOLO inference using the Mac webcam and draws result boxes using the `ultralytics` default plotting.

## How to Run
Run this script from within this directory:
```bash
python test_yolo.py
```

## Purpose
Use this as a baseline to see how the raw model performs without any post-processing logic. You will likely see box jitter and occasional "hallucinations" (double boxes).
