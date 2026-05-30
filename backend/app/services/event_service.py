from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.event import DetectionEvent
from app.schemas.event import EventIngest
from app.services.snapshot_service import normalize_snapshot


EVENT_LABELS = {
    "person": "Person",
    "phone": "Phone",
    "pigeon": "Pigeon",
}


def _event_summary(event_type: str, confidence: float) -> str:
    label = EVENT_LABELS.get(event_type, event_type.replace("_", " ").title())
    return f"{label} spotted with {round(confidence * 100)}% confidence"


async def is_in_cooldown(session: AsyncSession, payload: EventIngest) -> bool:
    settings = get_settings()
    cutoff = datetime.now(UTC) - timedelta(seconds=settings.event_cooldown_seconds)
    query = (
        select(DetectionEvent.id)
        .where(DetectionEvent.camera_id == payload.camera_id)
        .where(DetectionEvent.event_type == payload.event_type)
        .where(DetectionEvent.timestamp >= cutoff)
        .limit(1)
    )
    return (await session.execute(query)).scalar_one_or_none() is not None


async def create_detection_event(session: AsyncSession, payload: EventIngest) -> DetectionEvent | None:
    if await is_in_cooldown(session, payload):
        return None

    snapshot_blob, snapshot_hash = normalize_snapshot(payload.snapshot_jpeg_base64)
    event = DetectionEvent(
        camera_id=payload.camera_id,
        event_type=payload.event_type,
        confidence=payload.confidence,
        timestamp=payload.timestamp or datetime.now(UTC),
        bbox_json=payload.bbox.model_dump(),
        metadata_json=payload.metadata,
        inference_metadata_json=payload.inference_metadata,
        snapshot_blob=snapshot_blob,
        snapshot_sha256=snapshot_hash,
        summary=_event_summary(payload.event_type, payload.confidence),
    )
    session.add(event)
    await session.flush()
    return event


async def event_counts(session: AsyncSession) -> dict[str, int]:
    total = await session.scalar(select(func.count(DetectionEvent.id)))
    cutoff = datetime.now(UTC) - timedelta(hours=1)
    recent = await session.scalar(select(func.count(DetectionEvent.id)).where(DetectionEvent.timestamp >= cutoff))
    return {"total": total or 0, "recent": recent or 0}
