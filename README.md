# Vigilant Shakti

Production-style edge video analytics platform scaffold for local AI perception workflows.

## Services

- `frontend`: React + Vite dark operations UI on `http://localhost:5173`
- `backend`: FastAPI API/WebSocket service on `http://localhost:8000`
- `mysql`: MySQL 8.4 on host port `3307`
- `ai-inference`: YOLO/OpenCV worker API on `http://localhost:8100`
- `shakti-webrtc`: dedicated MediaMTX instance with non-conflicting ports:
  - RTSP publish/read: `8654`
  - HLS: `8898`
  - WebRTC: `8899`
  - WebRTC UDP mux: `8190/udp`
  - API: `9998`

## Run

```bash
docker compose up --build
```

The inference container downloads `yolov8n.pt` on first use and stores it in the `shakti-yolo-models` Docker volume.

## Camera Flow

1. Open Cameras.
2. Trigger ONVIF discovery manually.
3. Enter camera username, password, and final RTSP URL.
4. Start ingest.
5. `ai-inference` consumes RTSP over TCP, runs YOLO, overlays detections, publishes processed RTSP to `shakti-webrtc`, and emits events to the backend.
6. Live Monitoring displays the processed WebRTC stream only.

## Storage Policy

The backend stores analytics data only:

- cameras
- stream state
- detection events
- one compressed JPEG thumbnail BLOB per event

It does not store continuous video or archival recordings.
