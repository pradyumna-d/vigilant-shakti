import logging
import subprocess
import threading

import numpy as np

logger = logging.getLogger(__name__)


class RtspPublisher:
    def __init__(self, output_url: str, width: int, height: int, fps: float) -> None:
        self.output_url = output_url
        self.width = width
        self.height = height
        self.fps = fps if fps > 1 else 15
        self._stderr_lines: list[str] = []
        self._stderr_lock = threading.Lock()
        keyframe_interval = max(1, round(self.fps))
        self.process = subprocess.Popen(
            [
                "ffmpeg",
                "-loglevel",
                "info",
                "-f",
                "rawvideo",
                "-pix_fmt",
                "bgr24",
                "-s",
                f"{width}x{height}",
                "-r",
                str(self.fps),
                "-i",
                "-",
                "-an",
                "-c:v",
                "h264_nvenc",
                "-preset",
                "p1",
                "-tune",
                "ull",
                "-pix_fmt",
                "yuv420p",
                "-rc",
                "cbr",
                "-b:v",
                "1500k",
                "-maxrate",
                "1500k",
                "-bufsize",
                "500k",
                "-bf",
                "0",
                "-forced-idr",
                "1",
                "-g",
                str(keyframe_interval),
                "-keyint_min",
                str(keyframe_interval),
                "-sc_threshold",
                "0",
                "-flush_packets",
                "1",
                "-f",
                "rtsp",
                "-rtsp_transport",
                "tcp",
                output_url,
            ],
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self._stderr_thread = threading.Thread(target=self._drain_stderr, name="rtsp-publisher-stderr", daemon=True)
        self._stderr_thread.start()
        logger.info("rtsp_publisher_started output=%s", output_url)

    def _drain_stderr(self) -> None:
        if not self.process.stderr:
            return
        for line in self.process.stderr:
            clean_line = line.decode(errors="ignore").strip()
            if not clean_line:
                continue
            with self._stderr_lock:
                self._stderr_lines.append(clean_line)
                self._stderr_lines = self._stderr_lines[-20:]
            if "error" in clean_line.lower() or "failed" in clean_line.lower():
                logger.warning("rtsp_publisher_ffmpeg output=%s line=%s", self.output_url, clean_line)

    def recent_stderr(self) -> str | None:
        with self._stderr_lock:
            if not self._stderr_lines:
                return None
            return "\n".join(self._stderr_lines[-5:])

    def write(self, frame) -> tuple[bool, str | None]:
        if self.process.poll() is not None:
            return False, self.recent_stderr() or "ffmpeg process exited"
        if not self.process.stdin:
            return False, "ffmpeg stdin unavailable"
        try:
            if not frame.flags["C_CONTIGUOUS"]:
                frame = np.ascontiguousarray(frame)
            self.process.stdin.write(memoryview(frame).cast("B"))
            return True, None
        except (BrokenPipeError, OSError) as exc:
            return False, str(exc)

    def close(self) -> None:
        try:
            if self.process.stdin:
                self.process.stdin.close()
        except OSError:
            pass
        if self.process.poll() is None:
            self.process.terminate()
        try:
            self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.process.kill()
        stderr = self.recent_stderr()
        if stderr:
            logger.info("rtsp_publisher_stderr_tail output=%s error=%s", self.output_url, stderr[-1000:])
