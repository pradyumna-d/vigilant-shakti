import { useEffect } from "react";
import { API_BASE, type DashboardMetrics } from "./api";

export function useMetricsStream(onMetrics: (metrics: DashboardMetrics) => void) {
  useEffect(() => {
    const source = new EventSource(`${API_BASE}/api/metrics/dashboard/stream`);
    source.addEventListener("metrics", (event) => {
      onMetrics(JSON.parse((event as MessageEvent).data) as DashboardMetrics);
    });
    source.onerror = () => {
      console.warn("Metrics stream disconnected; browser will retry automatically.");
    };
    return () => source.close();
  }, [onMetrics]);
}
