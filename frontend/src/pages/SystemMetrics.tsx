import type { DashboardMetrics } from "../lib/api";

export function SystemMetrics({ metrics }: { metrics?: DashboardMetrics }) {
  const health = metrics?.service_health ?? {};
  const memory = metrics?.service_memory ?? {};
  const vram =
    metrics?.vram_used_mb != null && metrics?.vram_total_mb != null
      ? `${(metrics.vram_used_mb / 1024).toFixed(1)} / ${(metrics.vram_total_mb / 1024).toFixed(1)} GB`
      : "--";
  return (
    <div className="page">
      <section className="grid stats">
        <div className="card stat"><span className="micro">CPU</span><strong>{Math.round(metrics?.cpu_percent ?? 0)}%</strong></div>
        <div className="card stat"><span className="micro">RAM</span><strong>{Math.round(metrics?.ram_percent ?? 0)}%</strong></div>
        <div className="card stat"><span className="micro">GPU</span><strong>{metrics?.gpu_percent != null ? `${Math.round(metrics.gpu_percent)}%` : "--"}</strong></div>
        <div className="card stat"><span className="micro">VRAM</span><strong style={{ fontSize: 24 }}>{vram}</strong></div>
        <div className="card stat"><span className="micro">Throughput</span><strong>{metrics?.recent_events ?? 0}/h</strong></div>
        <div className="card stat"><span className="micro">Streams</span><strong>{metrics?.active_streams ?? 0}</strong></div>
      </section>
      <section className="panel">
        <div className="panel-header"><span className="micro">Service Health</span></div>
        <div style={{ padding: 16, display: "grid", gap: 10 }}>
          {Object.entries(health).map(([service, state]) => (
            <div key={service} className="service-row">
              <div>
                <strong>{service}</strong>
                <div className="micro">
                  RAM {memory[service]?.ram_used_mb ?? "--"} MB
                  {memory[service]?.ram_percent != null ? ` | ${memory[service]?.ram_percent}% of limit` : ""}
                </div>
              </div>
              <span className={state === "online" ? "chip" : "chip error"}>{state}</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
