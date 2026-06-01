import logging
import shutil
from pathlib import Path

import cv2

from inference.confidence_filter import Detection
from utils.config import get_settings

logger = logging.getLogger(__name__)


class YoloEngine:
    def __init__(self) -> None:
        from ultralytics import YOLO

        settings = get_settings()
        model_path = Path(settings.yolo_model_path)
        model_path.parent.mkdir(parents=True, exist_ok=True)
        source = str(model_path) if model_path.exists() else settings.yolo_model_name
        logger.info("loading_yolo_model source=%s", source)
        self.model = YOLO(source)
        if not model_path.exists() and Path(settings.yolo_model_name).exists():
            shutil.move(settings.yolo_model_name, model_path)
        self.names = self.model.names

    def detect(self, frame) -> list[Detection]:
        results = self.model.predict(frame, verbose=False, device=None)[0]
        detections: list[Detection] = []
        for box in results.boxes:
            cls_id = int(box.cls[0])
            coco_label = str(self.names.get(cls_id, cls_id))
            label = self._map_label(coco_label)
            if not label:
                continue
            x1, y1, x2, y2 = [float(v) for v in box.xyxy[0].tolist()]
            detections.append(
                Detection(
                    label=label,
                    confidence=float(box.conf[0]),
                    xyxy=(x1, y1, x2, y2),
                )
            )
        return detections

    @staticmethod
    def _map_label(coco_label: str) -> str | None:
        if coco_label == "person":
            return "person"
        if coco_label == "cell phone":
            return "phone"
        if coco_label == "bird":
            return "pigeon"
        return None


def encode_jpeg_base64(frame, quality: int = 72) -> str | None:
    import base64

    ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        return None
    return base64.b64encode(encoded.tobytes()).decode()
