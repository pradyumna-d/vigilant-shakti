import base64
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.event import DetectionEvent
from app.schemas.event import EventIngest, EventPage, EventRead
from app.services.event_service import create_detection_event
from app.websocket.manager import ws_manager

router = APIRouter(prefix="/events", tags=["events"])


def _utc_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _event_read(event: DetectionEvent) -> EventRead:
    return EventRead(
        id=event.id,
        camera_id=event.camera_id,
        event_type=event.event_type,
        confidence=event.confidence,
        timestamp=_utc_timestamp(event.timestamp),
        bbox_json=event.bbox_json,
        metadata_json=event.metadata_json,
        inference_metadata_json=event.inference_metadata_json,
        snapshot_url=f"/api/events/{event.id}/thumbnail",
        summary=event.summary,
    )


@router.get("", response_model=EventPage)
async def list_events(
    limit: int = 50,
    offset: int = 0,
    camera_id: int | None = None,
    event_type: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> EventPage:
    query = select(DetectionEvent)
    count_query = select(func.count(DetectionEvent.id))
    if camera_id:
        query = query.where(DetectionEvent.camera_id == camera_id)
        count_query = count_query.where(DetectionEvent.camera_id == camera_id)
    if event_type:
        query = query.where(DetectionEvent.event_type == event_type)
        count_query = count_query.where(DetectionEvent.event_type == event_type)
    total = await session.scalar(count_query)
    result = await session.execute(query.order_by(DetectionEvent.timestamp.desc()).offset(offset).limit(limit))
    return EventPage(total=total or 0, items=[_event_read(event) for event in result.scalars().all()])


@router.post("/ingest", response_model=EventRead | dict, status_code=201)
async def ingest_event(payload: EventIngest, session: AsyncSession = Depends(get_session)):
    event = await create_detection_event(session, payload)
    await session.commit()
    if event is None:
        return {"status": "suppressed", "reason": "cooldown"}
    await session.refresh(event)
    event_payload = _event_read(event)
    await ws_manager.broadcast("event.created", event_payload.model_dump(mode="json"))
    return event_payload


@router.get("/{event_id}/thumbnail")
async def get_event_thumbnail(event_id: int, session: AsyncSession = Depends(get_session)) -> Response:
    event = await session.get(DetectionEvent, event_id)
    if not event or not event.snapshot_blob:
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    return Response(event.snapshot_blob, media_type=event.snapshot_mime_type)


@router.get("/{event_id}/thumbnail/base64")
async def get_event_thumbnail_base64(event_id: int, session: AsyncSession = Depends(get_session)) -> dict:
    event = await session.get(DetectionEvent, event_id)
    if not event or not event.snapshot_blob:
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    return {"mime_type": event.snapshot_mime_type, "data": base64.b64encode(event.snapshot_blob).decode()}
