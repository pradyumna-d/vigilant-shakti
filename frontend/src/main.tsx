import { useCallback, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { Shell, type PageKey } from "./components/Shell";
import { api, type Camera, type DashboardMetrics, type DetectionEvent } from "./lib/api";
import { useMetricsStream } from "./lib/useMetricsStream";
import { useRealtime } from "./lib/useRealtime";
import { Cameras } from "./pages/Cameras";
import { Dashboard } from "./pages/Dashboard";
import { Events } from "./pages/Events";
import { LiveMonitoring } from "./pages/LiveMonitoring";
import { SystemMetrics } from "./pages/SystemMetrics";
import "./styles/global.css";

function App() {
  const [page, setPage] = useState<PageKey>("dashboard");
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [events, setEvents] = useState<DetectionEvent[]>([]);
  const [metrics, setMetrics] = useState<DashboardMetrics>();

  const refreshCameras = useCallback(async () => {
    const cameraData = await api.cameras();
    setCameras(cameraData);
  }, []);

  const refreshEvents = useCallback(async () => {
    const eventData = await api.events();
    setEvents(eventData.items);
  }, []);

  const refreshDashboard = useCallback(async () => {
    const [cameraData, eventData, metricData] = await Promise.all([api.cameras(), api.events(), api.metrics()]);
    setCameras(cameraData);
    setEvents(eventData.items);
    setMetrics(metricData);
  }, []);

  const loadPage = useCallback(async () => {
    if (page === "dashboard") await refreshDashboard();
    if (page === "cameras" || page === "live") await refreshCameras();
    if (page === "events") await refreshEvents();
    if (page === "metrics") {
      const metricData = await api.metrics();
      setMetrics(metricData);
    }
  }, [page, refreshCameras, refreshDashboard, refreshEvents]);

  useEffect(() => {
    loadPage().catch(console.error);
  }, [loadPage]);

  useMetricsStream(setMetrics);

  useRealtime((message) => {
    if (message.topic === "event.created") {
      const event = message.payload as DetectionEvent;
      setEvents((current) => [event, ...current.filter((item) => item.id !== event.id)].slice(0, 24));
      setMetrics((current) => current ? {
        ...current,
        events_total: current.events_total + 1,
        recent_events: current.recent_events + 1
      } : current);
    }

    if (message.topic === "camera.updated") {
      const camera = message.payload as Camera;
      setCameras((current) => {
        const exists = current.some((item) => item.id === camera.id);
        return exists ? current.map((item) => item.id === camera.id ? camera : item) : [camera, ...current];
      });
    }

    if (message.topic === "camera.discovery.completed") {
      const payload = message.payload as { cameras?: Camera[] };
      if (payload.cameras) {
        setCameras((current) => {
          const byId = new Map(current.map((camera) => [camera.id, camera]));
          for (const camera of payload.cameras ?? []) byId.set(camera.id, camera);
          return [...byId.values()].sort((a, b) => b.id - a.id);
        });
      }
    }

    if (message.topic === "stream.started") {
      refreshCameras().catch(console.error);
    }
  });

  const title = {
    dashboard: "Overview",
    cameras: "Cameras",
    live: "Live Monitoring",
    events: "Events Timeline",
    metrics: "System Metrics"
  }[page];

  return (
    <Shell page={page} setPage={setPage} title={title}>
      {page === "dashboard" && <Dashboard metrics={metrics} cameras={cameras} events={events} />}
      {page === "cameras" && <Cameras cameras={cameras} refresh={() => refreshCameras().catch(console.error)} />}
      {page === "live" && <LiveMonitoring cameras={cameras} />}
      {page === "events" && <Events events={events} />}
      {page === "metrics" && <SystemMetrics metrics={metrics} />}
    </Shell>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
