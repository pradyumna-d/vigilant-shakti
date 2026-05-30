from typing import Any

from pydantic import BaseModel


class DashboardMetrics(BaseModel):
    cameras_total: int
    cameras_online: int
    active_streams: int
    events_total: int
    recent_events: int
    cpu_percent: float
    ram_percent: float
    gpu_percent: float | None
    vram_percent: float | None
    vram_used_mb: float | None = None
    vram_total_mb: float | None = None
    service_memory: dict[str, Any] = {}
    service_health: dict[str, str]
    extra: dict[str, Any] = {}
