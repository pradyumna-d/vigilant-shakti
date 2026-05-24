import { Radar, Save, SlidersHorizontal } from "lucide-react";
import { useState } from "react";
import type { Camera } from "../lib/api";
import { api } from "../lib/api";

export function Cameras({ cameras, refresh }: { cameras: Camera[]; refresh: () => void }) {
  const [editing, setEditing] = useState<number | null>(null);
  const [form, setForm] = useState({ username: "", password: "" });
  const [classEdits, setClassEdits] = useState<Record<number, string[]>>({});
  const [busy, setBusy] = useState(false);
  const classOptions = ["person", "phone", "pigeon"];

  async function discover() {
    setBusy(true);
    try {
      await api.discover();
      refresh();
    } finally {
      setBusy(false);
    }
  }

  async function saveCredentials(cameraId: number) {
    await api.setCredentials(cameraId, form);
    setEditing(null);
    setForm({ username: "", password: "" });
    refresh();
  }

  async function saveClasses(camera: Camera) {
    await api.setDetectionClasses(camera.id, classEdits[camera.id] ?? camera.detection_classes);
    refresh();
  }

  function toggleClass(camera: Camera, detectionClass: string) {
    const current = classEdits[camera.id] ?? camera.detection_classes;
    const next = current.includes(detectionClass)
      ? current.filter((item) => item !== detectionClass)
      : [...current, detectionClass];
    setClassEdits({ ...classEdits, [camera.id]: next.length ? next : current });
  }

  return (
    <div className="page">
      <section className="panel" style={{ borderLeft: "4px solid #57f1db" }}>
        <div style={{ padding: 16, display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16 }}>
          <div>
            <h3 style={{ margin: 0 }}>Network Discovery</h3>
            <div className="micro">Manual-trigger ONVIF WS-Discovery multicast scan</div>
          </div>
          <button className="btn primary" onClick={discover} disabled={busy}>
            <Radar size={18} /> {busy ? "SCANNING" : "SCAN NETWORK"}
          </button>
        </div>
      </section>

      <section className="panel">
        <div className="panel-header">
          <span className="micro">Active Asset Inventory</span>
          <span className="chip">{cameras.length} Devices</span>
        </div>
        <table className="table">
          <thead>
            <tr>
              <th>Device Identity</th>
              <th>Endpoint IP</th>
              <th>Manufacturer</th>
              <th>Protocol</th>
              <th>State</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {cameras.map((camera) => (
              <tr key={camera.id}>
                <td>
                  <strong style={{ color: "#57f1db" }}>{camera.name}</strong>
                  <div className="micro">UID: CAM-{camera.id.toString().padStart(4, "0")}</div>
                </td>
                <td style={{ fontFamily: "JetBrains Mono" }}>{camera.ip_address}</td>
                <td>{camera.manufacturer ?? "Unknown"}</td>
                <td><span className="chip">ONVIF / RTSP</span></td>
                <td><span className={camera.state === "online" ? "chip" : "chip error"}>{camera.state}</span></td>
                <td>
                  {!camera.credentials_configured && (
                    <div style={{ display: "flex", gap: 8 }}>
                      <button className="btn" onClick={() => setEditing(camera.id)}><Save size={16} /> Auth</button>
                    </div>
                  )}
                  {camera.credentials_configured && (
                    <div className="class-picker">
                      {classOptions.map((detectionClass) => {
                        const selected = (classEdits[camera.id] ?? camera.detection_classes).includes(detectionClass);
                        return (
                          <button
                            className={selected ? "btn primary" : "btn"}
                            key={detectionClass}
                            onClick={() => toggleClass(camera, detectionClass)}
                          >
                            {detectionClass}
                          </button>
                        );
                      })}
                      <button className="btn" onClick={() => saveClasses(camera)}><SlidersHorizontal size={16} /> Apply</button>
                    </div>
                  )}
                  {!camera.credentials_configured && editing === camera.id && (
                    <div style={{ marginTop: 12, display: "grid", gap: 8, minWidth: 360 }}>
                      <input className="input" placeholder="Username" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} />
                      <input className="input" placeholder="Password" type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
                      <button className="btn primary" onClick={() => saveCredentials(camera.id)}>Authenticate & Start</button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
