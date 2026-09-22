# YOLO Tracking Experiments

This folder contains experiments around detection persistence and target identity. They are research prototypes, not a production control component and not connected to the buggy's motor commands.

## Before running

- Install the Phase 2 Python environment from the parent [README](../README.md).
- Supply a compatible local YOLO weight file; weights are intentionally not committed.
- Use a webcam or compatible camera and set the device/path required by the selected script.
- Start with the baseline implementation before evaluating tracker variants.

| Variant | Purpose | Notes |
| --- | --- | --- |
| [vanilla](vanilla/README.md) | Baseline YOLO detections | No temporal identity or persistence. |
| [simple_scaffolding](simple_scaffolding/README.md) | Lightweight suppression/persistence experiments | Prototype heuristics; tune against real footage. |
| [kalman_histo_scaffolding](kalman_histo_scaffolding/README.md) | Kalman motion plus HSV appearance experiment | Sensitive to lighting, occlusion, and thresholds. |
| `finalized_tracking.py` | Later configurable tracker work | Review its options and model path before use. |

Run these in a controlled environment. A tracker output is not sufficient to authorize autonomous motor movement; validate the full perception-to-control system separately.
