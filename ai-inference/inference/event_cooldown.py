import time


class EventCooldown:
    def __init__(self, seconds: int) -> None:
        self.seconds = seconds
        self._last_seen: dict[tuple[int, str], float] = {}

    def allow(self, camera_id: int, label: str) -> bool:
        key = (camera_id, label)
        now = time.monotonic()
        last = self._last_seen.get(key)
        if last is not None and now - last < self.seconds:
            return False
        self._last_seen[key] = now
        return True
