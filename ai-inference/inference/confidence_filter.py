from dataclasses import dataclass

from utils.config import get_settings


@dataclass(frozen=True)
class Detection:
    label: str
    confidence: float
    xyxy: tuple[float, float, float, float]


class ConfidenceFilter:
    def __init__(self) -> None:
        settings = get_settings()
        self.thresholds = {
            "person": settings.person_confidence_threshold,
            "phone": settings.phone_confidence_threshold,
            "pigeon": settings.pigeon_confidence_threshold,
        }

    def keep(self, detection: Detection) -> bool:
        threshold = self.thresholds.get(detection.label)
        return threshold is not None and detection.confidence >= threshold
