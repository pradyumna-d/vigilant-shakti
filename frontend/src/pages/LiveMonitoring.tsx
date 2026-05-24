import type { Camera } from "../lib/api";
import { WEBRTC_BASE } from "../lib/api";

export function LiveMonitoring({ cameras }: { cameras: Camera[] }) {
  const active = cameras.filter((camera) => camera.stream_path).slice(0, 4);
  return (
    <div className="page" style={{ overflow: "hidden" }}>
      <section className="stream-grid">
        {active.map((camera) => (
          <div className="stream-tile" key={camera.id}>
            <iframe title={camera.name} src={`${WEBRTC_BASE}/${camera.stream_path}`} allow="autoplay; fullscreen" />
            <div className="stream-hud">
              <div>
                <span className="chip">STREAM: {camera.state.toUpperCase()}</span>
              </div>
              <div>
                <strong style={{ fontFamily: "JetBrains Mono" }}>{camera.name}</strong>
                <div className="micro">Processed WebRTC Output | CAM {camera.id}</div>
              </div>
            </div>
          </div>
        ))}
        {active.length === 0 && <div className="panel" style={{ padding: 24 }}>No processed streams are active.</div>}
      </section>
    </div>
  );
}
