import { useEffect, useRef } from "react";
import { WS_BASE } from "./api";

export type RealtimeMessage = {
  topic: string;
  payload: unknown;
};

export function useRealtime(onMessage: (message: RealtimeMessage) => void) {
  const handler = useRef(onMessage);

  useEffect(() => {
    handler.current = onMessage;
  }, [onMessage]);

  useEffect(() => {
    const ws = new WebSocket(`${WS_BASE}/ws`);
    ws.onmessage = (event) => {
      try {
        handler.current(JSON.parse(event.data) as RealtimeMessage);
      } catch (error) {
        console.error("Realtime message parse failed", error);
      }
    };
    return () => {
      if (ws.readyState === WebSocket.CONNECTING || ws.readyState === WebSocket.OPEN) {
        ws.close();
      }
    };
  }, []);
}
