import { Activity, BarChart3, Bell, Camera, Gauge, LayoutDashboard, Radio, Search, Settings, Video } from "lucide-react";
import type { ReactNode } from "react";

export type PageKey = "dashboard" | "cameras" | "live" | "events" | "metrics";

const nav = [
  ["dashboard", LayoutDashboard, "Dashboard"],
  ["cameras", Camera, "Cameras"],
  ["live", Video, "Live Monitoring"],
  ["events", Radio, "Events"],
  ["metrics", BarChart3, "System Metrics"]
] as const;

export function Shell({
  page,
  setPage,
  title,
  children
}: {
  page: PageKey;
  setPage: (page: PageKey) => void;
  title: string;
  children: ReactNode;
}) {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <h1>Vigilant Shakti</h1>
          <div className="micro">Autonomous Monitoring</div>
        </div>
        <nav className="nav">
          {nav.map(([key, Icon, label]) => (
            <button key={key} className={page === key ? "active" : ""} onClick={() => setPage(key)}>
              <Icon size={20} />
              <span>{label}</span>
            </button>
          ))}
          <button>
            <Settings size={20} />
            <span>Settings</span>
          </button>
        </nav>
        <div className="user-tile">
          <div className="avatar">A</div>
          <div>
            <strong>Administrator</strong>
            <div className="micro">Primary Node</div>
          </div>
        </div>
      </aside>
      <main className="main">
        <header className="topbar">
          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
            <h2 style={{ margin: 0 }}>{title}</h2>
            <span className="chip">
              <Activity size={12} /> Node 01: Live
            </span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
            <div style={{ position: "relative", width: 260 }}>
              <Search size={16} style={{ position: "absolute", left: 10, top: 10, color: "#bacac5" }} />
              <input className="input" style={{ paddingLeft: 34 }} placeholder="Search logs..." />
            </div>
            <Gauge size={20} color="#bacac5" />
            <Bell size={20} color="#bacac5" />
          </div>
        </header>
        {children}
      </main>
    </div>
  );
}
