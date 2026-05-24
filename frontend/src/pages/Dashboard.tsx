import { Camera, Cpu, Radio, ShieldAlert, Signal, Timer } from "lucide-react";
import type { ReactNode } from "react";
import type { Camera as CameraType, DashboardMetrics, DetectionEvent } from "../lib/api";
import { thumbnailUrl } from "../lib/api";

function Stat({ label, value, icon }: { label: string; value: string | number; icon: ReactNode }) {
  return (
    <div className="card stat">
      <div style={{ display: "flex", justifyContent: "space-between", color: "#bacac5" }}>
        <span className="micro">{label}</span>
        {icon}
      </div>
      <strong>{value}</strong>
    </div>
  );
}

export function Dashboard({ metrics, cameras, events }: { metrics?: DashboardMetrics; cameras: CameraType[]; events: DetectionEvent[] }) {
  return (
    <div className="page">
      <section className="grid stats">
        <Stat label="Cameras" value={metrics?.cameras_total ?? 0} icon={<Camera size={18} />} />
        <Stat label="Active Streams" value={metrics?.active_streams ?? 0} icon={<Signal size={18} />} />
        <Stat label="Events / Hour" value={metrics?.recent_events ?? 0} icon={<Radio size={18} />} />
        <Stat label="Active Alerts" value={events.length} icon={<ShieldAlert size={18} color="#ffb4ab" />} />
        <div className="card stat">
          <div style={{ display: "flex", justifyContent: "space-between", color: "#bacac5" }}>
            <span className="micro">CPU Load</span>
            <Cpu size={18} />
          </div>
          <strong>{Math.round(metrics?.cpu_percent ?? 0)}%</strong>
          <div className="metric-line"><span style={{ width: `${metrics?.cpu_percent ?? 0}%` }} /></div>
        </div>
        <Stat label="Latency" value="-- ms" icon={<Timer size={18} />} />
      </section>

      <section className="grid" style={{ gridTemplateColumns: "2fr 1fr" }}>
        <div className="panel">
          <div className="panel-header">
            <span className="micro">Live Grid View</span>
            <span className="chip">Processed Streams Only</span>
          </div>
          <div className="grid" style={{ gridTemplateColumns: "repeat(4, minmax(0, 1fr))", padding: 16 }}>
            {cameras.slice(0, 8).map((camera) => (
              <div className="stream-tile" key={camera.id} style={{ aspectRatio: "16 / 9" }}>
                <div className="stream-hud">
                  <span className={camera.state === "online" ? "chip" : "chip error"}>{camera.state}</span>
                  <strong style={{ fontFamily: "JetBrains Mono", fontSize: 12 }}>{camera.name}</strong>
                </div>
              </div>
            ))}
            {cameras.length === 0 && <div style={{ color: "#bacac5" }}>No cameras registered.</div>}
          </div>
        </div>
        <div className="panel">
          <div className="panel-header"><span className="micro">Recent Events</span></div>
          <div style={{ padding: 16, display: "grid", gap: 12 }}>
            {events.slice(0, 5).map((event) => (
              <div key={event.id} style={{ display: "grid", gridTemplateColumns: "72px 1fr", gap: 12 }}>
                <img src={thumbnailUrl(event)} style={{ width: 72, height: 48, objectFit: "cover", background: "#0c0e11" }} />
                <div>
                  <strong>{event.event_type.toUpperCase()}</strong>
                  <div className="micro">{Math.round(event.confidence * 100)}% | CAM {event.camera_id}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
