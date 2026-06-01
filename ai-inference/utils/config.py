from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    backend_url: str = "http://host.docker.internal:8000"
    ai_inference_api_token: str = "change-me-local-token"
    yolo_model_path: str = "/app/models/yolov8n.pt"
    yolo_model_name: str = "yolov8n.pt"
    inference_device: str = "auto"
    rtsp_transport: str = "tcp"
    input_decoder_backend: str = "ffmpeg"
    mediamtx_rtsp_url: str = "rtsp://shakti-webrtc:8654"
    event_cooldown_seconds: int = 10
    person_confidence_threshold: float = 0.70
    phone_confidence_threshold: float = 0.50
    pigeon_confidence_threshold: float = 0.50
    frame_stride: int = 3
    output_fps: int = 15
    output_max_width: int = 1280
    yolo_fps: float = 3.0
    yolo_frame_interval: int = 5
    detection_ttl_seconds: float = 1.0
    event_queue_maxsize: int = 32


@lru_cache
def get_settings() -> Settings:
    return Settings()
