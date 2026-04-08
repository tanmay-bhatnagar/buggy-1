# Tracking Design Notes

Last updated: 2026-04-09

## Goal

Finalize the Phase 2 tracker design before writing code.

Known facts:
- Camera target is `30 FPS`
- YOLO + TensorRT already sustains `30 FPS`
- FPS drops happen in the tracker loop
- Current `kalman + histo` tracker falls to about `18 FPS` under motion

So the tracker must be:
- stable
- cheap
- predictable under motion
- modular enough to swap identity methods cleanly

---

## Core Design

### Motion backbone

Kalman stays constant.

Responsibilities:
- target continuity
- prediction
- smoothing
- ghosting

Kalman is the permanent backbone because it is cheap and directly useful for control.

### Identity layer

This is hot-swappable.

Candidate modes:
- none
- histogram
- embeddings

Identity should assist the tracker, not define it.

---

## Important Processing Rule

Only `tanmay` detections are tracked.

Config flag:
- `TRACK_TANMAY_ONLY = True` by default

Meaning:
- only detections from class `tanmay` enter the tracking/identity pipeline
- other classes are ignored for tracking purposes

Why:
- reduces candidate count
- reduces identity compute
- reduces association complexity
- fits the actual follow-me use case

This should take load off the processing loop.

---

## Three-Layer View

### 1. Detection layer

Per frame:
- read YOLO detections
- keep only `tanmay` detections if `TRACK_TANMAY_ONLY=True`
- filter by confidence
- prepare target candidates

### 2. Motion layer

Per frame:
- Kalman prediction
- target association
- smoothing
- ghosting

### 3. Identity layer

Optional and swappable:
- histogram scoring
- embedding scoring
- or no identity scoring

Final target choice should be based on:
- detection confidence
- motion consistency
- identity confidence

Motion remains the primary signal.

---

## Embeddings Direction

If we replace histogram identity, we do not replace the tracker.

We replace only the appearance module:
- current: `Kalman + histogram`
- candidate: `Kalman + embeddings`

That keeps maintenance simple and makes benchmarking fair.

---

## `SKIP_FRAMES = N`

For embeddings, use:
- `SKIP_FRAMES = N`

Meaning:
- run embedding inference once
- skip the next `N` frames
- run it again

Important:
- tracking still runs every frame
- Kalman still runs every frame
- only identity inference is sampled

So `SKIP_FRAMES` is an identity-refresh hyperparameter, not a tracking-rate hyperparameter.

---

## What Happens During Skipped Frames

During skipped frames, tracking continues using:
- Kalman prediction
- YOLO detections
- motion consistency
- previous identity belief

Practical interpretation:
- Kalman says where the target should be
- YOLO says what candidates exist now
- identity only periodically verifies who the target is

This means skipped frames should rely on:
- spatial continuity
- temporal continuity
- confidence carry-forward
- confidence decay

---

## Better Than Strict Sampling

There are two possible policies:

### A. Strict periodic refresh

Run embeddings every `N` frames exactly.

Pros:
- simple
- easy to benchmark

Cons:
- may wait too long when ambiguity rises

### B. Periodic refresh with early triggers

Run embeddings every `N` frames by default, but run earlier if needed.

Possible triggers:
- multiple plausible candidates
- target deviates from predicted motion
- detection confidence drops
- reappearance after occlusion
- lock confidence decays

This is likely the better long-term design.

---

## Why We Should Test Embeddings, Not Assume Them

Memory headroom alone does not answer the real question.

The real question is whether the full loop stays inside the `33.3 ms` frame budget for `30 FPS`.

Even a small embedding model can still add:
- extra inference time
- crop / resize overhead
- candidate handling cost
- synchronization overhead

So every-frame embeddings are valid to test, but should be measured rather than assumed free.

---

## Current Recommended Direction

- Keep Kalman as the fixed motion backbone
- Use `TRACK_TANMAY_ONLY = True` by default
- Make the identity layer hot-swappable
- Evaluate:
  - no identity
  - histogram identity
  - embedding identity
- For embeddings, start with `SKIP_FRAMES = N`
- Likely allow early refresh when ambiguity rises

---

## Open Design Questions

Still to decide:
- should embeddings only verify the current lock, or also choose between candidates?
- should `SKIP_FRAMES` be strict or interruptible?
- how should identity confidence decay between refreshes?
- what scene difficulty must Phase 2 handle reliably?

This is the current working design direction.
