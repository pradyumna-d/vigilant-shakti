import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.discovery.onvif_discovery import scan_onvif
from app.models.camera import Camera, CameraState
from app.schemas.camera import CameraCreate, CameraCredentials, CameraDetectionClasses, CameraRead, DiscoveryResult
from app.services.camera_service import (
    camera_detection_classes,
    configure_camera_credentials,
    ensure_stream_record,
    set_detection_classes,
    start_inference_stream,
    upsert_discovered_camera,
)
from app.websocket.manager import ws_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/cameras", tags=["cameras"])


def _camera_read(camera: Camera) -> CameraRead:
    payload = CameraRead.model_validate(camera)
    payload.detection_classes = camera_detection_classes(camera)
    return payload


@router.get("", response_model=list[CameraRead])
async def list_cameras(session: AsyncSession = Depends(get_session)) -> list[CameraRead]:
    result = await session.execute(select(Camera).order_by(Camera.id.desc()))
    return [_camera_read(camera) for camera in result.scalars().all()]


@router.post("", response_model=CameraRead, status_code=201)
async def create_camera(payload: CameraCreate, session: AsyncSession = Depends(get_session)) -> CameraRead:
    camera, _ = await upsert_discovered_camera(session, payload)
    await session.commit()
    await session.refresh(camera)
    await ws_manager.broadcast("camera.updated", _camera_read(camera).model_dump())
    return _camera_read(camera)


@router.post("/discover", response_model=DiscoveryResult)
async def discover_cameras(session: AsyncSession = Depends(get_session)) -> DiscoveryResult:
    discovered = await scan_onvif()
    created = 0
    cameras: list[Camera] = []
    for item in discovered:
        camera, is_created = await upsert_discovered_camera(
            session,
            CameraCreate(
                name=f"ONVIF {item.ip_address}",
                ip_address=item.ip_address,
                manufacturer=item.manufacturer,
                model=item.model,
                onvif_endpoint=item.onvif_endpoint,
            ),
        )
        created += int(is_created)
        cameras.append(camera)
    await session.commit()
    for camera in cameras:
        await session.refresh(camera)
    payload = DiscoveryResult(
        discovered=created,
        updated=len(cameras) - created,
        cameras=[_camera_read(camera) for camera in cameras],
    )
    await ws_manager.broadcast("camera.discovery.completed", payload.model_dump())
    return payload


@router.post("/{camera_id}/credentials", response_model=CameraRead)
async def set_camera_credentials(
    camera_id: int,
    payload: CameraCredentials,
    session: AsyncSession = Depends(get_session),
) -> CameraRead:
    camera = await session.get(Camera, camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    try:
        await configure_camera_credentials(session, camera, payload)
        stream = await ensure_stream_record(session, camera)
        response = await start_inference_stream(camera)
        stream.status = response.get("status", "starting")
        stream.processed_rtsp_url = response.get("processed_rtsp_url", stream.processed_rtsp_url)
        stream.webrtc_url = response.get("webrtc_url", stream.webrtc_url)
        await session.commit()
    except Exception as exc:
        await session.rollback()
        logger.exception("camera_credentials_failed camera_id=%s", camera_id)
        raise HTTPException(status_code=502, detail=f"Could not authenticate camera and start inference: {exc}") from exc
    await session.refresh(camera)
    await ws_manager.broadcast("camera.updated", _camera_read(camera).model_dump())
    await ws_manager.broadcast("stream.started", {"camera_id": camera_id})
    return _camera_read(camera)


@router.post("/{camera_id}/detection-classes", response_model=CameraRead)
async def update_camera_detection_classes(
    camera_id: int,
    payload: CameraDetectionClasses,
    session: AsyncSession = Depends(get_session),
) -> CameraRead:
    camera = await session.get(Camera, camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    try:
        set_detection_classes(camera, payload.detection_classes)
        stream = await ensure_stream_record(session, camera)
        if camera.credentials_configured:
            response = await start_inference_stream(camera)
            stream.status = response.get("status", stream.status)
        await session.commit()
    except Exception as exc:
        await session.rollback()
        raise HTTPException(status_code=502, detail=f"Could not update detection classes: {exc}") from exc
    await session.refresh(camera)
    await ws_manager.broadcast("camera.updated", _camera_read(camera).model_dump())
    return _camera_read(camera)


@router.post("/{camera_id}/streams/start")
async def start_camera_stream(camera_id: int, session: AsyncSession = Depends(get_session)) -> dict:
    camera = await session.get(Camera, camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    if not camera.credentials_configured:
        raise HTTPException(status_code=409, detail="Camera credentials must be configured before ingest")
    stream = await ensure_stream_record(session, camera)
    try:
        response = await start_inference_stream(camera)
    except Exception as exc:
        logger.exception("inference_start_failed camera_id=%s", camera_id)
        camera.state = CameraState.error
        stream.status = "error"
        stream.metadata_json = {"error": str(exc)}
        await session.commit()
        raise HTTPException(status_code=502, detail=f"Inference service failed: {exc}") from exc
    stream.status = response.get("status", "starting")
    stream.processed_rtsp_url = response.get("processed_rtsp_url", stream.processed_rtsp_url)
    stream.webrtc_url = response.get("webrtc_url", stream.webrtc_url)
    await session.commit()
    await ws_manager.broadcast("stream.started", {"camera_id": camera_id, **response})
    return response


@router.post("/{camera_id}/streams/stop")
async def stop_camera_stream(camera_id: int) -> dict:
    return {"camera_id": camera_id, "status": "stop_requested"}
