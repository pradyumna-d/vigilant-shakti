from inference.confidence_filter import Detection


class ZoneManager:
    """Hook point for polygon, tripwire, and exclusion-region rules."""

    def allow(self, camera_id: int, detection: Detection) -> bool:
        return True
