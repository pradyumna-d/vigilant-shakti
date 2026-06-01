from inference.confidence_filter import ConfidenceFilter, Detection
from zones.zone_manager import ZoneManager


class DetectionLogic:
    def __init__(self) -> None:
        self.confidence_filter = ConfidenceFilter()
        self.zone_manager = ZoneManager()

    def filter(self, camera_id: int, detections: list[Detection]) -> list[Detection]:
        kept = [d for d in detections if self.confidence_filter.keep(d)]
        return [d for d in kept if self.zone_manager.allow(camera_id, d)]
