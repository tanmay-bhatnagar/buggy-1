import numpy as np

class BuggyTracker:
    """
    Simple Inference Scaffolding for the Follow-Me Buggy.
    Handles:
    - Highlander Rule (Closest to last position)
    - Ghosting (Stationary persistence)
    - Cross-Class NMS (Priority to Tanmay)
    """
    def __init__(self, 
                 target_class_id=0, 
                 conf_threshold_start=0.6, 
                 conf_threshold_keep=0.35, 
                 ghost_limit=15, 
                 iou_suppress=0.6):
        self.target_class_id = target_class_id
        self.conf_start = conf_threshold_start
        self.conf_keep = conf_threshold_keep
        self.ghost_limit = ghost_limit
        self.iou_suppress = iou_suppress
        
        self.target_active = False
        self.last_box = None
        self.missed_frames = 0
        self.target_conf = 0.0

    def calculate_iou(self, boxA, boxB):
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
        # 1. Class Split
        raw_targets = []
        others = []
        for box, conf, cls in zip(boxes, confs, class_ids):
            if int(cls) == self.target_class_id:
                raw_targets.append((box, conf))
            else:
                others.append((box, conf, cls))

        # 2. Priority NMS
        filtered_others = []
        for o_box, o_conf, o_cls in others:
            if not any(self.calculate_iou(o_box, t_box) > self.iou_suppress for t_box, _ in raw_targets):
                filtered_others.append((o_box, o_conf, o_cls))

        # 3. Find Best Target
        best_target = None
        best_conf = 0.0
        threshold = self.conf_keep if self.target_active else self.conf_start
        valid_targets = [t for t in raw_targets if t[1] > threshold]

        if valid_targets:
            if self.target_active:
                last_center = np.array([(self.last_box[0] + self.last_box[2]) / 2, 
                                        (self.last_box[1] + self.last_box[3]) / 2])
                min_dist = float('inf')
                for t_box, t_conf in valid_targets:
                    center = np.array([(t_box[0] + t_box[2]) / 2, (t_box[1] + t_box[3]) / 2])
                    dist = np.linalg.norm(center - last_center)
                    if dist < min_dist:
                        min_dist = dist
                        best_target = t_box
                        best_conf = t_conf
            else:
                valid_targets.sort(key=lambda x: x[1], reverse=True)
                best_target = valid_targets[0][0]
                best_conf = valid_targets[0][1]

        # 4. State Update
        if best_target is not None:
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
                else:
                    self.target_conf *= 0.9

        return (self.last_box if self.target_active else None, 
                self.missed_frames > 0 if self.target_active else False,
                filtered_others)
