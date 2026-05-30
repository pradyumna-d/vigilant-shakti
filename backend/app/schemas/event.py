from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BoundingBox(BaseModel):
    x: float
    y: float
    width: float
    height: float


class EventIngest(BaseModel):
    camera_id: int
    event_type: str
    confidence: float
    timestamp: datetime | None = None
    bbox: BoundingBox
    snapshot_jpeg_base64: str | None = None
    metadata: dict[str, Any] | None = None
    inference_metadata: dict[str, Any] | None = None


class EventRead(BaseModel):
    id: int
    camera_id: int
    event_type: str
    confidence: float
    timestamp: datetime
    bbox_json: dict[str, Any]
    metadata_json: dict[str, Any] | None
    inference_metadata_json: dict[str, Any] | None
    snapshot_url: str
    summary: str | None = None

    class Config:
        from_attributes = True


class EventPage(BaseModel):
    total: int
    items: list[EventRead]


class StreamStartRequest(BaseModel):
    camera_id: int = Field(gt=0)
