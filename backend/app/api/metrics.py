import asyncio
import json

import httpx
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.system_metrics import read_system_metrics
from app.core.config import get_settings
from app.db.session import get_session
from app.schemas.metrics import DashboardMetrics
from app.services.camera_service import camera_counts
from app.services.event_service import event_counts

router = APIRouter(prefix="/metrics", tags=["metrics"])


async def _health(url: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=2) as client:
            response = await client.get(url)
            return "online" if response.status_code < 500 else "degraded"
    except Exception:
        return "offline"


async def _json_health(url: str) -> tuple[str, dict]:
    try:
        async with httpx.AsyncClient(timeout=2) as client:
            response = await client.get(url)
            status = "online" if response.status_code < 500 else "degraded"
            return status, response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
    except Exception:
        return "offline", {}


async def _dashboard_metrics(session: AsyncSession) -> DashboardMetrics:
    settings = get_settings()
    cameras = await camera_counts(session)
    events = await event_counts(session)
    system = read_system_metrics()
    inference_health, inference_payload = await _json_health(f"{str(settings.ai_inference_url).rstrip('/')}/health")
    mediamtx_health = await _health(f"{settings.mediamtx_api_url.rstrip('/')}/v3/config/global/get")
    gpu_percent = system["gpu_percent"] if system["gpu_percent"] is not None else inference_payload.get("gpu_percent")
    vram_used = system.get("vram_used_mb") if system.get("vram_used_mb") is not None else inference_payload.get("vram_used_mb")
    vram_total = system.get("vram_total_mb") if system.get("vram_total_mb") is not None else inference_payload.get("vram_total_mb")
    vram_percent = system["vram_percent"]
    if vram_percent is None and vram_used is not None and vram_total:
        vram_percent = (float(vram_used) / float(vram_total)) * 100
    return DashboardMetrics(
        cameras_total=cameras["total"],
        cameras_online=cameras["online"],
        active_streams=cameras["active_streams"],
        events_total=events["total"],
        recent_events=events["recent"],
        cpu_percent=system["cpu_percent"],
        ram_percent=system["ram_percent"],
        gpu_percent=gpu_percent,
        vram_percent=vram_percent,
        vram_used_mb=vram_used,
        vram_total_mb=vram_total,
        service_memory=system.get("service_memory", {}),
        service_health={
            "backend": "online",
            "ai-inference": inference_health,
            "shakti-webrtc": mediamtx_health,
            "mysql": "online",
        },
    )


@router.get("/dashboard", response_model=DashboardMetrics)
async def dashboard_metrics(session: AsyncSession = Depends(get_session)) -> DashboardMetrics:
    return await _dashboard_metrics(session)


@router.get("/dashboard/stream")
async def dashboard_metrics_stream(session: AsyncSession = Depends(get_session)) -> StreamingResponse:
    async def events():
        while True:
            payload = (await _dashboard_metrics(session)).model_dump()
            yield f"event: metrics\ndata: {json.dumps(payload)}\n\n"
            await asyncio.sleep(10)

    return StreamingResponse(events(), media_type="text/event-stream")


@router.get("/system")
async def system_metrics() -> dict:
    return read_system_metrics()
