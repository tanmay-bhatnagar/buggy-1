# Simple Scaffolding Testing
This directory introduces the first level of post-processing logic to stabilize detections.

## Contents
- `tracker.py`: Implements the `BuggyTracker` class with:
    - **Highlander Rule**: Prioritizes the detection closest to the last known position.
    - **Cross-Class NMS**: Prevents "hallucinations" by prioritizing `tanmay` over `other_person` in overlapping areas.
    - **Stationary Ghosting**: Keeps the last known target box alive for 15 frames if detection is lost.
- `test_yolo_scaffolded.py`: Runner script that uses the tracker and manually draws custom-styled boxes.

## How to Run
```bash
python test_yolo_scaffolded.py
```

## Purpose
Fixes overlapping boxes and basic target persistence. Boxes are color-coded: **Red** for active lock, **Grey** for ghosting.
