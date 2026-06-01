import json
import logging
import subprocess
import threading
import time
from dataclasses import dataclass
from fractions import Fraction

import numpy as np

from stream_processing.metrics import RateMeter
from utils.config import get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FrameLease:
    sequence: int
    frame: np.ndarray
    captured_at: float
    reader: "LatestFrameReader"
    buffer_index: int

    def release(self) -> None:
        self.reader.release(self.buffer_index)


class LatestFrameReader:
    def __init__(self, rtsp_url: str) -> None:
        settings = get_settings()
        self.rtsp_url = rtsp_url
        self.rtsp_transport = settings.rtsp_transport
        self.preferred_backend = settings.input_decoder_backend.lower()
        self._active_backend = self.preferred_backend if self.preferred_backend in {"ffmpeg", "opencv"} else "ffmpeg"
        self.output_fps = max(1, settings.output_fps)
        self.output_max_width = max(320, settings.output_max_width)
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._process: subprocess.Popen | None = None
        self._stderr_thread: threading.Thread | None = None
        self._stderr_lines: list[str] = []
        self._buffers: list[np.ndarray] = []
        self._leased: list[bool] = []
        self._scratch: np.ndarray | None = None
        self._frame_size = 0
        self._output_width = 0
        self._output_height = 0
        self._latest_index: int | None = None
        self._latest_sequence = 0
        self._latest_captured_at = 0.0
        self._consumed_sequence = 0
        self._dropped_frames = 0
        self._frame_buffer_drops = 0
        self._frame_buffer_leases = 0
        self._camera_reported_fps = 0.0
        self._error: str | None = None
        self._decoder_restarts = 0
        self._ffmpeg_failures = 0
        self._read_meter = RateMeter()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, name="latest-frame-reader", daemon=True)
        self._thread.start()

    def _probe_source(self) -> tuple[int, int, float]:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-rtsp_transport",
                self.rtsp_transport,
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height,avg_frame_rate,r_frame_rate",
                "-of",
                "json",
                self.rtsp_url,
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
        streams = json.loads(result.stdout).get("streams") or []
        if not streams:
            raise RuntimeError("ffprobe found no video stream")
        stream = streams[0]
        width = int(stream["width"])
        height = int(stream["height"])
        fps = self._parse_fps(stream.get("avg_frame_rate") or stream.get("r_frame_rate"))
        return width, height, fps

    @staticmethod
    def _parse_fps(value: str | None) -> float:
        if not value or value == "0/0":
            return 0.0
        try:
            return float(Fraction(value))
        except Exception:
            return 0.0

    def _compute_output_dimensions(self, source_width: int, source_height: int) -> tuple[int, int]:
        if source_width <= self.output_max_width:
            width = source_width
            height = source_height
        else:
            width = self.output_max_width
            height = round(source_height * (width / source_width))
        width = max(2, width - (width % 2))
        height = max(2, height - (height % 2))
        return width, height

    def _configure_buffers(self, width: int, height: int) -> None:
        frame_size = width * height * 3
        with self._lock:
            if self._output_width == width and self._output_height == height and self._buffers:
                return
            self._output_width = width
            self._output_height = height
            self._frame_size = frame_size
            self._buffers = [np.empty((height, width, 3), dtype=np.uint8) for _ in range(3)]
            self._leased = [False for _ in self._buffers]
            self._scratch = np.empty((height, width, 3), dtype=np.uint8)
            self._latest_index = None
            self._latest_sequence = 0
            self._consumed_sequence = 0

    def _start_ffmpeg(self, width: int, height: int) -> subprocess.Popen:
        command = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "warning",
            "-rtsp_transport",
            self.rtsp_transport,
            "-flags",
            "low_delay",
            "-probesize",
            "1000000",
            "-analyzeduration",
            "1000000",
            "-i",
            self.rtsp_url,
            "-an",
            "-vf",
            f"fps={self.output_fps},scale={width}:{height}",
            "-pix_fmt",
            "bgr24",
            "-f",
            "rawvideo",
            "pipe:1",
        ]
        return subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def _drain_stderr(self, process: subprocess.Popen) -> None:
        if not process.stderr:
            return
        for line in process.stderr:
            clean_line = line.decode(errors="ignore").strip()
            if not clean_line:
                continue
            with self._lock:
                self._stderr_lines.append(clean_line)
                self._stderr_lines = self._stderr_lines[-20:]
            if "error" in clean_line.lower() or "failed" in clean_line.lower():
                logger.warning("ffmpeg_decoder_stderr line=%s", clean_line)

    def _run(self) -> None:
        while not self._stop.is_set():
            if self._active_backend == "opencv":
                self._run_opencv_once()
                if not self._stop.is_set():
                    time.sleep(0.5)
                continue

            try:
                source_width, source_height, source_fps = self._probe_source()
                output_width, output_height = self._compute_output_dimensions(source_width, source_height)
                self._configure_buffers(output_width, output_height)
                with self._lock:
                    self._camera_reported_fps = source_fps
                    self._error = None

                self._process = self._start_ffmpeg(output_width, output_height)
                self._stderr_thread = threading.Thread(
                    target=self._drain_stderr,
                    args=(self._process,),
                    name="ffmpeg-decoder-stderr",
                    daemon=True,
                )
                self._stderr_thread.start()
                self._read_loop()
            except Exception as exc:
                if self._stop.is_set():
                    break
                logger.exception("ffmpeg_decoder_failed")
                with self._lock:
                    self._error = str(exc)
                    self._decoder_restarts += 1
                    self._ffmpeg_failures += 1
            finally:
                self._close_process()

            if not self._stop.is_set():
                time.sleep(0.5)

    def _run_opencv_once(self) -> None:
        capture = None
        try:
            import os

            import cv2

            os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = f"rtsp_transport;{self.rtsp_transport}"
            capture = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
            if not capture.isOpened():
                raise RuntimeError("opencv decoder could not open camera")
            source_width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
            source_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
            source_fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
            if source_width <= 0 or source_height <= 0:
                raise RuntimeError("opencv decoder could not determine frame dimensions")
            output_width, output_height = self._compute_output_dimensions(source_width, source_height)
            self._configure_buffers(output_width, output_height)
            with self._lock:
                self._camera_reported_fps = source_fps
                self._error = None

            frame_interval = 1 / self.output_fps
            next_publish = time.monotonic()
            while not self._stop.is_set():
                ok, frame = capture.read()
                if not ok:
                    raise RuntimeError("opencv decoder read failed")
                now = time.monotonic()
                if now < next_publish:
                    with self._lock:
                        self._dropped_frames += 1
                    continue
                next_publish = max(next_publish + frame_interval, now)
                if frame.shape[1] != output_width or frame.shape[0] != output_height:
                    frame = cv2.resize(frame, (output_width, output_height), interpolation=cv2.INTER_AREA)
                buffer_index, target = self._acquire_write_buffer()
                if buffer_index is None:
                    with self._lock:
                        self._frame_buffer_drops += 1
                        self._dropped_frames += 1
                    continue
                np.copyto(target, frame)
                captured_at = time.monotonic()
                with self._lock:
                    if self._latest_sequence > self._consumed_sequence:
                        self._dropped_frames += 1
                    self._latest_sequence += 1
                    self._latest_index = buffer_index
                    self._latest_captured_at = captured_at
                    self._error = None
                self._read_meter.tick()
        except Exception as exc:
            if not self._stop.is_set():
                logger.exception("opencv_decoder_failed")
                with self._lock:
                    self._error = str(exc)
                    self._decoder_restarts += 1
        finally:
            try:
                capture.release()
            except Exception:
                pass

    def _read_loop(self) -> None:
        if not self._process or not self._process.stdout:
            raise RuntimeError("ffmpeg stdout unavailable")
        while not self._stop.is_set():
            buffer_index, target = self._acquire_write_buffer()
            view = memoryview(target).cast("B")
            self._read_exact_frame(view)

            if buffer_index is None:
                with self._lock:
                    self._frame_buffer_drops += 1
                    self._dropped_frames += 1
                continue

            now = time.monotonic()
            with self._lock:
                if self._latest_sequence > self._consumed_sequence:
                    self._dropped_frames += 1
                self._latest_sequence += 1
                self._latest_index = buffer_index
                self._latest_captured_at = now
                self._error = None
                self._ffmpeg_failures = 0
            self._read_meter.tick()

    def _read_exact_frame(self, target: memoryview) -> None:
        if not self._process or not self._process.stdout:
            raise RuntimeError("ffmpeg stdout unavailable")
        offset = 0
        while offset < self._frame_size and not self._stop.is_set():
            bytes_read = self._process.stdout.readinto(target[offset : self._frame_size])
            if not bytes_read:
                raise RuntimeError("ffmpeg decoder ended")
            offset += bytes_read
        if offset != self._frame_size:
            raise RuntimeError("ffmpeg decoder stopped")

    def _acquire_write_buffer(self) -> tuple[int | None, np.ndarray]:
        with self._lock:
            for index, buffer in enumerate(self._buffers):
                if not self._leased[index] and index != self._latest_index:
                    return index, buffer
            if self._scratch is None:
                raise RuntimeError("frame scratch buffer unavailable")
            return None, self._scratch

    def acquire_latest(self) -> FrameLease | None:
        with self._lock:
            if self._latest_index is None:
                return None
            self._leased[self._latest_index] = True
            self._consumed_sequence = self._latest_sequence
            self._frame_buffer_leases += 1
            return FrameLease(
                sequence=self._latest_sequence,
                frame=self._buffers[self._latest_index],
                captured_at=self._latest_captured_at,
                reader=self,
                buffer_index=self._latest_index,
            )

    def release(self, buffer_index: int) -> None:
        with self._lock:
            if 0 <= buffer_index < len(self._leased):
                self._leased[buffer_index] = False

    def stop(self) -> None:
        self._stop.set()
        self._close_process()
        if self._thread:
            self._thread.join(timeout=2)

    def _close_process(self) -> None:
        process = self._process
        self._process = None
        if not process:
            return
        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()

    @property
    def decoder_backend(self) -> str:
        with self._lock:
            return self._active_backend

    @property
    def camera_reported_fps(self) -> float:
        with self._lock:
            return self._camera_reported_fps

    @property
    def input_read_fps(self) -> float:
        return self._read_meter.rate

    @property
    def dropped_frames(self) -> int:
        with self._lock:
            return self._dropped_frames

    @property
    def last_frame_age_ms(self) -> float:
        with self._lock:
            if not self._latest_captured_at:
                return 0.0
            return (time.monotonic() - self._latest_captured_at) * 1000

    @property
    def error(self) -> str | None:
        with self._lock:
            return self._error

    @property
    def reconnect_count(self) -> int:
        return self.decoder_restarts

    @property
    def decoder_restarts(self) -> int:
        with self._lock:
            return self._decoder_restarts

    @property
    def decoder_stderr_tail(self) -> str | None:
        with self._lock:
            if not self._stderr_lines:
                return None
            return "\n".join(self._stderr_lines[-5:])

    @property
    def frame_buffer_leases(self) -> int:
        with self._lock:
            return self._frame_buffer_leases

    @property
    def frame_buffer_drops(self) -> int:
        with self._lock:
            return self._frame_buffer_drops

    @property
    def output_width(self) -> int:
        with self._lock:
            return self._output_width

    @property
    def output_height(self) -> int:
        with self._lock:
            return self._output_height
