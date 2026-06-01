import os

import cv2

from utils.config import get_settings


class RtspDecoder:
    def __init__(self, rtsp_url: str) -> None:
        settings = get_settings()
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = f"rtsp_transport;{settings.rtsp_transport}"
        self.capture = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)

    def read(self):
        return self.capture.read()

    def release(self) -> None:
        self.capture.release()

    def fps(self) -> float:
        value = self.capture.get(cv2.CAP_PROP_FPS)
        return float(value) if value else 0.0
