#!/usr/bin/env python3
"""
Unified Phase 2 tracking harness.

Highlights:
- Tracks only the "tanmay" class by default.
- Keeps Kalman as the constant motion backbone.
- Hot-swaps identity mode between none / histogram / embeddings.
- Supports sampled embedding refresh with SKIP_FRAMES = N.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

import cv2
import numpy as np
from ultralytics import YOLO


SCRIPT_DIR = Path(__file__).resolve().parent
PHASE2_DIR = SCRIPT_DIR.parent
MODEL_DIR = PHASE2_DIR / "models" / "embedding_models"

DEFAULT_EMBEDDING_WEIGHTS = {
    "osnet_x0_25": MODEL_DIR / "torchreid" / "osnet_x0_25_imagenet.pth",
    "osnet_x0_5": MODEL_DIR / "torchreid" / "osnet_x0_5_imagenet.pth",
    "osnet_ain_x1_0": MODEL_DIR / "torchreid" / "osnet_ain_x1_0_imagenet.pth",
}


def parse_source(value: str):
    return int(value) if value.isdigit() else value


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom <= 1e-8:
        return 0.0
    return float(np.dot(a, b) / denom)


def clamp_box(box: Sequence[float], width: int, height: int) -> Optional[Tuple[int, int, int, int]]:
    x1, y1, x2, y2 = map(int, box)
    x1 = max(0, min(width - 1, x1))
    y1 = max(0, min(height - 1, y1))
    x2 = max(0, min(width, x2))
    y2 = max(0, min(height, y2))
    if x2 <= x1 or y2 <= y1:
        return None
    return x1, y1, x2, y2


class IdentityScorer:
    def score_many(
        self,
        image: np.ndarray,
        boxes: Sequence[np.ndarray],
        frame_idx: int,
        force_refresh: bool = False,
    ) -> List[float]:
        return [0.0] * len(boxes)

    def update_reference(self, image: np.ndarray, box: np.ndarray, frame_idx: int) -> None:
        return

    def reset(self) -> None:
        return

    @property
    def label(self) -> str:
        return "none"


class HistogramIdentityScorer(IdentityScorer):
    def __init__(self, bins: int = 16, ema_alpha: float = 0.15):
        self.bins = bins
        self.ema_alpha = ema_alpha
        self.reference_hist: Optional[np.ndarray] = None

    @property
    def label(self) -> str:
        return "histogram"

    def _extract_hist(self, image: np.ndarray, box: np.ndarray) -> Optional[np.ndarray]:
        clamped = clamp_box(box, image.shape[1], image.shape[0])
        if clamped is None:
            return None
        x1, y1, x2, y2 = clamped
        roi = image[y1:y2, x1:x2]
        if roi.size == 0:
            return None
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1], None, [self.bins, self.bins], [0, 180, 0, 256])
        cv2.normalize(hist, hist, 0, 1, cv2.NORM_MINMAX)
        return hist.astype(np.float32)

    def score_many(
        self,
        image: np.ndarray,
        boxes: Sequence[np.ndarray],
        frame_idx: int,
        force_refresh: bool = False,
    ) -> List[float]:
        if self.reference_hist is None:
            return [0.0] * len(boxes)
        scores = []
        for box in boxes:
            hist = self._extract_hist(image, box)
            if hist is None:
                scores.append(0.0)
                continue
            score = cv2.compareHist(self.reference_hist, hist, cv2.HISTCMP_CORREL)
            scores.append(float(max(0.0, min(1.0, (score + 1.0) / 2.0))))
        return scores

    def update_reference(self, image: np.ndarray, box: np.ndarray, frame_idx: int) -> None:
        hist = self._extract_hist(image, box)
        if hist is None:
            return
        if self.reference_hist is None:
            self.reference_hist = hist
        else:
            self.reference_hist = ((1.0 - self.ema_alpha) * self.reference_hist) + (self.ema_alpha * hist)

    def reset(self) -> None:
        self.reference_hist = None


class EmbeddingIdentityScorer(IdentityScorer):
    def __init__(self, model_name: str, weights_path: Path, skip_frames: int = 4, ema_alpha: float = 0.1):
        self.model_name = model_name
        self.weights_path = weights_path
        self.skip_frames = max(0, skip_frames)
        self.ema_alpha = ema_alpha
        self.reference_embedding: Optional[np.ndarray] = None
        self.last_refresh_frame = -10**9

        try:
            import torch
            from torchreid import models
            from torchreid.reid.utils import load_pretrained_weights
        except Exception as exc:
            raise RuntimeError(
                "Embedding mode requires torchreid + torch in the active environment."
            ) from exc

        if not self.weights_path.exists():
            raise FileNotFoundError(f"Embedding weights not found: {self.weights_path}")

        self.torch = torch
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = models.build_model(
            name=model_name,
            num_classes=1000,
            loss="softmax",
            pretrained=False,
            use_gpu=self.device.type == "cuda",
        )
        load_pretrained_weights(self.model, str(self.weights_path))
        self.model.to(self.device)
        self.model.eval()

        self.mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        self.std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        self.input_size = (128, 256)  # width, height

    @property
    def label(self) -> str:
        return f"embedding:{self.model_name}"

    def _extract_crop(self, image: np.ndarray, box: np.ndarray) -> Optional[np.ndarray]:
        clamped = clamp_box(box, image.shape[1], image.shape[0])
        if clamped is None:
            return None
        x1, y1, x2, y2 = clamped
        crop = image[y1:y2, x1:x2]
        if crop.size == 0:
            return None
        return crop

    def _embed_crops(self, crops: List[np.ndarray]) -> List[np.ndarray]:
        if not crops:
            return []
        tensors = []
        for crop in crops:
            rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
            resized = cv2.resize(rgb, self.input_size, interpolation=cv2.INTER_LINEAR)
            normalized = resized.astype(np.float32) / 255.0
            normalized = (normalized - self.mean) / self.std
            chw = np.transpose(normalized, (2, 0, 1))
            tensors.append(chw)

        batch = self.torch.from_numpy(np.stack(tensors)).to(self.device)
        with self.torch.no_grad():
            features = self.model(batch)
            features = self.torch.nn.functional.normalize(features, p=2, dim=1)
        return [feature.detach().cpu().numpy().astype(np.float32) for feature in features]

    def score_many(
        self,
        image: np.ndarray,
        boxes: Sequence[np.ndarray],
        frame_idx: int,
        force_refresh: bool = False,
    ) -> List[float]:
        if self.reference_embedding is None:
            return [0.0] * len(boxes)

        should_refresh = force_refresh or (frame_idx - self.last_refresh_frame > self.skip_frames)
        if not should_refresh:
            return [0.0] * len(boxes)

        crops: List[np.ndarray] = []
        valid_indices: List[int] = []
        for idx, box in enumerate(boxes):
            crop = self._extract_crop(image, box)
            if crop is None:
                continue
            crops.append(crop)
            valid_indices.append(idx)

        scores = [0.0] * len(boxes)
        embeddings = self._embed_crops(crops)
        for idx, embedding in zip(valid_indices, embeddings):
            scores[idx] = max(0.0, cosine_similarity(self.reference_embedding, embedding))

        self.last_refresh_frame = frame_idx
        return scores

    def update_reference(self, image: np.ndarray, box: np.ndarray, frame_idx: int) -> None:
        crop = self._extract_crop(image, box)
        if crop is None:
            return
        embeddings = self._embed_crops([crop])
        if not embeddings:
            return
        embedding = embeddings[0]
        if self.reference_embedding is None:
            self.reference_embedding = embedding
        else:
            mixed = ((1.0 - self.ema_alpha) * self.reference_embedding) + (self.ema_alpha * embedding)
            norm = np.linalg.norm(mixed)
            self.reference_embedding = mixed if norm <= 1e-8 else (mixed / norm).astype(np.float32)
        self.last_refresh_frame = frame_idx

    def reset(self) -> None:
        self.reference_embedding = None
        self.last_refresh_frame = -10**9


class FinalizedTracker:
    def __init__(
        self,
        target_class_id: int = 0,
        conf_start: float = 0.60,
        conf_keep: float = 0.35,
        ghost_limit: int = 15,
        track_tanmay_only: bool = True,
        identity_scorer: Optional[IdentityScorer] = None,
        identity_weight: float = 0.35,
        motion_weight: float = 0.45,
        confidence_weight: float = 0.20,
    ):
        self.target_class_id = target_class_id
        self.conf_start = conf_start
        self.conf_keep = conf_keep
        self.ghost_limit = ghost_limit
        self.track_tanmay_only = track_tanmay_only
        self.identity_scorer = identity_scorer or IdentityScorer()
        self.identity_weight = identity_weight
        self.motion_weight = motion_weight
        self.confidence_weight = confidence_weight

        self.frame_idx = 0
        self.target_active = False
        self.last_box: Optional[np.ndarray] = None
        self.target_conf = 0.0
        self.lock_score = 0.0
        self.missed_frames = 0

        self.kf = cv2.KalmanFilter(4, 2)
        self.kf.measurementMatrix = np.array([[1, 0, 0, 0], [0, 1, 0, 0]], np.float32)
        self.kf.transitionMatrix = np.array(
            [[1, 0, 1, 0], [0, 1, 0, 1], [0, 0, 1, 0], [0, 0, 0, 1]], np.float32
        )
        self.kf.processNoiseCov = np.eye(4, dtype=np.float32) * 0.03
        self.kf.measurementNoiseCov = np.eye(2, dtype=np.float32) * 0.2

    def _center(self, box: np.ndarray) -> np.ndarray:
        return np.array([(box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0], dtype=np.float32)

    def _predict_center(self) -> Optional[np.ndarray]:
        if not self.target_active:
            return None
        prediction = self.kf.predict()
        return np.array([float(prediction[0, 0]), float(prediction[1, 0])], dtype=np.float32)

    def _shift_box_to_center(self, box: np.ndarray, center: np.ndarray) -> np.ndarray:
        width = box[2] - box[0]
        height = box[3] - box[1]
        cx, cy = float(center[0]), float(center[1])
        return np.array(
            [cx - width / 2.0, cy - height / 2.0, cx + width / 2.0, cy + height / 2.0],
            dtype=np.float32,
        )

    def _filter_candidates(
        self,
        boxes: np.ndarray,
        confs: np.ndarray,
        class_ids: np.ndarray,
        threshold: float,
    ) -> Tuple[List[np.ndarray], List[float]]:
        candidate_boxes: List[np.ndarray] = []
        candidate_confs: List[float] = []
        for box, conf, cls in zip(boxes, confs, class_ids):
            if self.track_tanmay_only and int(cls) != self.target_class_id:
                continue
            if float(conf) < threshold:
                continue
            candidate_boxes.append(np.asarray(box, dtype=np.float32))
            candidate_confs.append(float(conf))
        return candidate_boxes, candidate_confs

    def _reset(self) -> None:
        self.target_active = False
        self.last_box = None
        self.target_conf = 0.0
        self.lock_score = 0.0
        self.missed_frames = 0
        self.identity_scorer.reset()

    def process(
        self,
        image: np.ndarray,
        boxes: np.ndarray,
        confs: np.ndarray,
        class_ids: np.ndarray,
    ) -> Tuple[Optional[np.ndarray], bool, dict]:
        self.frame_idx += 1
        threshold = self.conf_keep if self.target_active else self.conf_start
        candidate_boxes, candidate_confs = self._filter_candidates(boxes, confs, class_ids, threshold)
        predicted_center = self._predict_center()

        debug = {
            "num_candidates": len(candidate_boxes),
            "identity_mode": self.identity_scorer.label,
            "lock_score": self.lock_score,
        }

        if candidate_boxes:
            frame_diag = float(np.hypot(image.shape[1], image.shape[0]))
            force_identity_refresh = len(candidate_boxes) > 1
            identity_scores = self.identity_scorer.score_many(
                image,
                candidate_boxes,
                frame_idx=self.frame_idx,
                force_refresh=force_identity_refresh,
            )

            best_idx = 0
            best_total = -1e9
            best_motion_score = 0.0
            best_identity_score = 0.0

            for idx, (box, conf) in enumerate(zip(candidate_boxes, candidate_confs)):
                motion_score = 0.0
                if predicted_center is not None:
                    dist = np.linalg.norm(self._center(box) - predicted_center)
                    motion_score = max(0.0, 1.0 - min(1.0, dist / max(frame_diag, 1.0)))
                elif self.last_box is not None:
                    dist = np.linalg.norm(self._center(box) - self._center(self.last_box))
                    motion_score = max(0.0, 1.0 - min(1.0, dist / max(frame_diag, 1.0)))

                identity_score = identity_scores[idx] if idx < len(identity_scores) else 0.0
                total = (
                    (self.confidence_weight * conf)
                    + (self.motion_weight * motion_score)
                    + (self.identity_weight * identity_score)
                )
                if total > best_total:
                    best_total = total
                    best_idx = idx
                    best_motion_score = motion_score
                    best_identity_score = identity_score

            best_box = candidate_boxes[best_idx]
            best_conf = candidate_confs[best_idx]
            measurement = self._center(best_box).reshape(2, 1)
            self.kf.correct(measurement.astype(np.float32))

            self.target_active = True
            self.last_box = best_box
            self.target_conf = best_conf
            self.lock_score = float(best_total)
            self.missed_frames = 0
            self.identity_scorer.update_reference(image, best_box, self.frame_idx)

            debug.update(
                {
                    "motion_score": best_motion_score,
                    "identity_score": best_identity_score,
                }
            )
            return self.last_box.copy(), False, debug

        if self.target_active and self.last_box is not None:
            self.missed_frames += 1
            if self.missed_frames > self.ghost_limit:
                self._reset()
                return None, False, debug

            predicted_center = self._predict_center()
            if predicted_center is not None:
                self.last_box = self._shift_box_to_center(self.last_box, predicted_center)
            self.target_conf *= 0.92
            self.lock_score *= 0.95
            debug["lock_score"] = self.lock_score
            return self.last_box.copy(), True, debug

        return None, False, debug


def build_identity_scorer(args) -> IdentityScorer:
    if args.identity_mode == "none":
        return IdentityScorer()
    if args.identity_mode == "histogram":
        return HistogramIdentityScorer()
    if args.identity_mode == "embedding":
        weights_path = Path(args.embedding_weights) if args.embedding_weights else DEFAULT_EMBEDDING_WEIGHTS[args.embedding_model]
        return EmbeddingIdentityScorer(
            model_name=args.embedding_model,
            weights_path=weights_path,
            skip_frames=args.skip_frames,
        )
    raise ValueError(f"Unsupported identity mode: {args.identity_mode}")


def draw_tracking_overlay(
    frame: np.ndarray,
    tracked_box: Optional[np.ndarray],
    is_ghost: bool,
    fps: float,
    tracker: FinalizedTracker,
    debug: dict,
) -> None:
    if tracked_box is not None:
        x1, y1, x2, y2 = map(int, tracked_box)
        color = (0, 165, 255) if is_ghost else (0, 0, 255)
        thickness = 2 if is_ghost else 4
        state = "GHOST" if is_ghost else "LOCKED"
        label = f"TANMAY {state} conf={tracker.target_conf:.2f} lock={tracker.lock_score:.2f}"
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)
        cv2.rectangle(frame, (x1, max(0, y1 - 24)), (min(frame.shape[1], x1 + 330), y1), color, -1)
        cv2.putText(
            frame,
            label,
            (x1 + 6, max(14, y1 - 7)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            1,
            cv2.LINE_8,
        )

    hud_lines = [
        f"FPS: {fps:.1f}",
        f"Identity: {debug.get('identity_mode', 'n/a')}",
        f"Candidates: {debug.get('num_candidates', 0)}",
        f"Track tanmay only: {tracker.track_tanmay_only}",
    ]
    for idx, line in enumerate(hud_lines):
        cv2.putText(
            frame,
            line,
            (10, 30 + idx * 26),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 0),
            2,
            cv2.LINE_8,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Unified finalized tracker for Phase 2")
    parser.add_argument("--weights", type=str, default="../best.engine", help="Path to YOLO weights or TensorRT engine")
    parser.add_argument("--source", type=str, default="0", help="Camera index or video path")
    parser.add_argument("--target-class-id", type=int, default=0, help="Target class id for tanmay")
    parser.add_argument("--track-all-classes", action="store_true", help="Disable TRACK_TANMAY_ONLY optimization")
    parser.add_argument("--identity-mode", choices=["none", "histogram", "embedding"], default="none")
    parser.add_argument(
        "--embedding-model",
        choices=sorted(DEFAULT_EMBEDDING_WEIGHTS.keys()),
        default="osnet_x0_25",
        help="Embedding backbone to use when identity-mode=embedding",
    )
    parser.add_argument("--embedding-weights", type=str, default=None, help="Override embedding checkpoint path")
    parser.add_argument("--skip-frames", type=int, default=4, help="Number of frames to skip between embedding refreshes")
    parser.add_argument("--conf-start", type=float, default=0.60, help="Confidence threshold to acquire lock")
    parser.add_argument("--conf-keep", type=float, default=0.35, help="Confidence threshold to keep lock")
    parser.add_argument("--ghost-limit", type=int, default=15, help="Frames to keep ghost state alive")
    parser.add_argument("--max-det", type=int, default=0, help="Optional max detections override for YOLO")
    parser.add_argument("--camera-width", type=int, default=0, help="Optional camera width override")
    parser.add_argument("--camera-height", type=int, default=0, help="Optional camera height override")
    parser.add_argument("--headless", action="store_true", help="Disable OpenCV window rendering for true loop-FPS testing")
    parser.add_argument("--profile", action="store_true", help="Print timing breakdown every 30 frames")
    args = parser.parse_args()

    weights_path = Path(args.weights)
    if not weights_path.exists():
        raise FileNotFoundError(f"Weights not found: {weights_path}")

    print(f"Loading YOLO model: {weights_path}")
    model = YOLO(str(weights_path))
    identity_scorer = build_identity_scorer(args)
    tracker = FinalizedTracker(
        target_class_id=args.target_class_id,
        conf_start=args.conf_start,
        conf_keep=args.conf_keep,
        ghost_limit=args.ghost_limit,
        track_tanmay_only=not args.track_all_classes,
        identity_scorer=identity_scorer,
    )

    source = parse_source(args.source)
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open source: {args.source}")

    if args.camera_width > 0:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.camera_width)
    if args.camera_height > 0:
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.camera_height)

    window_name = "Phase 2 - Finalized Tracking"
    if not args.headless:
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window_name, 1280, 720)

    prev_time = time.time()
    fps = 0.0
    frame_count = 0
    capture_ms = 0.0
    infer_ms = 0.0
    track_ms = 0.0
    render_ms = 0.0

    print(
        "Running finalized tracker | "
        f"identity={identity_scorer.label} | "
        f"track_tanmay_only={tracker.track_tanmay_only}"
    )
    if args.headless:
        print("Headless mode enabled.")
    else:
        print("Press X to exit.")

    while True:
        loop_t0 = time.perf_counter()
        ok, frame = cap.read()
        if not ok:
            break
        t_after_capture = time.perf_counter()

        infer_kwargs = {"verbose": False}
        if args.max_det > 0:
            infer_kwargs["max_det"] = args.max_det
        result = model(frame, **infer_kwargs)[0]
        t_after_infer = time.perf_counter()

        boxes_data = result.boxes
        if boxes_data is not None and len(boxes_data) > 0:
            boxes = boxes_data.xyxy.detach().cpu().numpy()
            confs = boxes_data.conf.detach().cpu().numpy()
            classes = boxes_data.cls.detach().cpu().numpy()
        else:
            boxes = np.empty((0, 4), dtype=np.float32)
            confs = np.empty((0,), dtype=np.float32)
            classes = np.empty((0,), dtype=np.float32)

        tracked_box, is_ghost, debug = tracker.process(frame, boxes, confs, classes)
        t_after_track = time.perf_counter()

        curr_time = time.time()
        instant_fps = 1.0 / max(curr_time - prev_time, 1e-6)
        fps = instant_fps if fps == 0.0 else ((0.9 * fps) + (0.1 * instant_fps))
        prev_time = curr_time

        if not args.headless:
            draw_tracking_overlay(frame, tracked_box, is_ghost, fps, tracker, debug)
            cv2.imshow(window_name, frame)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("x"), ord("X")):
                break
        t_after_render = time.perf_counter()

        frame_count += 1
        capture_ms += (t_after_capture - loop_t0) * 1000.0
        infer_ms += (t_after_infer - t_after_capture) * 1000.0
        track_ms += (t_after_track - t_after_infer) * 1000.0
        render_ms += (t_after_render - t_after_track) * 1000.0

        if args.profile and frame_count % 30 == 0:
            denom = 30.0
            print(
                f"[profile] fps={fps:.1f} "
                f"capture={capture_ms / denom:.1f}ms "
                f"infer={infer_ms / denom:.1f}ms "
                f"track={track_ms / denom:.1f}ms "
                f"render={render_ms / denom:.1f}ms"
            )
            capture_ms = 0.0
            infer_ms = 0.0
            track_ms = 0.0
            render_ms = 0.0

    cap.release()
    if not args.headless:
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
