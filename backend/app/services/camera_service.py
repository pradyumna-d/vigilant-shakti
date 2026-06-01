import logging
from datetime import UTC, datetime
from urllib.parse import quote

import httpx
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.camera import Camera, CameraState, CameraStream
from app.schemas.camera import CameraCreate, CameraCredentials
from app.services.onvif_media_service import resolve_rtsp_url

logger = logging.getLogger(__name__)
DEFAULT_DETECTION_CLASSES = ["person", "phone", "pigeon"]


def _stream_path(camera_id: int) -> str:
    return f"camera-{camera_id}-processed"


def _raw_stream_path(camera_id: int) -> str:
    return f"camera-{camera_id}-raw"


def camera_detection_classes(camera: Camera) -> list[str]:
    classes = (camera.metadata_json or {}).get("detection_classes")
    if isinstance(classes, list):
        valid = [item for item in classes if item in DEFAULT_DETECTION_CLASSES]
        if valid:
            return valid
    return DEFAULT_DETECTION_CLASSES.copy()


async def configure_mediamtx_camera_source(camera: Camera) -> str:
    settings = get_settings()
    if not camera.rtsp_url:
        raise ValueError("camera has no RTSP URL")

    path = _raw_stream_path(camera.id)
    api_url = settings.mediamtx_api_url.rstrip("/")
    payload = {
        "source": camera.rtsp_url,
        "sourceOnDemand": True,
        "sourceOnDemandStartTimeout": "15s",
        "sourceOnDemandCloseAfter": "30s",
        "rtspTransport": "tcp",
    }
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(f"{api_url}/v3/config/paths/add/{quote(path, safe='')}", json=payload)
        if response.status_code in (400, 409):
            delete_response = await client.delete(f"{api_url}/v3/config/paths/delete/{quote(path, safe='')}")
            if delete_response.status_code not in (200, 404):
                delete_response.raise_for_status()
            response = await client.post(f"{api_url}/v3/config/paths/add/{quote(path, safe='')}", json=payload)
        response.raise_for_status()
    return f"{settings.mediamtx_rtsp_url}/{quote(path)}"


async def upsert_discovered_camera(session: AsyncSession, payload: CameraCreate) -> tuple[Camera, bool]:
    query = select(Camera).where(
        Camera.ip_address == payload.ip_address,
        Camera.onvif_endpoint == payload.onvif_endpoint,
    )
    existing = (await session.execute(query)).scalar_one_or_none()
    now = datetime.now(UTC)
    if existing:
        existing.last_seen_at = now
        existing.manufacturer = payload.manufacturer or existing.manufacturer
        existing.model = payload.model or existing.model
        return existing, False

    camera = Camera(
        name=payload.name,
        ip_address=payload.ip_address,
        manufacturer=payload.manufacturer,
        model=payload.model,
        onvif_endpoint=payload.onvif_endpoint,
        rtsp_url=payload.rtsp_url,
        state=CameraState.discovered,
        last_seen_at=now,
    )
    session.add(camera)
    await session.flush()
    camera.stream_path = _stream_path(camera.id)
    return camera, True


async def configure_camera_credentials(
    session: AsyncSession,
    camera: Camera,
    credentials: CameraCredentials,
) -> Camera:
    camera.rtsp_url = await resolve_rtsp_url(camera.onvif_endpoint, credentials.username, credentials.password)
    camera.credentials_configured = True
    camera.state = CameraState.online
    camera.metadata_json = {
        **(camera.metadata_json or {}),
        "auth_username": credentials.username,
        "auth_configured_at": datetime.now(UTC).isoformat(),
        "detection_classes": (camera.metadata_json or {}).get("detection_classes", DEFAULT_DETECTION_CLASSES),
    }
    if not camera.stream_path:
        camera.stream_path = _stream_path(camera.id)
    return camera


async def ensure_stream_record(session: AsyncSession, camera: Camera) -> CameraStream:
    settings = get_settings()
    path = camera.stream_path or _stream_path(camera.id)
    camera.stream_path = path
    input_rtsp_url = f"{settings.mediamtx_rtsp_url}/{quote(_raw_stream_path(camera.id))}" if camera.rtsp_url else ""
    processed_rtsp_url = f"{settings.mediamtx_rtsp_url}/{path}"
    webrtc_url = f"{settings.mediamtx_webrtc_base_url}/{path}"
    existing = (
        await session.execute(select(CameraStream).where(CameraStream.camera_id == camera.id))
    ).scalar_one_or_none()
    if existing:
        existing.input_rtsp_url = input_rtsp_url or existing.input_rtsp_url
        existing.processed_rtsp_url = processed_rtsp_url
        existing.webrtc_url = webrtc_url
        return existing
    stream = CameraStream(
        camera_id=camera.id,
        input_rtsp_url=input_rtsp_url,
        processed_rtsp_url=processed_rtsp_url,
        webrtc_url=webrtc_url,
        status="starting",
    )
    session.add(stream)
    return stream


async def start_inference_stream(camera: Camera) -> dict:
    settings = get_settings()
    if not camera.rtsp_url:
        raise ValueError("camera has no RTSP URL")

    inference_base_url = str(settings.ai_inference_url).rstrip("/")
    stream_path = camera.stream_path or _stream_path(camera.id)
    inference_input_rtsp_url = await configure_mediamtx_camera_source(camera)
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            f"{inference_base_url}/streams/start",
            headers={"X-Shakti-Token": settings.ai_inference_api_token},
            json={
                "camera_id": camera.id,
                "rtsp_url": inference_input_rtsp_url,
                "stream_path": stream_path,
                "processed_rtsp_url": f"{settings.mediamtx_rtsp_url}/{quote(stream_path)}",
                "detection_classes": camera_detection_classes(camera),
            },
        )
        response.raise_for_status()
        return response.json()


async def active_inference_camera_ids() -> set[int]:
    settings = get_settings()
    inference_base_url = str(settings.ai_inference_url).rstrip("/")
    async with httpx.AsyncClient(timeout=5) as client:
        response = await client.get(f"{inference_base_url}/streams")
        response.raise_for_status()
    active_ids: set[int] = set()
    for item in response.json():
        camera_id = item.get("camera_id")
        if isinstance(camera_id, int) and item.get("status") != "stopped":
            active_ids.add(camera_id)
    return active_ids


async def reconcile_authenticated_streams(session: AsyncSession) -> None:
    try:
        active_ids = await active_inference_camera_ids()
    except Exception:
        logger.exception("inference_stream_reconcile_failed")
        return

    result = await session.execute(
        select(Camera).where(
            Camera.credentials_configured.is_(True),
            Camera.rtsp_url.is_not(None),
        )
    )
    cameras = result.scalars().all()
    for camera in cameras:
        stream = await ensure_stream_record(session, camera)
        if camera.id in active_ids:
            stream.status = "running"
            camera.state = CameraState.online
            continue
        try:
            response = await start_inference_stream(camera)
            stream.status = response.get("status", "starting")
            stream.processed_rtsp_url = response.get("processed_rtsp_url", stream.processed_rtsp_url)
            stream.webrtc_url = response.get("webrtc_url", stream.webrtc_url)
            stream.metadata_json = None
            camera.state = CameraState.online
            logger.info("inference_stream_reconciled camera_id=%s", camera.id)
        except Exception as exc:
            logger.exception("inference_stream_reconcile_start_failed camera_id=%s", camera.id)
            stream.status = "error"
            stream.metadata_json = {"error": str(exc)}
            camera.state = CameraState.error
    await session.commit()


def set_detection_classes(camera: Camera, detection_classes: list[str]) -> None:
    valid = [item for item in detection_classes if item in DEFAULT_DETECTION_CLASSES]
    if not valid:
        raise ValueError("Select at least one supported class")
    camera.metadata_json = {
        **(camera.metadata_json or {}),
        "detection_classes": valid,
    }


async def camera_counts(session: AsyncSession) -> dict[str, int]:
    total = await session.scalar(select(func.count(Camera.id)))
    online = await session.scalar(select(func.count(Camera.id)).where(Camera.state == CameraState.online))
    active_streams = await session.scalar(
        select(func.count(CameraStream.id)).where(CameraStream.status.in_(["starting", "running"]))
    )
    return {"total": total or 0, "online": online or 0, "active_streams": active_streams or 0}
