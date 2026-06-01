import asyncio
import logging
import time
from dataclasses import dataclass

from event_dispatch.dispatcher import EventDispatcher
from inference.confidence_filter import Detection
from inference.detection_logic import DetectionLogic
from inference.event_cooldown import EventCooldown
from inference.yolo_engine import YoloEngine
from stream_processing.latest_frame_reader import LatestFrameReader
from stream_processing.metrics import RateMeter
from stream_processing.overlay_renderer import OverlayRenderer
from stream_processing.publisher import RtspPublisher
from utils.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class WorkerStatus:
    camera_id: int
    status: str
    fps: float = 0.0
    latency_ms: float = 0.0
    reconnect_count: int = 0
    error: str | None = None
    camera_reported_fps: float = 0.0
    input_read_fps: float = 0.0
    output_publish_fps: float = 0.0
    yolo_fps: float = 0.0
    yolo_latency_ms: float = 0.0
    last_frame_age_ms: float = 0.0
    dropped_frames: int = 0
    event_queue_depth: int = 0
    event_dispatch_failures: int = 0
    publisher_restarts: int = 0
    last_publish_error: str | None = None
    publish_latency_ms: float = 0.0
    loop_latency_ms: float = 0.0
    snapshot_latency_ms: float = 0.0
    resize_latency_ms: float = 0.0
    render_latency_ms: float = 0.0
    output_width: int = 0
    output_height: int = 0
    decoder_backend: str = "ffmpeg"
    decoder_restarts: int = 0
    decoder_stderr_tail: str | None = None
    frame_buffer_leases: int = 0
    frame_buffer_drops: int = 0


class CameraWorker:
    def __init__(
        self,
        camera_id: int,
        rtsp_url: str,
        stream_path: str,
        processed_rtsp_url: str,
        detection_classes: list[str],
    ) -> None:
        settings = get_settings()
        self.camera_id = camera_id
        self.rtsp_url = rtsp_url
        self.stream_path = stream_path
        self.processed_rtsp_url = processed_rtsp_url
        self.detection_classes = set(detection_classes)
        self.status = WorkerStatus(camera_id=camera_id, status="starting")
        self._stop = asyncio.Event()
        self.engine = YoloEngine()
        self.logic = DetectionLogic()
        self.cooldown = EventCooldown(settings.event_cooldown_seconds)
        self.dispatcher = EventDispatcher()
        self.renderer = OverlayRenderer()
        self.output_fps = max(1, settings.output_fps)
        self.yolo_interval_seconds = 1 / max(0.1, settings.yolo_fps)
        self.detection_ttl_seconds = settings.detection_ttl_seconds
        self.event_queue: asyncio.Queue[tuple[object, Detection, float]] = asyncio.Queue(
            maxsize=settings.event_queue_maxsize
        )

    def set_detection_classes(self, detection_classes: list[str]) -> None:
        self.detection_classes = set(detection_classes)

    async def stop(self) -> None:
        self._stop.set()

    def _enqueue_event(self, frame, detection: Detection, latency_ms: float) -> None:
        if self.event_queue.full():
            try:
                self.event_queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
        try:
            self.event_queue.put_nowait((frame.copy(), detection, latency_ms))
        except asyncio.QueueFull:
            self.status.event_dispatch_failures += 1

    async def _dispatch_events(self) -> None:
        while not self._stop.is_set():
            try:
                frame, detection, latency_ms = await asyncio.wait_for(self.event_queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue
            try:
                await self.dispatcher.dispatch(self.camera_id, frame, detection, latency_ms)
            except Exception:
                logger.exception("event_dispatch_failed camera_id=%s", self.camera_id)
                self.status.event_dispatch_failures += 1
            finally:
                self.event_queue.task_done()
                self.status.event_queue_depth = self.event_queue.qsize()

    def _update_reader_status(self, reader: LatestFrameReader, output_meter: RateMeter, yolo_meter: RateMeter) -> None:
        self.status.camera_reported_fps = reader.camera_reported_fps
        self.status.input_read_fps = reader.input_read_fps
        self.status.output_publish_fps = output_meter.rate
        self.status.fps = self.status.output_publish_fps
        self.status.yolo_fps = yolo_meter.rate
        self.status.last_frame_age_ms = reader.last_frame_age_ms
        self.status.dropped_frames = reader.dropped_frames
        self.status.reconnect_count = reader.reconnect_count
        self.status.decoder_backend = reader.decoder_backend
        self.status.decoder_restarts = reader.decoder_restarts
        self.status.decoder_stderr_tail = reader.decoder_stderr_tail
        self.status.frame_buffer_leases = reader.frame_buffer_leases
        self.status.frame_buffer_drops = reader.frame_buffer_drops
        self.status.output_width = reader.output_width
        self.status.output_height = reader.output_height
        self.status.event_queue_depth = self.event_queue.qsize()
        if reader.error:
            self.status.error = reader.error

    async def run(self) -> None:
        reader = LatestFrameReader(self.rtsp_url)
        publisher: RtspPublisher | None = None
        output_meter = RateMeter()
        yolo_meter = RateMeter()
        dispatch_task = asyncio.create_task(self._dispatch_events())
        last_published_sequence = 0
        active_detections: list[Detection] = []
        detections_until = 0.0
        frame_interval = 1 / self.output_fps
        next_tick = time.monotonic()
        next_yolo_at = time.monotonic()
        reader.start()

        try:
            self.status.status = "running"
            while not self._stop.is_set():
                now = time.monotonic()
                if now < next_tick:
                    await asyncio.sleep(next_tick - now)
                    continue
                loop_start = time.monotonic()
                next_tick = max(next_tick + frame_interval, time.monotonic())

                snapshot_start = time.monotonic()
                frame_lease = reader.acquire_latest()
                self.status.snapshot_latency_ms = (time.monotonic() - snapshot_start) * 1000
                if frame_lease is None:
                    self._update_reader_status(reader, output_meter, yolo_meter)
                    await asyncio.sleep(0)
                    continue
                if frame_lease.sequence == last_published_sequence:
                    frame_lease.release()
                    self._update_reader_status(reader, output_meter, yolo_meter)
                    await asyncio.sleep(0)
                    continue

                try:
                    last_published_sequence = frame_lease.sequence
                    frame = frame_lease.frame
                    self.status.resize_latency_ms = 0.0
                    self.status.output_height, self.status.output_width = frame.shape[:2]
                    detections: list[Detection] = []

                    yolo_due_at = time.monotonic()
                    if yolo_due_at >= next_yolo_at:
                        next_yolo_at = yolo_due_at + self.yolo_interval_seconds
                        yolo_start = time.monotonic()
                        detections = self.logic.filter(self.camera_id, self.engine.detect(frame))
                        detections = [detection for detection in detections if detection.label in self.detection_classes]
                        self.status.yolo_latency_ms = (time.monotonic() - yolo_start) * 1000
                        self.status.latency_ms = self.status.yolo_latency_ms
                        yolo_meter.tick()
                        if detections:
                            active_detections = detections
                            detections_until = time.monotonic() + self.detection_ttl_seconds
                        elif time.monotonic() >= detections_until:
                            active_detections = []
                    elif time.monotonic() >= detections_until:
                        active_detections = []

                    render_start = time.monotonic()
                    rendered = self.renderer.render(frame, active_detections)
                    self.status.render_latency_ms = (time.monotonic() - render_start) * 1000
                    for detection in detections:
                        if self.cooldown.allow(self.camera_id, detection.label):
                            self._enqueue_event(rendered, detection, self.status.yolo_latency_ms)

                    if publisher is None:
                        height, width = rendered.shape[:2]
                        publisher = RtspPublisher(self.processed_rtsp_url, width, height, self.output_fps)

                    publish_start = time.monotonic()
                    ok, error = publisher.write(rendered)
                    self.status.publish_latency_ms = (time.monotonic() - publish_start) * 1000
                    if not ok:
                        self.status.publisher_restarts += 1
                        self.status.last_publish_error = error
                        publisher.close()
                        publisher = None
                    else:
                        output_meter.tick()
                finally:
                    frame_lease.release()

                self.status.error = None
                self.status.loop_latency_ms = (time.monotonic() - loop_start) * 1000
                self._update_reader_status(reader, output_meter, yolo_meter)
                await asyncio.sleep(0)
        except Exception as exc:
            logger.exception("camera_worker_error camera_id=%s", self.camera_id)
            self.status.status = "error"
            self.status.error = str(exc)
        finally:
            reader.stop()
            if publisher:
                publisher.close()
            dispatch_task.cancel()
            try:
                await dispatch_task
            except asyncio.CancelledError:
                pass

        self.status.status = "stopped"
