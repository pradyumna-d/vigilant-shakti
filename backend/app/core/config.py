from functools import lru_cache

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    project_name: str = "Vigilant Shakti"
    mysql_host: str = "mysql"
    mysql_port: int = 3306
    mysql_database: str = "vigilant_shakti"
    mysql_user: str = "shakti"
    mysql_password: str = "shakti_password"

    backend_cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    ai_inference_url: AnyHttpUrl = "http://ai-inference:8100"
    ai_inference_api_token: str = "change-me-local-token"

    event_cooldown_seconds: int = 10
    person_confidence_threshold: float = 0.70
    pigeon_confidence_threshold: float = 0.50
    snapshot_max_width: int = 640
    snapshot_jpeg_quality: int = 72

    mediamtx_rtsp_url: str = "rtsp://shakti-webrtc:8654"
    mediamtx_webrtc_base_url: str = Field(default="http://localhost:8899", alias="MEDIAMTX_WEBRTC_BASE_URL")
    mediamtx_api_url: str = "http://shakti-webrtc:9998"

    @property
    def database_url(self) -> str:
        return (
            f"mysql+aiomysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
        )

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.backend_cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
