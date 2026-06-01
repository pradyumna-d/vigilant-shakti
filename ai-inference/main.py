import asyncio
import logging
import subprocess
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from rtsp.url import processed_rtsp_url
from stream_workers.camera_worker import CameraWorker
from utils.config import get_settings
from utils.logging import configure_logging

configure_logging()
logger = logging.getLogger(__name__)
settings = get_settings()
app = FastAPI(title="Vigilant Shakti AI Inference", version="0.1.0")

workers: dict[int, CameraWorker] = {}
tasks: dict[int, asyncio.Task] = {}


class StreamStart(BaseModel):
    camera_id: int
    rtsp_url: str
    stream_path: str
    processed_rtsp_url: str | None = None
    detection_classes: list[str] = ["person", "phone", "pigeon"]


def require_token(token: str | None) -> None:
    if settings.ai_inference_api_token and token != settings.ai_inference_api_token:
        raise HTTPException(status_code=401, detail="Invalid inference token")


@app.get("/health")
async def health() -> dict[str, Any]:
    gpu: dict[str, float | None] = {"gpu_percent": None, "vram_used_mb": None, "vram_total_mb": None}
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=utilization.gpu,memory.used,memory.total",
                "--format=csv,noheader,nounits",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
        gpu_percent, vram_used, vram_total = [float(value.strip()) for value in result.stdout.splitlines()[0].split(",")]
        gpu = {"gpu_percent": gpu_percent, "vram_used_mb": vram_used, "vram_total_mb": vram_total}
    except Exception:
        pass
    return {"status": "ok", "service": "ai-inference", "workers": len(workers), **gpu}


@app.post("/streams/start")
async def start_stream(payload: StreamStart, x_shakti_token: str | None = Header(default=None)) -> dict:
    require_token(x_shakti_token)
    if payload.camera_id in tasks and not tasks[payload.camera_id].done():
        worker = workers[payload.camera_id]
        if worker.rtsp_url != payload.rtsp_url or (
            payload.processed_rtsp_url and worker.processed_rtsp_url != payload.processed_rtsp_url
        ):
            await worker.stop()
            await asyncio.wait([tasks[payload.camera_id]], timeout=5)
            workers.pop(payload.camera_id, None)
            tasks.pop(payload.camera_id, None)
        else:
            worker.set_detection_classes(payload.detection_classes)
            return {
                "camera_id": payload.camera_id,
                "status": worker.status.status,
                "processed_rtsp_url": worker.processed_rtsp_url,
                "webrtc_url": f"/{payload.stream_path}",
            }

    if payload.camera_id in tasks and not tasks[payload.camera_id].done():
        worker = workers[payload.camera_id]
        worker.set_detection_classes(payload.detection_classes)
        return {
            "camera_id": payload.camera_id,
            "status": worker.status.status,
            "processed_rtsp_url": worker.processed_rtsp_url,
            "webrtc_url": f"/{payload.stream_path}",
        }

    output_url = payload.processed_rtsp_url or processed_rtsp_url(settings.mediamtx_rtsp_url, payload.stream_path)
    worker = CameraWorker(payload.camera_id, payload.rtsp_url, payload.stream_path, output_url, payload.detection_classes)
    workers[payload.camera_id] = worker
    tasks[payload.camera_id] = asyncio.create_task(worker.run())
    logger.info("stream_worker_started camera_id=%s path=%s", payload.camera_id, payload.stream_path)
    return {
        "camera_id": payload.camera_id,
        "status": "starting",
        "processed_rtsp_url": output_url,
        "webrtc_url": f"/{payload.stream_path}",
    }


@app.post("/streams/{camera_id}/stop")
async def stop_stream(camera_id: int, x_shakti_token: str | None = Header(default=None)) -> dict:
    require_token(x_shakti_token)
    worker = workers.get(camera_id)
    if not worker:
        return {"camera_id": camera_id, "status": "not_found"}
    await worker.stop()
    task = tasks.get(camera_id)
    if task:
        await asyncio.wait([task], timeout=5)
    workers.pop(camera_id, None)
    tasks.pop(camera_id, None)
    return {"camera_id": camera_id, "status": "stopped"}


@app.get("/streams")
async def list_streams() -> list[dict[str, Any]]:
    return [
        {
            "camera_id": worker.camera_id,
            "status": worker.status.status,
            "fps": worker.status.fps,
            "latency_ms": worker.status.latency_ms,
            "reconnect_count": worker.status.reconnect_count,
            "error": worker.status.error,
            "processed_rtsp_url": worker.processed_rtsp_url,
            "camera_reported_fps": worker.status.camera_reported_fps,
            "input_read_fps": worker.status.input_read_fps,
            "output_publish_fps": worker.status.output_publish_fps,
            "yolo_fps": worker.status.yolo_fps,
            "yolo_latency_ms": worker.status.yolo_latency_ms,
            "last_frame_age_ms": worker.status.last_frame_age_ms,
            "dropped_frames": worker.status.dropped_frames,
            "event_queue_depth": worker.status.event_queue_depth,
            "event_dispatch_failures": worker.status.event_dispatch_failures,
            "publisher_restarts": worker.status.publisher_restarts,
            "last_publish_error": worker.status.last_publish_error,
            "publish_latency_ms": worker.status.publish_latency_ms,
            "loop_latency_ms": worker.status.loop_latency_ms,
            "snapshot_latency_ms": worker.status.snapshot_latency_ms,
            "resize_latency_ms": worker.status.resize_latency_ms,
            "render_latency_ms": worker.status.render_latency_ms,
            "output_width": worker.status.output_width,
            "output_height": worker.status.output_height,
            "decoder_backend": worker.status.decoder_backend,
            "decoder_restarts": worker.status.decoder_restarts,
            "decoder_stderr_tail": worker.status.decoder_stderr_tail,
            "frame_buffer_leases": worker.status.frame_buffer_leases,
            "frame_buffer_drops": worker.status.frame_buffer_drops,
        }
        for worker in workers.values()
    ]
