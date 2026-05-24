import { ChevronDown, Filter, X } from "lucide-react";
import { useState } from "react";
import type { DetectionEvent } from "../lib/api";
import { thumbnailUrl } from "../lib/api";

function eventTitle(event: DetectionEvent) {
  const label = event.event_type.replace("_", " ");
  return `${label.charAt(0).toUpperCase()}${label.slice(1)} spotted`;
}

function eventDetail(event: DetectionEvent) {
  return `${Math.round(event.confidence * 100)}% confidence`;
}

export function Events({ events }: { events: DetectionEvent[] }) {
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [selected, setSelected] = useState<DetectionEvent | null>(null);

  return (
    <div className="page">
      <section className="events-layout">
        <div className="events-toolbar panel">
          <button className="btn" onClick={() => setFiltersOpen((value) => !value)}>
            <Filter size={16} /> Filters <ChevronDown className={filtersOpen ? "rotate" : ""} size={16} />
          </button>
          <span className="micro">Showing {events.length} events</span>
        </div>

        {filtersOpen && (
          <div className="events-filter-panel panel">
            <select className="input"><option>Last 1 Hour</option><option>Last 24 Hours</option></select>
            <select className="input"><option>All Sources</option></select>
            <div className="segmented">
              <button className="btn">ALL</button>
              <button className="btn">PERSON</button>
            </div>
          </div>
        )}

        <div className="grid event-grid">
          {events.map((event) => (
            <button className="card event-card" key={event.id} onClick={() => setSelected(event)}>
              <img src={thumbnailUrl(event)} />
              <div className="event-card-body">
                <span className={event.event_type === "person" ? "chip" : "chip error"}>{event.event_type.toUpperCase()}</span>
                <h3>{eventTitle(event)}</h3>
                <div className="micro">{eventDetail(event)} | {new Date(event.timestamp).toLocaleString()} | CAM {event.camera_id}</div>
              </div>
            </button>
          ))}
        </div>
      </section>

      {selected && (
        <div className="snapshot-modal" role="dialog" aria-modal="true" onClick={() => setSelected(null)}>
          <div className="snapshot-dialog" onClick={(event) => event.stopPropagation()}>
            <button className="icon-btn" onClick={() => setSelected(null)} aria-label="Close snapshot"><X size={18} /></button>
            <img src={thumbnailUrl(selected)} />
            <div className="snapshot-meta">
              <span className={selected.event_type === "person" ? "chip" : "chip error"}>{selected.event_type.toUpperCase()}</span>
              <strong>{eventTitle(selected)}</strong>
              <span className="micro">{eventDetail(selected)} | {new Date(selected.timestamp).toLocaleString()} | CAM {selected.camera_id}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
