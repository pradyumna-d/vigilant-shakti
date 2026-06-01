import logging
from datetime import UTC, datetime

import httpx

from inference.confidence_filter import Detection
from inference.yolo_engine import encode_jpeg_base64
from utils.config import get_settings

logger = logging.getLogger(__name__)


class EventDispatcher:
    async def dispatch(self, camera_id: int, frame, detection: Detection, latency_ms: float) -> None:
        settings = get_settings()
        x1, y1, x2, y2 = detection.xyxy
        payload = {
            "camera_id": camera_id,
            "event_type": detection.label,
            "confidence": detection.confidence,
            "timestamp": datetime.now(UTC).isoformat(),
            "bbox": {"x": x1, "y": y1, "width": x2 - x1, "height": y2 - y1},
            "snapshot_jpeg_base64": encode_jpeg_base64(frame),
            "metadata": {"source": "ai-inference"},
            "inference_metadata": {"latency_ms": latency_ms, "engine": "yolov8"},
        }
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(f"{settings.backend_url}/api/events/ingest", json=payload)
            response.raise_for_status()
            logger.info("event_dispatched camera_id=%s label=%s", camera_id, detection.label)
