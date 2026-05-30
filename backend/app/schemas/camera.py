from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CameraBase(BaseModel):
    name: str = "Unnamed Camera"
    ip_address: str
    manufacturer: str | None = None
    model: str | None = None
    onvif_endpoint: str
    rtsp_url: str | None = None


class CameraCreate(CameraBase):
    pass


class CameraCredentials(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class CameraDetectionClasses(BaseModel):
    detection_classes: list[str] = Field(default_factory=lambda: ["person", "phone", "pigeon"], min_length=1)


class CameraRead(CameraBase):
    id: int
    state: str
    stream_path: str | None
    credentials_configured: bool
    last_seen_at: datetime | None
    created_at: datetime
    updated_at: datetime
    metadata_json: dict[str, Any] | None = None
    detection_classes: list[str] = Field(default_factory=list)

    class Config:
        from_attributes = True


class DiscoveryResult(BaseModel):
    discovered: int
    updated: int
    cameras: list[CameraRead]
