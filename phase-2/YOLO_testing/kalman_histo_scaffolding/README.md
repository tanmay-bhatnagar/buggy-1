# Kalman & Histogram Scaffolding
The most advanced version of our inference logic, designed for maximum stability and identity persistence.

## Contents
- `tracker.py`: Advanced `BuggyTracker` featuring:
    - **Kalman Filter**: A Constant Velocity model that predicts motion and smooths jitter.
    - **Color Histograms (HSV)**: Creates a "Visual Fingerprint" of your clothes to differentiate between targets.
    - **Moving Ghosting**: If you disappear, the "ghost" box continues moving based on your last predicted velocity.
- `kalman_histo.py`: Premium runner script with detailed visual feedback on tracking states.

## How to Run
```bash
python kalman_histo.py
```

## Features
- **Visual ID Locked**: A green indicator appears when the tracker has fingerprinted your colors.
- **Smart Prediction**: Hide behind an object and watch the **Orange (Ghost)** box stay on track with your real movement.
- **Smooth Locomotion**: The Kalman filter removes "pixel-jitter," which is crucial for smooth motor control on the Jetson.
