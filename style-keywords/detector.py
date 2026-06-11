import numpy as np
import cv2
from ultralytics import YOLO

# 0 = person class in COCO
PERSON_CLASS = 0
MIN_CONFIDENCE = 0.5
# minimum pixel area to bother analyzing
MIN_CROP_AREA = 10000


class PersonDetector:
    def __init__(self):
        # yolov8n is the lightest model, runs fine on CPU
        self.model = YOLO("yolov8n.pt")

    def get_person_crops(self, frame: np.ndarray) -> list[np.ndarray]:
        results = self.model(frame, verbose=False)[0]
        crops = []
        for box in results.boxes:
            if int(box.cls[0]) != PERSON_CLASS:
                continue
            if float(box.conf[0]) < MIN_CONFIDENCE:
                continue
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            # add small padding
            h, w = frame.shape[:2]
            x1 = max(0, x1 - 10)
            y1 = max(0, y1 - 10)
            x2 = min(w, x2 + 10)
            y2 = min(h, y2 + 10)
            crop = frame[y1:y2, x1:x2]
            if crop.size >= MIN_CROP_AREA:
                crops.append(crop)
        return crops
