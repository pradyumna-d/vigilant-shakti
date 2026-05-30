from fastapi import APIRouter

from app.api import cameras, events, metrics, streams

api_router = APIRouter(prefix="/api")
api_router.include_router(cameras.router)
api_router.include_router(events.router)
api_router.include_router(metrics.router)
api_router.include_router(streams.router)
