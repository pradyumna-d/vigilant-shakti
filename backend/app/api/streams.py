from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.camera import CameraStream

router = APIRouter(prefix="/streams", tags=["streams"])


@router.get("")
async def list_streams(session: AsyncSession = Depends(get_session)) -> list[dict]:
    result = await session.execute(select(CameraStream).order_by(CameraStream.camera_id))
    return [
        {
            "id": stream.id,
            "camera_id": stream.camera_id,
            "status": stream.status,
            "fps": stream.fps,
            "latency_ms": stream.latency_ms,
            "processed_rtsp_url": stream.processed_rtsp_url,
            "webrtc_url": stream.webrtc_url,
            "reconnect_count": stream.reconnect_count,
        }
        for stream in result.scalars().all()
    ]
