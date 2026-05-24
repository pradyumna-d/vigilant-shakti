export const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
export const WS_BASE = import.meta.env.VITE_WS_BASE_URL ?? "ws://localhost:8000";
export const WEBRTC_BASE = import.meta.env.VITE_WEBRTC_BASE_URL ?? "http://localhost:8899";

export type Camera = {
  id: number;
  name: string;
  ip_address: string;
  manufacturer?: string | null;
  model?: string | null;
  onvif_endpoint: string;
  rtsp_url?: string | null;
  state: string;
  stream_path?: string | null;
  credentials_configured: boolean;
  detection_classes: string[];
  metadata_json?: Record<string, unknown> | null;
  last_seen_at?: string | null;
};

export type DetectionEvent = {
  id: number;
  camera_id: number;
  event_type: string;
  confidence: number;
  timestamp: string;
  bbox_json: { x: number; y: number; width: number; height: number };
  snapshot_url: string;
  summary?: string | null;
};

export type DashboardMetrics = {
  cameras_total: number;
  cameras_online: number;
  active_streams: number;
  events_total: number;
  recent_events: number;
  cpu_percent: number;
  ram_percent: number;
  gpu_percent?: number | null;
  vram_percent?: number | null;
  vram_used_mb?: number | null;
  vram_total_mb?: number | null;
  service_memory: Record<string, { ram_used_mb: number; ram_limit_mb?: number | null; ram_percent?: number | null }>;
  service_health: Record<string, string>;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<T>;
}

export const api = {
  cameras: () => request<Camera[]>("/api/cameras"),
  discover: () => request("/api/cameras/discover", { method: "POST" }),
  setCredentials: (cameraId: number, payload: { username: string; password: string }) =>
    request<Camera>(`/api/cameras/${cameraId}/credentials`, { method: "POST", body: JSON.stringify(payload) }),
  setDetectionClasses: (cameraId: number, detection_classes: string[]) =>
    request<Camera>(`/api/cameras/${cameraId}/detection-classes`, { method: "POST", body: JSON.stringify({ detection_classes }) }),
  startStream: (cameraId: number) => request(`/api/cameras/${cameraId}/streams/start`, { method: "POST" }),
  events: () => request<{ total: number; items: DetectionEvent[] }>("/api/events?limit=24"),
  metrics: () => request<DashboardMetrics>("/api/metrics/dashboard"),
  streams: () => request("/api/streams")
};

export function thumbnailUrl(event: DetectionEvent) {
  return `${API_BASE}${event.snapshot_url}`;
}
