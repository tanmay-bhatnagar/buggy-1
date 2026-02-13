import numpy as np
import cv2

class BuggyTracker:
    """
    Advanced Inference Scaffolding for the Follow-Me Buggy.
    Uses:
    - Cross-Class NMS (Priority to Tanmay)
    - Color Histograms (Visual identity/Fingerprinting)
    - Kalman Filter (Constant Velocity motion smoothing & prediction)
    - Ghosting (Persistence during occlusion)
    """
    def __init__(self, 
                 target_class_id=0, 
                 conf_threshold_start=0.6, 
                 conf_threshold_keep=0.35, 
                 ghost_limit=15, 
                 iou_suppress=0.6,
                 use_histogram=True,
                 use_kalman=True):
        self.target_class_id = target_class_id
        self.conf_start = conf_threshold_start
        self.conf_keep = conf_threshold_keep
        self.ghost_limit = ghost_limit
        self.iou_suppress = iou_suppress
        self.use_histogram = use_histogram
        self.use_kalman = use_kalman
        
        self.target_active = False
        self.last_box = None  # [x1, y1, x2, y2]
        self.missed_frames = 0
        self.target_conf = 0.0
        
        # Visual Fingerprint (Internal memory of what you look like)
        self.target_hist = None
        
        # Kalman Filter Initialization (Constant Velocity)
        if self.use_kalman:
            self.kf = cv2.KalmanFilter(4, 2) # 4 state vars (x,y,dx,dy), 2 measured (x,y)
            self.kf.measurementMatrix = np.array([[1, 0, 0, 0], 
                                                  [0, 1, 0, 0]], np.float32)
            self.kf.transitionMatrix = np.array([[1, 0, 1, 0], 
                                                 [0, 1, 0, 1], 
                                                 [0, 0, 1, 0], 
                                                 [0, 0, 0, 1]], np.float32)
            self.kf.processNoiseCov = np.eye(4, dtype=np.float32) * 0.03

    def get_color_hist(self, image, box):
        """Extract HSV color histogram from a bounding box."""
        x1, y1, x2, y2 = map(int, box)
        # Ensure box is within image bounds
        h, w = image.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        
        if x2 <= x1 or y2 <= y1: return None
        
        roi = image[y1:y2, x1:x2]
        hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        
        # Calculate histogram (Hue and Saturation)
        hist = cv2.calcHist([hsv_roi], [0, 1], None, [16, 16], [0, 180, 0, 256])
        cv2.normalize(hist, hist, 0, 255, cv2.NORM_MINMAX)
        return hist

    def calculate_iou(self, boxA, boxB):
        """Standard Intersection over Union."""
        xA = max(boxA[0], boxB[0])
        yA = max(boxA[1], boxB[1])
        xB = min(boxA[2], boxB[2])
        yB = min(boxA[3], boxB[3])
        interArea = max(0, xB - xA) * max(0, yB - yA)
        boxAArea = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
        boxBArea = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])
        iou = interArea / float(boxAArea + boxBArea - interArea + 1e-6)
        return iou

    def process_detections(self, image, boxes, confs, class_ids):
        """
        Refine raw detections using scaffolding logic.
        """
        # 1. Split and Filter
        raw_targets = []  # (box, conf)
        others = []       # (box, conf, id)
        
        for box, conf, cls in zip(boxes, confs, class_ids):
            if int(cls) == self.target_class_id:
                raw_targets.append((box, conf))
            else:
                others.append((box, conf, cls))

        # 2. Cross-Class NMS (Priority to Tanmay)
        filtered_others = []
        for o_box, o_conf, o_cls in others:
            if not any(self.calculate_iou(o_box, t_box) > self.iou_suppress for t_box, _ in raw_targets):
                filtered_others.append((o_box, o_conf, o_cls))

        # 3. Kalman Prediction (Where do we expect him to be?)
        predicted_pos = None
        if self.target_active and self.use_kalman:
            prediction = self.kf.predict()
            predicted_pos = (prediction[0], prediction[1])

        # 4. Find the Best Target (Visual Fingerprint + Spatial Logic)
        best_target = None
        best_conf = 0.0
        
        threshold = self.conf_keep if self.target_active else self.conf_start
        valid_targets = [t for t in raw_targets if t[1] > threshold]
        
        if valid_targets:
            scores = []
            for t_box, t_conf in valid_targets:
                # Base score is confidence
                score = t_conf
                
                # Spatial penalty (Distance from prediction or last known)
                t_center = np.array([(t_box[0] + t_box[2])/2, (t_box[1] + t_box[3])/2])
                ref_pos = predicted_pos if predicted_pos else (
                    np.array([(self.last_box[0]+self.last_box[2])/2, (self.last_box[1]+self.last_box[3])/2]) 
                    if self.target_active else None
                )
                
                if ref_pos is not None:
                    dist = np.linalg.norm(t_center - ref_pos)
                    # Penalty increases with distance (simple normalized distance)
                    score -= (dist / 1000.0) 

                # Visual Identity penalty (Histogram check)
                if self.target_hist is not None and self.use_histogram:
                    current_hist = self.get_color_hist(image, t_box)
                    if current_hist is not None:
                        sim = cv2.compareHist(self.target_hist, current_hist, cv2.HISTCMP_CORREL)
                        # Correlation is 0 to 1. We boost score if highly similar.
                        score += (sim * 0.5) 
                
                scores.append((t_box, t_conf, score))
            
            # Sort by total score
            scores.sort(key=lambda x: x[2], reverse=True)
            best_target, best_conf, _ = scores[0]

        # 5. State Update
        if best_target is not None:
            # First lock? Capture the fingerprint
            if self.target_hist is None and self.use_histogram:
                self.target_hist = self.get_color_hist(image, best_target)
            
            # Update Kalman with new measurement
            if self.use_kalman:
                center = np.array([[(best_target[0] + best_target[2]) / 2], 
                                   [(best_target[1] + best_target[3]) / 2]], np.float32)
                self.kf.correct(center)
            
            self.target_active = True
            self.last_box = best_target
            self.target_conf = best_conf
            self.missed_frames = 0
        else:
            if self.target_active:
                self.missed_frames += 1
                if self.missed_frames > self.ghost_limit:
                    self.target_active = False
                    self.last_box = None
                    self.target_hist = None # Forget fingerprint if lost too long
                else:
                    # GHOSTING: use Kalman prediction to move the box if we can
                    if self.use_kalman:
                        pred = self.kf.predict()
                        dx = pred[0] - (self.last_box[0] + self.last_box[2])/2
                        dy = pred[1] - (self.last_box[1] + self.last_box[3])/2
                        self.last_box = [self.last_box[0]+dx, self.last_box[1]+dy, 
                                         self.last_box[2]+dx, self.last_box[3]+dy]
                    self.target_conf *= 0.9

        return (self.last_box if self.target_active else None, 
                self.missed_frames > 0 if self.target_active else False,
                filtered_others)
