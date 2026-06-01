from collections import deque
import time


class RateMeter:
    def __init__(self, window_seconds: float = 10.0) -> None:
        self.count = 0
        self.window_seconds = window_seconds
        self.started_at = time.monotonic()
        self._ticks: deque[float] = deque()

    def tick(self, count: int = 1) -> None:
        self.count += count
        now = time.monotonic()
        for _ in range(count):
            self._ticks.append(now)
        self._trim(now)

    def _trim(self, now: float | None = None) -> None:
        now = now or time.monotonic()
        cutoff = now - self.window_seconds
        while self._ticks and self._ticks[0] < cutoff:
            self._ticks.popleft()

    @property
    def rate(self) -> float:
        now = time.monotonic()
        self._trim(now)
        elapsed = min(max(now - self.started_at, 0.001), self.window_seconds)
        return len(self._ticks) / elapsed


class StreamMetrics:
    def __init__(self) -> None:
        self.frames = 0
        self.started_at = time.monotonic()
        self.latency_ms = 0.0

    def tick(self, latency_ms: float) -> None:
        self.frames += 1
        self.latency_ms = latency_ms

    @property
    def fps(self) -> float:
        elapsed = max(time.monotonic() - self.started_at, 0.001)
        return self.frames / elapsed
