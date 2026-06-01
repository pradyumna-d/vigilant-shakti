import cv2

from inference.confidence_filter import Detection


class OverlayRenderer:
    def render(self, frame, detections: list[Detection]):
        for detection in detections:
            x1, y1, x2, y2 = [int(v) for v in detection.xyxy]
            color = (219, 241, 87) if detection.label == "person" else (255, 198, 173)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            label = f"{detection.label.upper()} {detection.confidence:.2f}"
            cv2.putText(frame, label, (x1, max(20, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)
        return frame
